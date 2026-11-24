(()=>{'use strict';
const dialog=document.getElementById('workspace-menu'),toggle=document.getElementById('workspace-menu-toggle'),close=document.getElementById('workspace-menu-close');let previousOverflow='';
function dismiss(){if(dialog.open)dialog.close()}
toggle.addEventListener('click',()=>{if(dialog.open)return dismiss();previousOverflow=document.body.style.overflow;dialog.showModal();document.body.style.overflow='hidden';toggle.setAttribute('aria-expanded','true');close.focus()});
close.addEventListener('click',dismiss);
dialog.addEventListener('close',()=>{document.body.style.overflow=previousOverflow;toggle.setAttribute('aria-expanded','false');toggle.focus()});
dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)dismiss()});
for(const button of dialog.querySelectorAll('[data-workspace-tab]'))button.addEventListener('click',()=>{const target=document.getElementById(button.dataset.workspaceTab+'-tab');dismiss();target?.click();target?.focus()});
for(const link of dialog.querySelectorAll('a'))link.addEventListener('click',dismiss);
})();
