"""Shared technician identity and session controls."""
import os


def register_routes(app):
    from flask import jsonify, request
    import requests as http

    @app.route('/api/session', methods=['GET', 'PATCH', 'DELETE'])
    def technician_session():
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer ') or not auth[7:].strip():
            return jsonify(error='Sign in to view your account.'), 401
        url = os.getenv('SUPABASE_URL', '').rstrip('/')
        key = os.getenv('SUPABASE_PUBLISHABLE_KEY', '')
        if not url or not key:
            return jsonify(error='Account service is not configured.'), 503
        headers = {'apikey': key, 'Authorization': auth}
        try:
            if request.method == 'DELETE':
                response = http.post(url + '/auth/v1/logout?scope=local', headers=headers, timeout=20)
                if response.status_code not in (200, 204, 401, 403):
                    return jsonify(error='Signed out here; the account service could not close the remote session.'), 502
                return jsonify(ok=True)
            if request.method == 'PATCH':
                data = request.get_json(silent=True)
                name = data.get('name') if isinstance(data, dict) else None
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
                    return jsonify(error='Enter a name containing 1 to 100 characters.'), 400
                response = http.put(url + '/auth/v1/user', headers=headers,
                                    json={'data': {'display_name': name.strip()}}, timeout=20)
            else:
                response = http.get(url + '/auth/v1/user', headers=headers, timeout=20)
            if response.status_code in (401, 403):
                return jsonify(error='Your session expired. Sign in again.'), 401
            if not response.ok:
                return jsonify(error='Could not load your account. Please retry.'), 502
            user = response.json()
            metadata = user.get('user_metadata') or {}
            name = next((metadata[k].strip() for k in ('display_name', 'full_name', 'name')
                         if isinstance(metadata.get(k), str) and metadata[k].strip()), '')
            result = jsonify(user={'id': user['id'], 'name': name[:100], 'email': user.get('email', '')})
            result.headers['Cache-Control'] = 'no-store'
            return result
        except (http.RequestException, ValueError, KeyError, TypeError):
            return jsonify(error='Could not reach the account service. Please retry.'), 502
