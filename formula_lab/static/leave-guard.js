/* Save pending workspace content before an intentional in-app departure. */
export function createLeaveGuard({pending, save}) {
  const dialog=document.createElement('dialog');dialog.id='leave-dialog';dialog.setAttribute('aria-labelledby','leave-heading');
  const heading=document.createElement('h2');heading.id='leave-heading';heading.className='dialog-header';heading.textContent='Save before leaving?';
  const body=document.createElement('div');body.className='dialog-body';
  const message=document.createElement('p');message.textContent='You have unsaved work. Save it before leaving this page?';
  const list=document.createElement('ul'), status=document.createElement('p'), error=document.createElement('p');
  status.className='field-note';status.setAttribute('role','status');status.hidden=true;
  error.className='error';error.setAttribute('role','alert');error.hidden=true;
  body.append(message,list,status,error);
  const footer=document.createElement('div');footer.className='dialog-footer annotation-choice-actions';
  const cancel=document.createElement('button'), discard=document.createElement('button'), persist=document.createElement('button');
  for (const button of [cancel,discard,persist]) button.type='button';
  cancel.textContent='Cancel';cancel.className='secondary';cancel.autofocus=true;
  discard.textContent='Leave without saving';discard.className='secondary';persist.textContent='Save and leave';
  footer.append(cancel,discard,persist);dialog.append(heading,body,footer);document.body.append(dialog);
  let saving=false, approved=false, confirmation;
  function refresh() {
    list.replaceChildren(...pending().map(label=>{const item=document.createElement('li');item.textContent=label;return item;}));
  }
  function busy(value) {
    saving=value;for (const button of [cancel,discard,persist]) button.disabled=value;
    status.hidden=!value;status.textContent=value?'Saving your work…':'';dialog.setAttribute('aria-busy',String(value));
  }
  cancel.addEventListener('click',()=>dialog.close('cancel'));
  discard.addEventListener('click',()=>dialog.close('leave'));
  dialog.addEventListener('cancel',event=>{if(saving)event.preventDefault();});
  persist.addEventListener('click',async()=>{
    if(saving)return;busy(true);error.hidden=true;
    try {
      await save();
      if(pending().length)throw new Error('Some work is still unsaved. Save or finish it before leaving.');
      dialog.close('leave');
    } catch(failure) {refresh();error.textContent=failure.message;error.hidden=false;}
    finally {busy(false);}
  });
  addEventListener('beforeunload',event=>{
    if(approved){approved=false;return;}
    if(pending().length){event.preventDefault();event.returnValue='';}
  });
  addEventListener('pageshow',()=>{approved=false;});
  return {
    reset() {approved=false;},
    confirm() {
      if(confirmation)return confirmation;
      if(!pending().length){approved=true;return Promise.resolve(true);}
      refresh();error.hidden=true;busy(false);dialog.returnValue='cancel';dialog.showModal();
      confirmation=new Promise(resolve=>dialog.addEventListener('close',()=>{
        approved=dialog.returnValue==='leave';confirmation=null;resolve(approved);
      },{once:true}));
      return confirmation;
    },
  };
}
