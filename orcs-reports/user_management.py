"""Account management; role authority lives in Supabase, never in browser metadata."""
import os
from uuid import UUID
from flask import jsonify,request,render_template
import requests as http


def register_routes(app):
    def upstream(path,payload):
        url=os.getenv('SUPABASE_URL','').rstrip('/');key=os.getenv('SUPABASE_PUBLISHABLE_KEY','')
        auth=request.headers.get('Authorization','')
        if not url or not key:raise RuntimeError('Account service is not configured.')
        if not auth.startswith('Bearer ') or not auth[7:].strip():raise PermissionError('Sign in with an approved account.')
        r=http.post(url+path,headers={'apikey':key,'Authorization':auth,'Content-Type':'application/json'},json=payload,timeout=30)
        if r.status_code in (401,403):raise PermissionError('Your account is blocked, unapproved, or does not have permission for this action.')
        if not r.ok:
            if path.startswith('/functions/'):
                message=r.json().get('error','Could not send invitation. Please retry later.')
                raise ValueError(message)
            raise ValueError('Account action failed. Reload the user list and retry.')
        return r.json()

    @app.get('/manage-users')
    def manage_users_page():return render_template('manage_users.html')

    @app.route('/api/admin/users',methods=['GET','POST','PATCH'])
    def manage_users_api():
        try:
            if request.method=='GET':
                me=upstream('/rest/v1/rpc/orcs_manage_users',{'p_action':'me'})
                if request.args.get('profile')=='1':return jsonify(user=me)
                return jsonify(user=me,users=upstream('/rest/v1/rpc/orcs_manage_users',{'p_action':'list'}))
            data=request.get_json(silent=True)
            if not isinstance(data,dict):raise ValueError('Invalid account request.')
            if request.method=='POST':
                return jsonify(upstream('/functions/v1/orcs-user-admin',{'email':data.get('email'),'role':data.get('role')}))
            target=str(UUID(str(data.get('user_id',''))));action=data.get('action')
            payload={'p_action':action,'p_target':target}
            if action=='status':
                if type(data.get('active')) is not bool:raise ValueError('Invalid account status.')
                payload['p_active']=data['active']
            elif action=='role':
                if data.get('role') not in ('technician','admin'):raise ValueError('Select Technician or Admin.')
                payload['p_role']=data['role']
            else:raise ValueError('Invalid account action.')
            return jsonify(upstream('/rest/v1/rpc/orcs_manage_users',payload))
        except PermissionError as exc:return jsonify(error=str(exc)),403
        except (ValueError,TypeError) as exc:return jsonify(error=str(exc)),400
        except (http.RequestException,RuntimeError):return jsonify(error='Account service unavailable. Please retry.'),502

    @app.before_request
    def reject_blocked_account():
        # Existing database operations use active membership in RLS/RPCs. This also
        # protects identity/template operations with an already issued access token.
        if not (request.path=='/api/session' and request.method!='DELETE' or request.path.startswith('/api/report-template/')):return
        if not request.headers.get('Authorization','').startswith('Bearer '):return
        try:upstream('/rest/v1/rpc/orcs_manage_users',{'p_action':'me'})
        except PermissionError:return jsonify(error='Your account is blocked or unapproved. Contact the owner.'),401
        except Exception:return jsonify(error='Could not verify account access. Please retry.'),503
