import pytest
from django.test import Client


@pytest.mark.django_db(transaction=True)
def test_healthz_does_not_require_tenant_host():
    client = Client()
    resp = client.get('/healthz', HTTP_HOST='unknown.example')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}


@pytest.mark.django_db(transaction=True)
def test_readyz_does_not_require_tenant_host_and_checks_db():
    client = Client()
    resp = client.get('/readyz', HTTP_HOST='unknown.example')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}

