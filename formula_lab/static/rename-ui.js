/* One accessible name dialog for library items and workspace tabs. */
export function createRenameDialog(){
  const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;};
  const dialog=make('dialog'),form=make('form'),header=make('div',null,'dialog-header'),title=make('h2'),body=make('div',null,'dialog-body');
  const label=make('label','Name'),input=make('input'),note=make('p',null,'field-note'),error=make('p',null,'error');
  title.id='rename-heading';dialog.setAttribute('aria-labelledby',title.id);input.id='rename-name';label.htmlFor=input.id;input.maxLength=200;input.required=true;input.autocomplete='off';error.setAttribute('role','alert');
  header.append(title);body.append(label,input,note,error);const footer=make('div',null,'dialog-footer'),cancel=make('button','Cancel','secondary'),save=make('button','Save name');cancel.type='button';save.type='submit';footer.append(cancel,save);form.append(header,body,footer);dialog.append(form);document.body.append(dialog);
  let intent,busy=false;cancel.addEventListener('click',()=>{if(!busy)dialog.close();});dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
  form.addEventListener('submit',async event=>{event.preventDefault();if(busy||!intent)return;busy=true;save.disabled=cancel.disabled=true;error.hidden=true;
    try{await intent.save(input.value);dialog.close();}catch(failure){error.textContent=failure.message;error.hidden=false;}finally{busy=false;save.disabled=cancel.disabled=false;}});
  return {open({name,kind,save:apply}){intent={save:apply};title.textContent=kind==='documents'?'Rename file':'Rename study set';input.value=name;note.textContent=kind==='documents'?'The file type stays the same. The extension will be kept automatically.':'Your cards, solutions and progress keep their existing identifiers.';error.hidden=true;dialog.showModal();input.focus();input.select();}};
}
