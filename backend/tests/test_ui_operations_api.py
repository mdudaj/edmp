import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenants():
    host_a = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    host_b = f"tenantb-{uuid.uuid4().hex[:6]}.example"
    with schema_context("public"):
        tenant_a = Tenant(
            schema_name=f"t_{uuid.uuid4().hex[:8]}",
            name=f"Tenant A {uuid.uuid4().hex[:6]}",
        )
        tenant_a.save()
        Domain(domain=host_a, tenant=tenant_a, is_primary=True).save()
        tenant_b = Tenant(
            schema_name=f"t_{uuid.uuid4().hex[:8]}",
            name=f"Tenant B {uuid.uuid4().hex[:6]}",
        )
        tenant_b.save()
        Domain(domain=host_b, tenant=tenant_b, is_primary=True).save()
    return host_a, host_b


@pytest.mark.django_db(transaction=True)
def test_ui_operations_dashboard_and_monitors():
    host, _ = _create_tenants()
    client = Client()
    project = client.post(
        "/api/v1/projects",
        data=json.dumps({"name": "UI Ops Project"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    project_id = project.json()["id"]

    ingestion = client.post(
        "/api/v1/ingestions",
        data=json.dumps(
            {
                "project_id": project_id,
                "connector": "dbt",
                "source": {"processed_entities": 2},
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    ingestion_id = ingestion.json()["id"]
    client.post(
        "/api/v1/connectors/runs",
        data=json.dumps({"ingestion_id": ingestion_id, "execution_path": "worker"}),
        content_type="application/json",
        HTTP_HOST=host,
    )
    workflow = client.post(
        "/api/v1/orchestration/workflows",
        data=json.dumps(
            {
                "name": "ui-orch",
                "project_id": project_id,
                "steps": [{"step_id": "s1", "ingestion_id": ingestion_id}],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    run = client.post(
        "/api/v1/orchestration/runs",
        data=json.dumps({"workflow_id": workflow.json()["id"]}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    client.post(
        f"/api/v1/orchestration/runs/{run.json()['id']}/transition",
        data=json.dumps({"action": "start"}),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {"item_type": "quality_exception", "subject_ref": f"project:{project_id}"}
        ),
        content_type="application/json",
        HTTP_HOST=host,
    )
    client.post(
        "/api/v1/agent/runs",
        data=json.dumps(
            {
                "prompt": f"project:{project_id} summarize failures",
                "allowed_tools": ["quality.read"],
            }
        ),
        content_type="application/json",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )

    dashboard = client.get(
        f"/api/v1/ui/operations/dashboard?project_id={project_id}",
        HTTP_HOST=host,
    )
    assert dashboard.status_code == 200
    assert "cards" in dashboard.json()
    assert "stewardship" in dashboard.json()["cards"]
    assert "orchestration" in dashboard.json()["cards"]
    assert "agent" in dashboard.json()["cards"]

    workbench = client.get(
        "/api/v1/ui/operations/stewardship-workbench",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="policy.admin",
    )
    assert workbench.status_code == 200
    assert len(workbench.json()["items"]) == 1
    assert "assign" in workbench.json()["items"][0]["allowed_actions"]

    orchestration_monitor = client.get(
        f"/api/v1/ui/operations/orchestration-monitor?project_id={project_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert orchestration_monitor.status_code == 200
    assert len(orchestration_monitor.json()["workflows"]) == 1
    assert len(orchestration_monitor.json()["runs"]) == 1

    agent_monitor = client.get(
        f"/api/v1/ui/operations/agent-monitor?project_id={project_id}",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.editor",
    )
    assert agent_monitor.status_code == 200
    assert len(agent_monitor.json()["runs"]) == 1


@pytest.mark.django_db(transaction=True)
def test_ui_operations_are_tenant_scoped():
    host_a, host_b = _create_tenants()
    client = Client()
    client.post(
        "/api/v1/stewardship/items",
        data=json.dumps(
            {"item_type": "quality_exception", "subject_ref": "asset:customers"}
        ),
        content_type="application/json",
        HTTP_HOST=host_a,
    )
    dashboard_a = client.get("/api/v1/ui/operations/dashboard", HTTP_HOST=host_a)
    dashboard_b = client.get("/api/v1/ui/operations/dashboard", HTTP_HOST=host_b)
    assert dashboard_a.status_code == 200
    assert dashboard_b.status_code == 200
    assert dashboard_a.json()["cards"]["stewardship"]["open"] == 1
    assert dashboard_b.json()["cards"]["stewardship"]["open"] == 0


@pytest.mark.django_db(transaction=True)
def test_ui_operations_role_enforcement_when_enabled(monkeypatch):
    monkeypatch.setenv("EDMP_ENFORCE_ROLES", "true")
    host, _ = _create_tenants()
    client = Client()

    denied = client.get("/api/v1/ui/operations/dashboard", HTTP_HOST=host)
    assert denied.status_code == 403

    allowed = client.get(
        "/api/v1/ui/operations/dashboard",
        HTTP_HOST=host,
        HTTP_X_USER_ROLES="catalog.reader",
    )
    assert allowed.status_code == 200
