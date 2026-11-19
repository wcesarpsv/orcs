const $=id=>document.getElementById(id),form=$('report-form');let generated=null,busy=false;
function updateType(){const kind=$('kind').value,titles=kind==='BREAKFIX WJS'?[['old','Old WJS'],['new','New WJS']]:['INSTALLATION','DEINSTALLATION'].includes(kind)?[['unit','WJS Info']]:[];$('units').hidden=!titles.length;$('key-fields').hidden=kind!=='PM';$('key-status').required=kind==='PM';$('unit-fields').replaceChildren();$('wjs-install-photos').hidden=kind!=='INSTALLATION';$('sst-install-fields').hidden=kind!=='SST Install';$('sst-install-report-template').hidden=kind!=='SST Install';$('additional-report-photos').hidden=['SST PM','EXPENSE REPORT'].includes(kind);for(const name of ['sst_front_photo','sst_call_clear_photo','sst_id_photo']){form.elements[name].required=kind==='SST Install';form.elements[name].disabled=kind!=='SST Install';}$('wjs-report-template').hidden=kind!=='INSTALLATION';$('final-editor').hidden=true;$('confirm-wjs-install').hidden=true;for(const [key,title] of titles){const div=document.createElement('div');div.innerHTML=kind==='INSTALLATION'?`<h3>WJS Equipment</h3><label>Equipment source<select id="wjs-source"><option value="inventory">My Inventory</option><option value="manual">Manual entry</option></select></label><label id="wjs-inventory-wrap">Available WJS<select id="wjs-inventory-select"><option value="">Loading inventory…</option></select></label><label>S/N (Serial)<input name="unit_sn" maxlength="200" required></label><label>Call reference for inventory movement<input name="wjs_call_ref" maxlength="100" placeholder="Call / ticket number"></label>`:`<h3>${title}</h3><label class="upload">Label / serial photo<input type="file" name="${key}_photo" accept="image/jpeg,image/png"><img hidden alt="${title} label preview"></label><label>Item<input name="${key}_item" maxlength="200"></label><div class="two"><label>P/N<input name="${key}_pn" maxlength="200"></label><label>S/N (Serial)<input name="${key}_sn" maxlength="200"></label></div>`;$('unit-fields').append(div)}if(kind==='INSTALLATION')setupWjsInventory();updateKey();if(typeof toggleExpenses==='function')toggleExpenses();if(typeof toggleSstPm==='function')toggleSstPm()}
const WJS_TEMPLATE=`WJS Large Carmanah - Installation\nStore: [Store Name]\nRDL: [RDL]\n\nSummary:\nUpon arrival at the site, the retailer indicated the preferred installation location and desired height for the sign.\n\n[Additional observations]\n\nWJS Info:\nS/N: [Serial Number]\n\nAfter completion, I explained the work performed to the retailer and demonstrated that the equipment was operating correctly.`;
const templateInput=$('wjs-template-text');
const templateStatus=$('report-template-status');
let templateLoadVersion=0,templateDirty=false,templateUser='';
templateInput.value=WJS_TEMPLATE;
function templateToken(){return sessionStorage.getItem('orcs_sst_token')||''}
async function loadPersonalTemplate(){
  const version=++templateLoadVersion,token=templateToken();
  templateUser=token;
  if(!token){templateStatus.textContent='Sign in to load or save your personal template.';templateInput.value=WJS_TEMPLATE;return}
  templateStatus.textContent='Loading your saved template…';
  try{
    const response=await fetch('/api/report-template/INSTALLATION',{headers:{Authorization:'Bearer '+token},cache:'no-store'});
    const data=await response.json();
    if(version!==templateLoadVersion||token!==templateToken())return;
    if(!response.ok)throw Error(data.error||'Unable to load template.');
    if(!templateDirty)templateInput.value=data.template||WJS_TEMPLATE;
    templateStatus.textContent=data.template?'Your personal template loaded.':'Using the default ORCS template.';
  }catch(error){if(version===templateLoadVersion)templateStatus.textContent=error.message}
}
templateInput.addEventListener('input',()=>{templateDirty=true;templateStatus.textContent='Unsaved changes. Save Template to reuse this wording.'});
$('save-report-template').onclick=async()=>{
  const token=templateToken();if(!token){templateStatus.textContent='Sign in before saving your template.';return}
  const value=templateInput.value;if(!value.trim()){templateStatus.textContent='Enter template text first.';return}
  const button=$('save-report-template');button.disabled=true;
  try{
    const response=await fetch('/api/report-template/INSTALLATION',{method:'PUT',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({template:value})});
    const data=await response.json();if(!response.ok)throw Error(data.error||'Save failed.');
    templateDirty=false;templateStatus.textContent='Personal template saved to your account.';
  }catch(error){templateStatus.textContent=error.message}finally{button.disabled=false}
};
$('restore-report-template').onclick=async()=>{
  const token=templateToken();if(!token){templateStatus.textContent='Sign in to restore your saved template.';return}
  if(!confirm('Restore the original ORCS template? Your saved personal version will be deleted.'))return;
  const button=$('restore-report-template');button.disabled=true;
  try{
    const response=await fetch('/api/report-template/INSTALLATION',{method:'DELETE',headers:{Authorization:'Bearer '+token}});
    const data=await response.json();if(!response.ok)throw Error(data.error||'Restore failed.');
    templateInput.value=WJS_TEMPLATE;templateDirty=false;templateStatus.textContent='Default ORCS template restored.';
  }catch(error){templateStatus.textContent=error.message}finally{button.disabled=false}
};
document.addEventListener('orcs-session',e=>{
  const next=templateToken();
  if(next!==templateUser){templateDirty=false;loadPersonalTemplate()}
});
loadPersonalTemplate();
// SST Install follows the same account-owned template workflow, with a separate report key.
(()=>{
const input=$('sst-install-template'),message=$('sst-install-template-status'),defaultText=input.value;
const endpoint='/api/report-template/'+encodeURIComponent('SST Install');
let generation=0,dirty=false,owner='';
async function load(){
 const version=++generation,token=templateToken();owner=token;
 // Clear another user's wording before starting an asynchronous account switch.
 input.value=defaultText;dirty=false;
 if(!token){message.textContent='Sign in to load or save your personal template.';return}
 message.textContent='Loading your saved template…';
 try{
  const response=await fetch(endpoint,{headers:{Authorization:'Bearer '+token},cache:'no-store'}),data=await response.json();
  if(version!==generation||token!==templateToken())return;
  if(!response.ok)throw Error(data.error||'Unable to load template.');
  if(!dirty)input.value=data.template||defaultText;
  message.textContent=dirty?'Unsaved changes. Save Template to reuse this wording.':data.template?'Your personal template loaded.':'Using the default ORCS template.';
 }catch(error){if(version===generation&&token===templateToken())message.textContent=error.message}
}
input.addEventListener('input',()=>{dirty=true;message.textContent='Unsaved changes. Save Template to reuse this wording.'});
$('save-sst-install-template').onclick=async()=>{
 const token=templateToken();if(!token){message.textContent='Sign in before saving your template.';return}
 const value=input.value;if(!value.trim()){message.textContent='Enter template text first.';return}
 const button=$('save-sst-install-template');button.disabled=true;const version=generation;
 try{
  const response=await fetch(endpoint,{method:'PUT',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({template:value})}),data=await response.json();
  if(version!==generation||token!==templateToken())return;
  if(!response.ok)throw Error(data.error||'Save failed.');
  dirty=input.value!==value;message.textContent=dirty?'Saved. Your latest edits are not saved yet.':'Personal template saved to your account.';
 }catch(error){if(version===generation&&token===templateToken())message.textContent=error.message}finally{button.disabled=false}
};
$('restore-sst-install-template').onclick=async()=>{
 const token=templateToken();if(!token){message.textContent='Sign in to restore your saved template.';return}
 if(!confirm('Restore the original SST Install template? Your saved personal SST Install version will be deleted.'))return;
 const button=$('restore-sst-install-template');button.disabled=true;const version=generation;
 try{
  const response=await fetch(endpoint,{method:'DELETE',headers:{Authorization:'Bearer '+token}}),data=await response.json();
  if(version!==generation||token!==templateToken())return;
  if(!response.ok)throw Error(data.error||'Restore failed.');
  input.value=defaultText;dirty=false;message.textContent='Default ORCS template restored.';
 }catch(error){if(version===generation&&token===templateToken())message.textContent=error.message}finally{button.disabled=false}
};
document.addEventListener('orcs-session',()=>{if(templateToken()!==owner)load()});load();
})();
let additionalPhotos=[];const additionalInput=form.elements.additional_photos;const photoList=$('additional-photo-list');function renderAdditionalPhotos(){photoList.replaceChildren();const count=document.createElement('p');count.textContent=additionalPhotos.length+' additional photo(s) selected';photoList.append(count);additionalPhotos.forEach((file,index)=>{const row=document.createElement('div');row.style.cssText='display:flex;align-items:center;gap:10px;margin:8px 0';const image=document.createElement('img');const url=URL.createObjectURL(file);image.src=url;image.alt=file.name;image.style.cssText='width:76px;height:64px;object-fit:cover';image.onload=()=>URL.revokeObjectURL(url);const label=document.createElement('span');label.textContent=file.name;label.style.overflowWrap='anywhere';const remove=document.createElement('button');remove.type='button';remove.textContent='Remove';remove.onclick=()=>{additionalPhotos.splice(index,1);renderAdditionalPhotos()};row.append(image,label,remove);photoList.append(row)})}additionalInput.addEventListener('change',()=>{additionalPhotos.push(...Array.from(additionalInput.files));additionalInput.value='';renderAdditionalPhotos()});renderAdditionalPhotos();
let selectedWjs=null;async function setupWjsInventory(){const source=$('wjs-source'),select=$('wjs-inventory-select'),sn=form.elements.unit_sn;source.onchange=()=>{selectedWjs=null;$('wjs-inventory-wrap').hidden=source.value==='manual';sn.readOnly=false;sn.value='';if(source.value==='inventory')loadWjsInventory()};select.onchange=()=>{const row=JSON.parse(select.selectedOptions[0]?.dataset.item||'null');selectedWjs=row;sn.value=row?.serial||'';sn.readOnly=!!row};await loadWjsInventory()}
async function loadWjsInventory(){const select=$('wjs-inventory-select');if(!select)return;select.replaceChildren(new Option('Select an available WJS',''));const token=sessionStorage.getItem('orcs_sst_token');if(!token){select.add(new Option('Sign in to load inventory',''));return}try{let offset=0;do{const r=await fetch('/api/inventory/items?offset='+offset,{headers:{Authorization:'Bearer '+token}});if(!r.ok)throw Error('Could not load inventory');const d=await r.json();for(const item of d.items||[])if(item.status==='Available'&&/CARMANAH/i.test(item.product||'')){const option=new Option(item.product+' — '+item.serial,item.id);option.dataset.item=JSON.stringify(item);select.add(option)}offset=d.next_offset??null}while(offset!==null)}catch(e){select.add(new Option(e.message,''))}}
function updateKey(){const pm=$('kind').value==='PM',s=$('key-status').value;$('reason-field').hidden=!pm||s!=='No';$('destination-field').hidden=!pm||s!=='Return SST Key';form.elements.key_reason.required=pm&&s==='No';form.elements.key_destination.required=pm&&s==='Return SST Key'}
$('kind').onchange=updateType;$('key-status').onchange=updateKey;updateType();
form.addEventListener('change',e=>{if(e.target.type!=='file')return;const img=e.target.parentElement.querySelector('img');if(!img)return;if(img.dataset.url)URL.revokeObjectURL(img.dataset.url);const file=e.target.files[0];img.hidden=!file;if(file){img.src=URL.createObjectURL(file);img.dataset.url=img.src}});
async function optimize(file){const img=new Image(),url=URL.createObjectURL(file);try{img.src=url;await img.decode();const scale=Math.min(1,1600/img.naturalWidth,1600/img.naturalHeight),canvas=document.createElement('canvas');canvas.width=Math.round(img.naturalWidth*scale);canvas.height=Math.round(img.naturalHeight*scale);const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.8));if(!blob)throw Error('Could not prepare photo.');return blob}finally{URL.revokeObjectURL(url)}}
function fillExtracted(d){if(!d)return;for(const name of ['place','rdl'])if(d[name]&&!form.elements[name].value.trim())form.elements[name].value=d[name];for(const u of d.units||[])for(const field of ['item','pn','sn']){const input=form.elements[u.key+'_'+field];if(input&&!input.value.trim())input.value=u[field]||''}}
function status(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error)}
form.onsubmit=async e=>{e.preventDefault();if($('sst-scan-dialog')?.open)return;if($('kind').value==='SST PM'){await generateSstPm();return}if($('kind').value==='EXPENSE REPORT'){await generateExpenses();return}if(busy)return;if($('kind').value==='SST Install'){for(const [name,label] of [['sst_front_photo','SST front'],['sst_call_clear_photo','Call Clear'],['sst_id_photo','SST ID']])if(!form.elements[name]?.files.length){status('Required photo missing: '+label,true);return}}if($('kind').value==='INSTALLATION'){for(const name of ['store_front_photo','wjs_serial_photo','call_completion_photo'])if(!form.elements[name]?.files.length){status('Required photo missing: '+name.replaceAll('_',' '),true);return}if($('wjs-source').value==='inventory'&&!selectedWjs){status('Select a WJS from My Inventory or choose Manual entry.',true);return}}busy=true;$('generate').disabled=true;status('Preparing photos…');try{const data=new FormData(form);data.delete('additional_photos');for(const [name,value] of [...data.entries()])if(value instanceof File){if(!value.size){data.delete(name);continue}const optimized=await optimize(value);data.set(name,optimized,name+'.jpg')}{for(const file of additionalPhotos){const optimized=await optimize(file);data.append('additional_photos',optimized,file.name+'.jpg')}}let total=0;for(const v of data.values())total+=v instanceof Blob?v.size:new Blob([v]).size;if(total>18000000)throw Error('Photos are still too large. Crop the labels and try again.');status('Reading photos and preparing your report…');const r=await fetch('/api/generate',{method:'POST',body:data});if(!(r.headers.get('content-type')||'').includes('application/json'))throw Error('Server request failed. Please try again.');const result=await r.json();fillExtracted(result.extracted);if(!r.ok)throw Error([result.error,...(result.warnings||[])].join(' '));generated=result;setupFinalEditor();$('confirm-wjs-install').hidden=$('kind').value!=='INSTALLATION'||!selectedWjs;$('word').hidden=true;$('sst-excel').hidden=true;$('sst-labels').hidden=true;$('report').innerHTML=result.html;$('warnings').textContent=(result.warnings||[]).join(' ');$('empty').hidden=true;$('result').hidden=false;$('report-badge').textContent='Ready for review';$('copy-status').textContent='';status('Report generated. Review serials and service statements.');if(window.innerWidth<850)$('result').scrollIntoView({behavior:'smooth',block:'start'})}catch(e){status(e.message||'Unable to generate report.',true)}finally{busy=false;$('generate').disabled=false}};

const finalEditor=$('final-editor'),finalText=$('final-report-text');
let editableSectionIndices=[];
function setupFinalEditor(){
  const enabled=false;
  finalEditor.hidden=!enabled;
  if(!enabled)return;
  editableSectionIndices=generated.sections.map((s,i)=>!s.image?i:-1).filter(i=>i>=0);
  const original=editableSectionIndices.map(i=>generated.sections[i].text).join('\\n\\n');
  const draftKey='orcs_wjs_final_draft';
  const fingerprint=JSON.stringify({serial:form.elements.unit_sn?.value,rdl:form.elements.rdl?.value,original});
  let saved=null;try{saved=JSON.parse(sessionStorage.getItem(draftKey)||'null')}catch{}
  finalText.value=saved?.fingerprint===fingerprint?saved.text:original;
  finalText.dataset.fingerprint=fingerprint;
  applyFinalEdits();
}
function applyFinalEdits(){
  if(!generated||finalEditor.hidden)return;
  const edited=finalText.value;
  const first=editableSectionIndices[0];
  if(first===undefined)return;
  for(const i of editableSectionIndices)generated.sections[i].text=i===first?edited:'';
  generated.plain=generated.sections.map(s=>s.text).filter(Boolean).join('\\n\\n');
  const preview=$('report');
  preview.replaceChildren();
  for(const section of generated.sections){
    if(section.text){const p=document.createElement('p');p.style.whiteSpace='pre-wrap';p.textContent=section.text;preview.append(p)}
    if(section.image){const img=document.createElement('img');img.src='data:image/jpeg;base64,'+section.image;img.alt=section.text||'Report photo';img.style.maxWidth='100%';preview.append(img)}
  }
  generated.html=preview.innerHTML;
  $('report-badge').textContent='Ready for review / editable';
}
finalText.addEventListener('input',()=>{
  try{sessionStorage.setItem('orcs_wjs_final_draft',JSON.stringify({fingerprint:finalText.dataset.fingerprint,text:finalText.value}))}catch{}
  applyFinalEdits();
});

function selectReport(){const range=document.createRange();range.selectNodeContents($('report'));const s=window.getSelection();s.removeAllRanges();s.addRange(range)}
function legacyCopy(rich){const handler=e=>{e.clipboardData.setData('text/plain',generated.plain);if(rich)e.clipboardData.setData('text/html',generated.html);e.preventDefault()};document.addEventListener('copy',handler);selectReport();try{return document.execCommand('copy')}finally{document.removeEventListener('copy',handler)}}
$('copy-rich').onclick=async()=>{if(!generated)return;try{await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([generated.html],{type:'text/html'}),'text/plain':new Blob([generated.plain],{type:'text/plain'})})]);$('copy-status').textContent='Formatted report copied. Check photos after pasting.'}catch{$('copy-status').textContent=legacyCopy(true)?'Formatted copy requested. Check photos after pasting.':'Report selected. Copy manually or download PDF.'}};
$('copy-text').onclick=async()=>{if(!generated)return;try{await navigator.clipboard.writeText(generated.plain);$('copy-status').textContent='Text copied.'}catch{$('copy-status').textContent=legacyCopy(false)?'Text copied.':'Use Select report and copy manually.'}};
$('select').onclick=()=>{selectReport();$('copy-status').textContent='Report selected. Use your browser Copy command.'};
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000)}
$('txt').onclick=()=>{if(generated)download(new Blob([generated.plain],{type:'text/plain;charset=utf-8'}),generated.filename+'.txt')};
$('pdf').onclick=async()=>{if(!generated)return;$('pdf').disabled=true;try{const r=await fetch('/api/pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sections:generated.sections})});if(!r.ok)throw Error('PDF export failed. Try again or download TXT.');download(await r.blob(),generated.filename+'.pdf');$('copy-status').textContent='PDF downloaded.'}catch(e){$('copy-status').textContent=e.message}finally{$('pdf').disabled=false}};

$('confirm-wjs-install').onclick=async()=>{if(!generated||!selectedWjs)return;const ref=form.elements.wjs_call_ref.value.trim(),rdl=form.elements.rdl.value.trim().replace(/^RDL\s*:\s*/i,'');if(!ref){status('Enter the call reference before confirming installation.',true);return}if(!confirm('Confirm WJS '+selectedWjs.serial+' installed at RDL '+rdl+'? This updates My Inventory.'))return;const button=$('confirm-wjs-install');button.disabled=true;try{const token=sessionStorage.getItem('orcs_sst_token');const uuid=crypto.randomUUID();const r=await fetch('/api/inventory/action',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify({action:'install',request_id:uuid,data:{id:selectedWjs.id,revision:selectedWjs.revision,call_ref:ref,rdl}})});const d=await r.json();if(!r.ok)throw Error(d.error||'Inventory update failed');button.hidden=true;status('Installation confirmed. WJS marked Installed in My Inventory.')}catch(e){status(e.message,true)}finally{button.disabled=false}};
