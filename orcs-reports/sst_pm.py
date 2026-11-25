"""SST PM validation, template filling and printable labels."""
import base64
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from datetime import date
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
from reportlab.lib.units import inch
from reports import make_pdf,report_html

COMPONENTS=['Enclosure']+[f'Burster {i}' for i in range(1,8)]+['Scanner','Printer','Slip Reader','LCD','Keypad','Pin Pad','Router','Key']
NO_TEST={'Key','Enclosure'}
SERIAL=re.compile(r'[A-Za-z0-9][A-Za-z0-9._/\-]{2,23}\Z')

def normalize_id(value):
    raw=str(value or '').strip()
    if not re.fullmatch(r'\d{6}|\d{10}',raw):raise ValueError('Scan the 10-digit SST serial or enter the 6-digit SST ID.')
    return raw[-6:]

def prepare(data, *, for_excel=False):
    if not isinstance(data,dict):raise ValueError('Invalid SST PM data.')
    sst_id=normalize_id(data.get('sst_id'))
    place=str(data.get('place') or '').strip()[:200];rdl=str(data.get('rdl') or '').strip()
    if not place or not re.fullmatch(r'\d{1,12}',rdl):raise ValueError('Enter the store name and a valid RDL.')
    technician=str(data.get('technician') or '').strip()[:100]
    if not technician:raise ValueError('Enter the technician name.')
    visit=str(data.get('date') or '')
    try:date.fromisoformat(visit)
    except ValueError:raise ValueError('Select the PM date.')
    source=data.get('components',[])
    if not isinstance(source,list) or len(source)!=len(COMPONENTS):raise ValueError('Review all component rows.')
    by_name={r.get('name'):r for r in source if isinstance(r,dict)}
    if set(by_name)!=set(COMPONENTS):raise ValueError('Invalid or duplicate component names.')
    rows=[];seen={'reference':set(),'physical':set()};failed=[]
    for name in COMPONENTS:
        r=by_name[name];absent=r.get('absent') is True
        if absent and name not in ('Router','Key'):raise ValueError(name+' cannot be marked Not installed.')
        ref=str(r.get('reference') or '').strip();physical=str(r.get('physical') or '').strip()
        if absent:
            if ref or physical:raise ValueError(name+': clear serials before marking Not installed.')
        else:
            for col,value in [('reference',ref),('physical',physical)]:
                if not value and name!='Key':raise ValueError(name+': '+col+' serial is required.')
                if value and not SERIAL.fullmatch(value):raise ValueError(name+': serial must contain 3–24 letters, digits, dots, slashes or hyphens.')
                if value and name!='Key':
                    if value in seen[col]:raise ValueError(name+': duplicate '+col+' serial. Please rescan.')
                    seen[col].add(value)
        mismatch=bool(ref and physical and ref!=physical)
        reason=str(r.get('reason') or '').strip()[:2000]
        if mismatch and (r.get('confirmed') is not True or not reason):raise ValueError(name+': acknowledge the serial difference and enter an observation.')
        test='Not applicable' if name in NO_TEST or absent else r.get('test','')
        if test not in ('Passed','Failed','Not applicable'):raise ValueError(name+': choose Passed or Failed.')
        if test=='Failed':
            failed.append(name)
            if not reason:raise ValueError(name+': describe the failed test.')
        status='Not installed' if absent else ('Optional — not provided' if name=='Key' and not ref and not physical else ('Previously Swapped / Not Documented' if mismatch else 'OK'))
        rows.append(dict(name=name,reference=ref,physical=physical,absent=absent,test=test,reason=reason,confirmed=bool(r.get('confirmed')),status=status))
    key=data.get('key_status')
    if key not in ('Yes','No','Return SST Key'):
        if for_excel and not key:key='Not recorded'
        else:raise ValueError('Select the SST key collection status.')
    reason=str(data.get('key_reason') or '').strip()[:2000];destination=data.get('key_destination','')
    if key=='No' and not reason and not for_excel:raise ValueError('Explain why the SST key could not be collected.')
    if key=='Return SST Key' and destination not in ('Office','Warehouse') and not for_excel:raise ValueError('Select the SST key return destination.')
    photos=data.get('photos',[])
    if not isinstance(photos,list) or len(photos)>8:raise ValueError('Use at most 8 report photos.')
    validated_photos=[]
    for photo in photos:
        if not isinstance(photo,dict):raise ValueError('Invalid photo.')
        try:
            image=base64.b64decode(photo.get('image',''),validate=True)
            if not image or len(image)>500000:raise ValueError()
            with Image.open(BytesIO(image)) as im:im.verify()
        except Exception:raise ValueError('A report photo is unreadable or too large.')
        validated_photos.append(dict(caption=str(photo.get('caption') or 'Service photo')[:200],image=base64.b64encode(image).decode()))
    full=str(data.get('sst_serial') or '').strip()
    if full and (not re.fullmatch(r'\d{10}',full) or full[-6:]!=sst_id):raise ValueError('The SST serial must end with the selected SST ID.')
    return dict(sst_id=sst_id,sst_serial=full or sst_id,place=place,rdl=rdl,technician=technician,date=visit,components=rows,notes=str(data.get('notes') or '').strip()[:20000],key_status=key,key_reason=reason,key_destination=destination,photos=validated_photos,failed=failed,completed=not failed)

def sections(pm):
    outcome='PM completed' if pm['completed'] else 'PM NOT COMPLETED — failed tests require follow-up'
    result=[{'text':f"SST PM — {pm['place']} (RDL: {pm['rdl']})\nSST ID: {pm['sst_id']} | {pm['date']}\nTechnician: {pm['technician']}\n{outcome}"}]
    if pm['notes']:result.append({'text':pm['notes']})
    for r in pm['components']:
        t=f"{r['name']}\nComponent List S/N: {r['reference'] or 'Not provided'}\nPhysical S/N: {r['physical'] or 'Not provided'}\nDouble Check: {r['status']}"
        if r['name'] not in NO_TEST and not r['absent']:t+='\nFunctional test: '+r['test']
        if r['reason']:t+='\nObservation: '+r['reason']
        result.append({'text':t})
    for photo in pm['photos']:result.append({'text':photo['caption'],'image':base64.b64decode(photo['image'])})
    if pm['key_status']=='Yes':key="SST's key was successfully collected and will be returned to the office."
    elif pm['key_status']=='No':key="SST's key could not be collected for return to the office.\nReason: "+pm['key_reason']+"\nThe SST's key was returned to the retailer upon completion."
    else:key='The SST key was collected during a previous visit and will be returned to the '+pm['key_destination'].lower()+'.'
    result.append({'text':key});return result

def labels(pm):
    output=BytesIO();w,h=4*inch,inch;c=canvas.Canvas(output,pagesize=(w,h))
    for r in pm['components']:
        if r['name']=='Key' or r['absent'] or not r['physical']:continue
        c.setFont('Helvetica-Bold',9);c.drawString(10,h-12,f"{r['name']}   SST {pm['sst_id']}   RDL {pm['rdl']}")
        barcode=code128.Code128(r['physical'],barHeight=26,barWidth=.65,humanReadable=False)
        scale=min(1,(w-20)/barcode.width)
        c.saveState();c.translate((w-barcode.width*scale)/2,22);c.scale(scale,1);barcode.drawOn(c,0,0);c.restoreState()
        c.setFont('Helvetica',8);c.drawCentredString(w/2,10,r['physical']);c.showPage()
    c.save();return output.getvalue()

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ET.register_namespace('x',NS)
def q(name):return '{'+NS+'}'+name

def excel(pm):
    """Fill an Artifact Tool-prepared template without changing its styles or layout."""
    template=base64.b64decode((Path(__file__).parent/'assets/sst_template.b64').read_text())
    original=zipfile.ZipFile(BytesIO(template));data=ET.fromstring(original.read('xl/worksheets/sheet1.xml'));tag=ET.fromstring(original.read('xl/worksheets/sheet2.xml'));details=ET.fromstring(original.read('xl/worksheets/sheet3.xml'))
    def put(root,address,value,formula=None):
        cell=root.find(f'.//{q("c")}[@r="{address}"]')
        if cell is None:
            rownum=re.search(r'\d+',address)[0];row=root.find(f'.//{q("row")}[@r="{rownum}"]')
            if row is None:row=ET.SubElement(root.find(q('sheetData')),q('row'),{'r':rownum})
            cell=ET.SubElement(row,q('c'),{'r':address})
        for child in list(cell):cell.remove(child)
        if formula:
            cell.set('t','str');ET.SubElement(cell,q('f')).text=formula;ET.SubElement(cell,q('v')).text=str(value)
        else:
            cell.set('t','inlineStr');ET.SubElement(ET.SubElement(cell,q('is')),q('t')).text=str(value)
    put(data,'A3',pm['sst_serial']);put(data,'G3',pm['sst_serial']);put(data,'D3',pm['sst_id'],'RIGHT(A3,6)');put(data,'J3',pm['sst_id'],'RIGHT(G3,6)')
    put(data,'H3','OK','IF(A3=G3,"OK","SWAPPED")')
    for row,r in enumerate(pm['components'],4):
        put(data,f'A{row}',r['reference']);put(data,f'G{row}',r['physical'])
        cached='' if not r['reference'] and not r['physical'] else ('OK' if r['reference']==r['physical'] else 'SWAPPED')
        put(data,f'H{row}',cached,f'IF(AND(A{row}="",G{row}=""),"",IF(A{row}=G{row},"OK","SWAPPED"))')
    # Keep the existing Tag sheet, using physically verified serials. Key has no label.
    tag_components=[pm['components'][0]]+pm['components'][:-1]
    for idx,r in enumerate(tag_components):
        row=idx*3+1;source=4+(idx-1 if idx else 0)
        serial=r['physical'] if not r['absent'] else ''
        put(tag,f'A{row}','*'+serial+'*' if serial else '',f'IF(Data!G{source}="","","*"&Data!G{source}&"*")')
        put(tag,f'B{row+1}',r['name'],f'Data!I{source}')
        put(tag,f'A{row+2}',pm['sst_id'],'Data!J3')
    for row,(label,value) in enumerate([('SST PM', 'Component serial export — PM summary not finalized' if pm['key_status']=='Not recorded' else ('Completed' if pm['completed'] else 'Not completed — failed tests')),('SST ID',pm['sst_id']),('RDL',pm['rdl']),('Store',pm['place']),('Technician',pm['technician']),('PM date',pm['date']),('Key collection status',pm['key_status']),('Key return destination',pm['key_destination']),('Key observation',pm['key_reason']),('PM notes',pm['notes'])],1):
        put(details,f'A{row}',label);put(details,f'B{row}',value)
    for col,value in zip('ABCD',['Component','Test result','Double Check','Observation']):put(details,col+'12',value)
    for row,r in enumerate(pm['components'],13):
        for col,value in zip('ABCD',[r['name'],r['test'],r['status'],r['reason']]):put(details,f'{col}{row}',value)
    out=BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for item in original.infolist():
            content=ET.tostring(data,encoding='utf-8',xml_declaration=True) if item.filename=='xl/worksheets/sheet1.xml' else ET.tostring(tag,encoding='utf-8',xml_declaration=True) if item.filename=='xl/worksheets/sheet2.xml' else ET.tostring(details,encoding='utf-8',xml_declaration=True) if item.filename=='xl/worksheets/sheet3.xml' else original.read(item.filename)
            z.writestr(item,content)
    return out.getvalue()
