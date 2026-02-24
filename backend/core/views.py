import json

from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import DataAsset


def health(request):
    return JsonResponse({'schema': connection.schema_name})


def probe_ok(request):
    return JsonResponse({'status': 'ok'})

def livez(request):
    return probe_ok(request)


def healthz(request):
    return probe_ok(request)


def readyz(request):
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except DatabaseError:
        return JsonResponse({'status': 'not-ready'}, status=503)
    return JsonResponse({'status': 'ok'})


def _asset_to_dict(asset: DataAsset) -> dict[str, object]:
    return {
        'id': str(asset.id),
        'qualified_name': asset.qualified_name,
        'display_name': asset.display_name,
        'asset_type': asset.asset_type,
        'properties': asset.properties,
        'created_at': asset.created_at.isoformat(),
        'updated_at': asset.updated_at.isoformat(),
    }


def _parse_json_body(request):
    try:
        body = request.body.decode('utf-8') if request.body else ''
        return json.loads(body or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


@csrf_exempt
def assets(request):
    if request.method == 'GET':
        items = [_asset_to_dict(a) for a in DataAsset.objects.order_by('created_at')[:100]]
        return JsonResponse({'items': items})

    if request.method == 'POST':
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        qualified_name = payload.get('qualified_name')
        asset_type = payload.get('asset_type')
        if not qualified_name or not asset_type:
            return JsonResponse({'error': 'qualified_name and asset_type are required'}, status=400)

        asset = DataAsset.objects.create(
            qualified_name=qualified_name,
            display_name=payload.get('display_name') or qualified_name,
            asset_type=asset_type,
            properties=payload.get('properties') or {},
        )
        return JsonResponse(_asset_to_dict(asset), status=201)

    return JsonResponse({'error': 'method_not_allowed'}, status=405)


@csrf_exempt
def asset_detail(request, asset_id: str):
    try:
        asset = DataAsset.objects.get(id=asset_id)
    except DataAsset.DoesNotExist:
        return JsonResponse({'error': 'not_found'}, status=404)

    if request.method == 'GET':
        return JsonResponse(_asset_to_dict(asset))

    if request.method == 'PUT':
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'error': 'invalid_json'}, status=400)

        asset.display_name = payload.get('display_name') or asset.display_name
        asset.asset_type = payload.get('asset_type') or asset.asset_type
        if 'properties' in payload:
            asset.properties = payload.get('properties') or {}
        asset.save()
        return JsonResponse(_asset_to_dict(asset))

    return JsonResponse({'error': 'method_not_allowed'}, status=405)
