"""Technician inventory. Serial catalog ported from RouteDeskFlow bd602df, app/page.tsx."""
import re

RULES = {
    'PIN PAD': (r'P[0-9]{7}', 'P followed by 7 digits'),
    'PRINTER VKP80III': (r'MEC[0-9]{13}', 'MEC followed by 13 digits'),
    '19INCH CARMANAH SIGN': (r'EMONJC[0-9]{6}', 'EMONJC followed by 6 digits'),
    '30INCH CARMANAH SIGN': (r'EMONJC[0-9]{6}', 'EMONJC followed by 6 digits'),
    '30INCH NEW CARMANAH SIGN': (r'EMONJC[0-9]{6}', 'EMONJC followed by 6 digits'),
    '4.5 INCH BETSLIP RDR': (r'800000[0-9]{10}', '16 digits beginning with 800000'),
    'BURSTER ASSY': (r'192582[0-9]{6}', '12 digits beginning with 192582'),
    'QUAD BURSTER ASSY': (r'192582[0-9]{6}', '12 digits beginning with 192582'),
    'DS4608 SCANNER -BLACK': (r'[0-9]{14}', '14 digits'),
    'MAINBOARD ENCLOSURE': (r'[0-9A-F]{16}', '16 hexadecimal characters'),
}
STATUSES = ['Available', 'Installed', 'Return pending', 'Returned']

def normalize_serial(value):
    if not isinstance(value, str) or len(value)>200: raise ValueError('Enter a serial number as text.')
    return re.sub(r"[\s'\-]", '', value).strip('*').upper()

def identify(value):
    serial=normalize_serial(value)
    return {'serial':serial,'candidates':[name for name,(pattern,_) in RULES.items() if re.fullmatch(pattern,serial)]}

def prepare_item(data):
    if not isinstance(data,dict): raise ValueError('Invalid inventory item.')
    result=identify(data.get('serial',''))
    product=data.get('product','')
    if product not in result['candidates']: raise ValueError('Select a matching product. '+(RULES.get(product,('', 'Use a supported serial format'))[1]))
    cn=data.get('active_cn','')
    if not isinstance(cn,str) or len(cn)>100: raise ValueError('Invalid Active CN.')
    cn=re.sub(r'\s','',cn).upper()
    if cn and not re.fullmatch(r'(?:[GS][0-9]{5}|L[0-9]{6})',cn): raise ValueError('Active CN must be G/S + 5 digits or L + 6 digits.')
    condition=data.get('condition','Available')
    if condition not in ('Available','Return pending'): raise ValueError('New items must be available or awaiting return.')
    notes=data.get('notes','')
    if not isinstance(notes,str) or len(notes)>2000: raise ValueError('Notes must contain at most 2,000 characters.')
    return dict(serial=result['serial'],product=product,active_cn=cn,status=condition,notes=notes.strip())

def register_routes(app, cloud):
    from flask import jsonify, request, render_template
    from uuid import UUID
    @app.get('/inventory')
    def inventory_page():
        return render_template('index.html',materials=app.config['INVENTORY_MATERIALS'],ai_ready=False,initial_tab='inventory')

    @app.get('/api/inventory/catalog')
    def inventory_catalog():
        return jsonify(products=[dict(name=n,pattern=p,hint=h) for n,(p,h) in RULES.items()],statuses=STATUSES)

    @app.post('/api/inventory/identify')
    def inventory_identify():
        data=request.get_json(silent=True)
        try:
            if not isinstance(data,dict): raise ValueError('Invalid serial request.')
            return jsonify(identify(data.get('serial','')))
        except ValueError as exc:return jsonify(error=str(exc)),400

    def approved():
        members=cloud('GET','orcs_sst_members?select=user_id,active&active=eq.true')
        if not members: raise PermissionError('Approved technician access required.')

    def failure(exc):
        if isinstance(exc,PermissionError):return jsonify(error=str(exc)),401
        if isinstance(exc,ValueError):return jsonify(error=str(exc)),400
        return jsonify(error='Inventory service unavailable. Your form has been preserved. Retry later.'),502

    @app.get('/api/inventory/items')
    def inventory_items():
        try:
            approved()
            offset=max(0,int(request.args.get('offset','0')))
            if offset>100000: raise ValueError('Invalid page.')
            rows=cloud('GET','orcs_inventory_items?select=*&order=updated_at.desc,id.asc&limit=201&offset='+str(offset))
            return jsonify(items=rows[:200],next_offset=offset+200 if len(rows)>200 else None)
        except Exception as exc:return failure(exc)

    @app.get('/api/inventory/history/<item_id>')
    def inventory_history(item_id):
        try:
            approved();sid=str(UUID(item_id))
            rows=cloud('GET','orcs_inventory_events?select=id,action,snapshot,created_at&item_id=eq.'+sid+'&order=created_at.desc&limit=100')
            return jsonify(events=rows)
        except Exception as exc:return failure(exc)

    @app.post('/api/inventory/action')
    def inventory_action():
        try:
            data=request.get_json(silent=True)
            if not isinstance(data,dict): raise ValueError('Invalid inventory request.')
            action=data.get('action');payload=data.get('data')
            rid=str(UUID(str(data.get('request_id',''))))
            if action=='add':payload=prepare_item(payload)
            elif action in ('install','uninstall','return','restock'):
                if not isinstance(payload,dict):raise ValueError('Invalid item action.')
                iid=str(UUID(str(payload.get('id',''))));rev=payload.get('revision')
                if type(rev) is not int or rev<1:raise ValueError('Invalid item revision. Reload your inventory.')
                call=payload.get('call_ref','');rdl=payload.get('rdl','')
                if not isinstance(call,str) or len(call)>100 or not isinstance(rdl,str):raise ValueError('Invalid call reference.')
                if action in ('install','uninstall') and (not call.strip() or not re.fullmatch(r'[0-9]{1,10}',rdl.strip())):raise ValueError('Enter a call reference and valid RDL.')
                payload=dict(id=iid,revision=rev,call_ref=call.strip(),rdl=rdl.strip())
            else:raise ValueError('Invalid inventory action.')
            saved=cloud('POST','rpc/orcs_inventory_action',{'p_action':action,'p_data':payload,'p_request_id':rid})
            return jsonify(item=saved)
        except Exception as exc:return failure(exc)
