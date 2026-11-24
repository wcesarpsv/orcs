from unittest.mock import Mock,patch
from app import app


def test_reporting_pages_and_unauthorized(monkeypatch):
 monkeypatch.setenv('SUPABASE_URL','https://example.invalid');monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','test')
 c=app.test_client()
 assert c.get('/inventory-reports').status_code==200
 assert c.get('/api/admin/inventory-report').status_code==403
 with patch('user_management.http.post',return_value=Mock(ok=False,status_code=403)):
  assert c.get('/api/admin/inventory-report',headers={'Authorization':'Bearer technician-token'}).status_code==403


def test_reporting_filters(monkeypatch):
 monkeypatch.setenv('SUPABASE_URL','https://example.invalid');monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','test')
 c=app.test_client();headers={'Authorization':'Bearer admin-token'}
 with patch('user_management.http.post',return_value=Mock(ok=True,status_code=200,json=lambda:{'rows':[],'count':0})) as post:
  r=c.get('/api/admin/inventory-report?kind=installations&technician=00000000-0000-4000-8000-000000000001&offset=200',headers=headers)
  assert r.status_code==200
  assert post.call_args.kwargs['json']=={'p_kind':'installations','p_owner':'00000000-0000-4000-8000-000000000001','p_status':'held','p_offset':200}
  assert c.get('/api/admin/inventory-report?technician=invalid',headers=headers).status_code==400
  assert c.get('/api/admin/inventory-report?offset=no',headers=headers).status_code==400
