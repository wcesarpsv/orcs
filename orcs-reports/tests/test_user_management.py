from unittest.mock import Mock,patch
import pytest
from app import app

@pytest.fixture
def client(monkeypatch):
 monkeypatch.setenv('SUPABASE_URL','https://example.invalid')
 monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','test-key')
 return app.test_client()


def test_login_required(client):
 assert client.get('/manage-users').status_code==200
 assert client.get('/api/admin/users').status_code==403
 assert client.post('/api/admin/users',json={'email':'tech@example.invalid','role':'admin'}).status_code==403


def test_admin_endpoints_delegate_identity_to_database(client):
 headers={'Authorization':'Bearer test-token'}
 with patch('user_management.http.post') as post:
  post.return_value=Mock(ok=True,status_code=200,json=lambda:{'id':'server-identity','role':'admin','active':True})
  assert client.get('/api/admin/users?profile=1',headers=headers).json['user']['role']=='admin'
  assert post.call_args.kwargs['json']=={'p_action':'me'}
  assert client.post('/api/admin/users',headers=headers,json={'email':'tech@example.invalid','role':'technician','actor_id':'forged'}).status_code==200
  assert post.call_args.args[0].endswith('/functions/v1/orcs-user-admin')
  assert post.call_args.kwargs['json']=={'email':'tech@example.invalid','role':'technician'}
  post.return_value=Mock(ok=False,status_code=403)
  r=client.patch('/api/admin/users',headers=headers,json={'user_id':'00000000-0000-4000-8000-000000000002','action':'status','active':False})
  assert r.status_code==403


def test_status_requires_boolean(client):
 assert client.patch('/api/admin/users',headers={'Authorization':'Bearer test-token'},json={'user_id':'00000000-0000-4000-8000-000000000002','action':'status','active':'false'}).status_code==400


def test_blocked_existing_session_is_denied(client):
 with patch('user_management.http.post',return_value=Mock(ok=False,status_code=403)):
  r=client.get('/api/session',headers={'Authorization':'Bearer existing-blocked-token'})
  assert r.status_code==401
  assert client.get('/api/report-template/INSTALLATION',headers={'Authorization':'Bearer existing-blocked-token'}).status_code==401
