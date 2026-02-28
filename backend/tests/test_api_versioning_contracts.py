import json
import uuid

import pytest
from django.test import Client
from django_tenants.utils import schema_context

from tenants.models import Domain, Tenant


def _create_tenant_host() -> str:
    host = f"tenanta-{uuid.uuid4().hex[:6]}.example"
    with schema_context('public'):
        tenant = Tenant(
            schema_name=f't_{uuid.uuid4().hex[:8]}',
            name=f"Tenant A {uuid.uuid4().hex[:6]}",
        )
        tenant.save()
        Domain(domain=host, tenant=tenant, is_primary=True).save()
    return host


def _assert_contract_keys(payload: dict, expected_keys: set[str]) -> None:
    assert expected_keys.issubset(set(payload.keys()))


@pytest.mark.django_db(transaction=True)
def test_api_version_header_and_asset_contract_keys_are_stable():
    host = _create_tenant_host()
    client = Client()
    resp = client.post(
        '/api/v1/assets',
        data=json.dumps({'qualified_name': 'warehouse.sales.orders', 'asset_type': 'table'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert resp.status_code == 201
    assert resp.headers['X-API-Version'] == 'v1'
    _assert_contract_keys(
        resp.json(),
        {'id', 'qualified_name', 'display_name', 'asset_type', 'properties', 'created_at', 'updated_at'},
    )


@pytest.mark.django_db(transaction=True)
def test_unsupported_api_version_is_rejected():
    host = _create_tenant_host()
    client = Client()
    resp = client.get('/api/v1/assets', HTTP_HOST=host, HTTP_X_API_VERSION='v2')
    assert resp.status_code == 400
    assert resp.headers['X-API-Version'] == 'v1'
    assert resp.json()['error'] == 'unsupported_api_version'
    assert resp.json()['supported_versions'] == ['v1']


@pytest.mark.django_db(transaction=True)
def test_project_and_ingestion_contract_fields_are_stable():
    host = _create_tenant_host()
    client = Client()

    project_resp = client.post(
        '/api/v1/projects',
        data=json.dumps({'name': 'Cancer Study', 'sync_config': {'source': 'fhir'}}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert project_resp.status_code == 201
    _assert_contract_keys(
        project_resp.json(),
        {'id', 'name', 'code', 'institution_ref', 'status', 'sync_config', 'created_at', 'updated_at'},
    )

    ingestion_resp = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'project_id': project_resp.json()['id'], 'connector': 'dbt', 'source': {}}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert ingestion_resp.status_code == 201
    _assert_contract_keys(
        ingestion_resp.json(),
        {'id', 'project_id', 'connector', 'source', 'mode', 'status', 'created_at', 'updated_at'},
    )


@pytest.mark.django_db(transaction=True)
def test_stewardship_orchestration_and_agent_contract_fields_are_stable():
    host = _create_tenant_host()
    client = Client()

    stewardship_resp = client.post(
        '/api/v1/stewardship/items',
        data=json.dumps({'item_type': 'quality_exception', 'subject_ref': 'asset:warehouse.sales.orders'}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert stewardship_resp.status_code == 201
    _assert_contract_keys(
        stewardship_resp.json(),
        {'id', 'item_type', 'subject_ref', 'status', 'severity', 'resolution', 'created_at', 'updated_at'},
    )

    ingestion_resp = client.post(
        '/api/v1/ingestions',
        data=json.dumps({'connector': 'dbt', 'source': {}}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert ingestion_resp.status_code == 201

    workflow_resp = client.post(
        '/api/v1/orchestration/workflows',
        data=json.dumps(
            {
                'name': 'nightly-refresh',
                'steps': [{'step_id': 'extract', 'ingestion_id': ingestion_resp.json()['id']}],
            }
        ),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert workflow_resp.status_code == 201
    _assert_contract_keys(
        workflow_resp.json(),
        {'id', 'name', 'status', 'trigger_type', 'steps', 'created_at', 'updated_at'},
    )

    agent_resp = client.post(
        '/api/v1/agent/runs',
        data=json.dumps({'prompt': 'Summarize incidents', 'allowed_tools': ['catalog.search']}),
        content_type='application/json',
        HTTP_HOST=host,
        HTTP_X_API_VERSION='v1',
    )
    assert agent_resp.status_code == 201
    _assert_contract_keys(
        agent_resp.json(),
        {'id', 'status', 'prompt', 'allowed_tools', 'actor_id', 'created_at', 'updated_at'},
    )
