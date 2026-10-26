/* Account-owned files and saved sets. Names are always inserted as text. */
const home = id => document.getElementById(id);
let uploading = false;
let uploadTask,uploadFailure,pendingFiles=[];
let previews;
let deleteIntent;
const previewModule = import('/static/file-previews.js').catch(() => null);
function node(tag, className, text) {
  const element = document.createElement(tag); element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function fileMetadata(file) {
  const type = file.page_count ? `PDF · ${file.page_count} ${file.page_count === 1 ? 'page' : 'pages'}` :
    file.media_type.startsWith('image/') ? 'Image' : file.media_type === 'text/markdown' ? 'Markdown' : 'Text';
  const size = file.size < 1024 * 1024 ? `${Math.max(1, Math.round(file.size / 1024))} KB` : `${(file.size / 1024 / 1024).toFixed(1)} MB`;
  return `${type} · ${size}`;
}
function row(title, metadata, url) {
  const item = node('div', 'library-row');
  const link = node('a', 'library-item-link'); link.href = url;
  link.append(node('span', 'library-item-title', title), node('span', 'library-item-meta', metadata));
  item.append(link); return item;
}
function chooseFiles() {if (!uploading) {if(archiveView)navigateFolder(null);home('library-file-input').click();}}
function showDeletion(impact) {
  home('delete-heading').textContent = deleteIntent.kind === 'documents' ? 'Delete file?' : 'Delete study set?';
  home('delete-message').textContent = `Permanently delete “${impact.title}”? This cannot be undone.`;
  const count = impact.study_sets.length;
  const copies=impact.edited_copies?.length || 0, consequences=[];
  if (copies) consequences.push(`${copies} edited ${copies===1?'copy':'copies'}`);
  if (count) consequences.push(`${count} saved study ${count===1?'set':'sets'} using ${copies?'this file or its edited copy':'this file'} as the main source`);
  home('delete-warning').textContent = consequences.length ? `This will also permanently delete ${consequences.join(' and ')}.` : '';
  home('delete-context').textContent = impact.context_sets.length ? `${impact.context_sets.length} saved ${impact.context_sets.length === 1 ? 'set used' : 'sets used'} this file only as additional context. Those sets will remain; the context attachment will be removed.` : '';
}
async function confirmDeletion(kind, id) {
  const impact = await MathPDFSession.api(`/api/${kind}/${encodeURIComponent(id)}/deletion`);
  deleteIntent = {kind, id, impact}; showDeletion(impact);
  home('delete-error').hidden = true; home('confirm-delete').disabled = false;
  home('delete-dialog').showModal();
}
home('cancel-delete').addEventListener('click', () => home('delete-dialog').close());
home('delete-dialog').addEventListener('cancel', event => {
  if (home('confirm-delete').disabled) event.preventDefault();
});
home('delete-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!deleteIntent) return;
  const intent = deleteIntent; home('confirm-delete').disabled = true; home('cancel-delete').disabled = true;
  try {
    const result = await MathPDFSession.api(`/api/${intent.kind}/${encodeURIComponent(intent.id)}`,
      {method: 'DELETE', headers: {'If-Match': intent.impact.revision}});
    if (result.deleted_document_id) {
      try {
        const {clearVisualCache}=await import('/static/visual-cache.js');
        for (const id of result.deleted_document_ids || [result.deleted_document_id]) await clearVisualCache(MathPDFSession.user.id,id);
      } catch {}
    }
    home('delete-dialog').close(); deleteIntent = null; await loadLibrary();
  } catch (error) {
    if (error.status === 409) {
      try {intent.impact = await MathPDFSession.api(`/api/${intent.kind}/${encodeURIComponent(intent.id)}/deletion`); showDeletion(intent.impact);} catch {}
    }
    home('delete-error').textContent = error.message; home('delete-error').hidden = false;
  } finally {home('confirm-delete').disabled = false; home('cancel-delete').disabled = false;}
});
let library={folders:[],files:[],sets:[]},currentFolder=null,archiveView=false,folderIntent,moveIntent,removeFolderIntent;
const folderIcon='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7V5h6l2 2h10v13H3Z"/></svg>';
function control(text, className, action, label) {
  const b=node('button',className,text);b.type='button';if(label)b.setAttribute('aria-label',label);
  b.addEventListener('click',()=>Promise.resolve().then(action).catch(showError));return b;
}
function jsonWrite(method, data) {return {method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)};}
function folderPath(id) {
  const path=[],seen=new Set();let f=library.folders.find(f=>f.id===id);
  while(f&&!seen.has(f.id)){seen.add(f.id);path.unshift(f);f=library.folders.find(p=>p.id===f.parent_id);}
  return path;
}
function locationName(id) {return ['Your library',...folderPath(id).map(f=>f.name)].join(' / ');}
function navigateFolder(id, archive=false) {
  currentFolder=id;archiveView=archive;
  const url=new URL(location.href);url.searchParams.delete('folder');url.searchParams.delete('view');
  if(id&&!archive)url.searchParams.set('folder',id);if(archive)url.searchParams.set('view','archive');
  history.pushState(null,'',url);renderLibrary();
}
function readLocation() {
  const query=new URLSearchParams(location.search);currentFolder=query.get('folder');archiveView=query.get('view')==='archive';
  if(currentFolder&&!library.folders.some(f=>f.id===currentFolder))currentFolder=null;
}
function menu(title, actions) {
  const details=node('details','item-menu'),summary=node('summary','','⋯');summary.setAttribute('aria-label',`Actions for ${title}`);
  const panel=node('div','item-menu-panel');
  for(const [text,action,danger] of actions)panel.append(control(text,danger?'menu-danger':'',()=>{details.open=false;return action();},`${text} ${title}`));
  details.append(summary,panel);return details;
}
function itemMenu(kind,item,title) {
  return menu(title,[['Move',()=>showMove(kind,item.id,title,item.folder_id)],
    [item.archived?'Restore':'Archive',()=>organize(kind,item.id,{archived:!item.archived})],
    ['Delete',()=>confirmDeletion(kind,item.id),true]]);
}
async function organize(kind,id,update) {
  await MathPDFSession.api(`/api/library/items/${kind}/${encodeURIComponent(id)}`,jsonWrite('PATCH',update));await loadLibrary();
}
function dragItem(element, kind, id) {
  element.draggable=true;
  element.addEventListener('dragstart',event=>{if(event.target.closest('button,summary')){event.preventDefault();return;}
    event.dataTransfer.setData('application/x-mathpdf-item',JSON.stringify({kind,id}));event.dataTransfer.effectAllowed='move';});
}
function dropFolder(element,id) {
  element.addEventListener('dragover',event=>{if([...event.dataTransfer.types].includes('application/x-mathpdf-item')){event.preventDefault();element.classList.add('drop-target');event.dataTransfer.dropEffect='move';}});
  element.addEventListener('dragleave',()=>element.classList.remove('drop-target'));
  element.addEventListener('drop',event=>{event.preventDefault();element.classList.remove('drop-target');
    try {const {kind,id:itemId}=JSON.parse(event.dataTransfer.getData('application/x-mathpdf-item'));
      const known=kind==='folders'?library.folders:kind==='documents'?library.files:kind==='study-sets'?library.sets:[];
      if(!known.some(item=>item.id===itemId))return;
      (kind==='folders'?MathPDFSession.api(`/api/library/folders/${itemId}`,jsonWrite('PATCH',{parent_id:id})).then(loadLibrary):organize(kind,itemId,{folder_id:id})).catch(showError);
    }catch{showError(new Error('This item could not be moved.'));}});
}
function renderNavigation() {
  home('new-folder').disabled=false;home('archive-view').disabled=false;
  home('library-breadcrumbs').hidden=!currentFolder&&!archiveView;
  home('archive-view').setAttribute('aria-pressed',String(archiveView));
  const archived=library.files.filter(f=>f.archived).length+library.sets.filter(s=>s.archived).length;
  home('archive-count').textContent=archived?String(archived):'';
  home('archive-note').hidden=!archiveView;home('new-folder').hidden=archiveView;
  const crumbs=home('library-breadcrumbs');crumbs.replaceChildren();
  const root=control('Your library','breadcrumb',()=>navigateFolder(null));dropFolder(root,null);crumbs.append(root);
  for(const f of archiveView?[{name:'Archive',id:null}]:folderPath(currentFolder)){
    crumbs.append(node('span','breadcrumb-divider','/'));
    const b=control(f.name,'breadcrumb',()=>navigateFolder(f.id,archiveView));if(!archiveView)dropFolder(b,f.id);crumbs.append(b);
  }
  crumbs.lastElementChild.setAttribute('aria-current','page');
  const children=archiveView?[]:library.folders.filter(f=>f.parent_id===currentFolder);
  home('library-folders').replaceChildren(...children.map(f=>{
    const tile=node('article','folder-tile');
    const open=control('','folder-open',()=>navigateFolder(f.id),`Open folder ${f.name}`);
    const icon=node('span','folder-icon');icon.innerHTML=folderIcon;
    const copy=node('span','folder-copy');copy.append(node('strong','',f.name));
    const files=library.files.filter(x=>!x.archived&&x.folder_id===f.id).length,sets=library.sets.filter(x=>!x.archived&&x.folder_id===f.id).length;
    copy.append(node('small','muted',`${files} ${files===1?'file':'files'} · ${sets} ${sets===1?'set':'sets'}`));open.append(icon,copy);
    tile.append(open,menu(f.name,[['Rename',()=>showFolder(f)],['Move',()=>showMove('folders',f.id,f.name,f.parent_id)],['Remove folder',()=>showRemoveFolder(f),true]]));
    dragItem(tile,'folders',f.id);dropFolder(tile,f.id);return tile;
  }));
  home('library-folders').hidden=!children.length;
}
function renderLibrary() {
  previews?.destroy();previews=previewRenderer?.createFilePreviews({request:MathPDFSession.request,userId:MathPDFSession.user.id,onAuthFailure:()=>MathPDFSession.api('/api/me').catch(()=>{})});
  renderNavigation();home('library-error').hidden=true;
  const visible=item=>archiveView?item.archived:!item.archived&&item.folder_id===currentFolder;
  const files=library.files.filter(visible),sets=library.sets.filter(visible);
  home('files-count').textContent=String(files.length);home('sets-count').textContent=String(sets.length);
  home('library-files').classList.toggle('file-library',files.length>0);
  home('library-files').replaceChildren(...files.map(file=>{
    const entry=node('article','file-card');if(file.original_document_id)entry.classList.add('annotated-file');
    const link=node('a','file-card-link');link.href=`/workspace?${new URLSearchParams({document:file.id})}`;
    const preview=node('div','file-preview',previews?'Loading preview…':'Preview unavailable'),details=node('div','file-card-details');
    details.append(node('span','library-item-title',file.filename),node('span','library-item-meta',fileMetadata(file)));
    if(file.original_document_id){details.prepend(node('span','edited-copy-label','Edited copy'));const original=library.files.find(x=>x.id===file.original_document_id);if(original)details.append(node('span','library-item-meta',`From ${original.filename}`));}
    if(archiveView)details.append(node('span','library-item-meta',locationName(file.folder_id)));
    link.append(preview,details);entry.append(link);
    const footer=node('div','file-card-footer'),download=node('a','library-download','Download');
    download.href=`/api/documents/${encodeURIComponent(file.id)}/file?download=true`;download.setAttribute('aria-label',`Download ${file.filename}`);
    footer.append(download,itemMenu('documents',file,file.filename));entry.append(footer);dragItem(entry,'documents',file.id);previews?.observe(preview,file);return entry;
  }));
  if(!files.length){const empty=node('div','library-empty');empty.append(node('p','',archiveView?'No archived files.':currentFolder?'No files in this folder yet.':'Upload a PDF to start studying.'));
    if(!archiveView)empty.append(control('Upload PDF','',chooseFiles));home('library-files').append(empty);}
  const groups=new Map();
  for(const set of sets){if(!groups.has(set.document_id))groups.set(set.document_id,{name:set.document_filename,items:[]});groups.get(set.document_id).items.push(set);}
  home('library-sets').replaceChildren(...[...groups].map(([id,group])=>{
    const section=node('details','source-group');const key=`mathpdf-${MathPDFSession.user.id}-source-group-${currentFolder||'root'}-${archiveView}-${id}`;
    try{section.open=localStorage.getItem(key)!=='false';}catch{section.open=true;}
    const heading=node('summary','source-group-heading');const icon=node('span','folder-icon');icon.innerHTML=folderIcon;
    heading.append(icon,node('strong','',group.name),node('span','muted',String(group.items.length)));section.append(heading);
    section.addEventListener('toggle',()=>{try{localStorage.setItem(key,String(section.open));}catch{}});
    const list=node('div','source-group-list');
    for(const set of group.items){const kind=set.mode==='flashcards'?(set.item_count===1?'flashcard':'flashcards'):(set.item_count===1?'problem':'problems');
      const date=new Date(set.updated_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
      const meta=`${set.item_count} ${kind} · Level ${set.difficulty} · Saved ${date}${archiveView?' · '+locationName(set.folder_id):''}`;
      const entry=row(set.title,meta,`/workspace?${new URLSearchParams({set:set.id})}`);entry.append(itemMenu('study-sets',set,set.title));dragItem(entry,'study-sets',set.id);list.append(entry);}
    section.append(list);return section;
  }));
  if(!sets.length)home('library-sets').append(node('p','library-empty',archiveView?'No archived study sets.':'Study sets saved in this folder will appear here, grouped by source file.'));
}
let previewRenderer;
async function loadLibrary() {
  const [data,renderer]=await Promise.all([MathPDFSession.api('/api/library'),previewModule]);library=data;previewRenderer=renderer;
  readLocation();renderLibrary();
}
function showFolder(folder=null) {
  folderIntent=folder;home('folder-heading').textContent=folder?'Rename folder':'New folder';home('confirm-folder').textContent=folder?'Save name':'Create folder';
  home('folder-name').value=folder?.name||'';home('folder-error').hidden=true;home('folder-dialog').showModal();home('folder-name').focus();
}
async function showRemoveFolder(folder) {
  removeFolderIntent=await MathPDFSession.api(`/api/library/folders/${folder.id}/deletion`);
  home('remove-folder-message').textContent=`Remove “${removeFolderIntent.name}”? Its ${removeFolderIntent.item_count} items and ${removeFolderIntent.folder_count} subfolders will be kept.`;
  home('remove-folder-error').hidden=true;home('remove-folder-dialog').showModal();
}
function showMove(kind,id,title,folder) {
  moveIntent={kind,id};home('move-item-name').textContent=title;home('move-error').hidden=true;
  const descendants=new Set([id]);if(kind==='folders'){let changed=true;while(changed){changed=false;for(const f of library.folders)if(descendants.has(f.parent_id)&&!descendants.has(f.id)){descendants.add(f.id);changed=true;}}}
  const choices=[{id:'',name:'Your library'},...library.folders.filter(f=>kind!=='folders'||!descendants.has(f.id)).map(f=>({id:f.id,name:locationName(f.id)})).sort((a,b)=>a.name.localeCompare(b.name))];
  home('move-destination').replaceChildren(...choices.map(f=>new Option(f.name,f.id)));home('move-destination').value=folder||'';home('move-dialog').showModal();
}
async function submitDialog(event,id,button,errorId,operation) {
  event.preventDefault();home(button).disabled=true;home(errorId).hidden=true;
  try{await operation();home(id).close();await loadLibrary();}catch(error){home(errorId).textContent=error.message;home(errorId).hidden=false;}
  finally{home(button).disabled=false;}
}
home('new-folder').addEventListener('click',()=>showFolder());home('archive-view').addEventListener('click',()=>navigateFolder(null,!archiveView));
home('folder-form').addEventListener('submit',event=>submitDialog(event,'folder-dialog','confirm-folder','folder-error',()=>MathPDFSession.api(folderIntent?`/api/library/folders/${folderIntent.id}`:'/api/library/folders',jsonWrite(folderIntent?'PATCH':'POST',folderIntent?{name:home('folder-name').value}:{name:home('folder-name').value,parent_id:currentFolder}))));
home('move-form').addEventListener('submit',event=>submitDialog(event,'move-dialog','confirm-move','move-error',()=>MathPDFSession.api(moveIntent.kind==='folders'?`/api/library/folders/${moveIntent.id}`:`/api/library/items/${moveIntent.kind}/${moveIntent.id}`,jsonWrite('PATCH',moveIntent.kind==='folders'?{parent_id:home('move-destination').value||null}:{folder_id:home('move-destination').value||null}))));
home('remove-folder-form').addEventListener('submit',event=>submitDialog(event,'remove-folder-dialog','confirm-remove-folder','remove-folder-error',async()=>{
  try{return await MathPDFSession.api(`/api/library/folders/${removeFolderIntent.id}`,{method:'DELETE',headers:{'If-Match':removeFolderIntent.revision}});}
  catch(error){if(error.status===409){removeFolderIntent=await MathPDFSession.api(`/api/library/folders/${removeFolderIntent.id}/deletion`);home('remove-folder-message').textContent=`The folder changed. Review again: ${removeFolderIntent.item_count} items and ${removeFolderIntent.folder_count} subfolders will move to its parent.`;}throw error;}
}));
for(const close of document.querySelectorAll('[data-close]'))close.addEventListener('click',()=>{if(!close.closest('dialog').querySelector('button[type=submit]:disabled'))home(close.dataset.close).close();});
for(const id of ['folder-dialog','move-dialog','remove-folder-dialog'])home(id).addEventListener('cancel',event=>{if(home(id).querySelector('button[type=submit]:disabled'))event.preventDefault();});
addEventListener('popstate',()=>{readLocation();renderLibrary();});
document.addEventListener('click',event=>{for(const details of document.querySelectorAll('.item-menu[open]'))if(!details.contains(event.target))details.open=false;});
document.addEventListener('keydown',event=>{if(event.key==='Escape')for(const details of document.querySelectorAll('.item-menu[open]'))details.open=false;});

function showError(error) {home('library-error').textContent = error.message; home('library-error').hidden = false;}
home('upload-files').addEventListener('click', chooseFiles);
home('library-file-input').addEventListener('change', () => {
  const files = [...home('library-file-input').files]; home('library-file-input').value = '';
  if (!files.length || uploading) return;
  pendingFiles.push(...files);uploadTask=uploadFiles();
});
async function uploadFiles() {
  uploading = true; home('upload-files').disabled = true; home('library-error').hidden = true;
  uploadFailure=null;
  home('upload-status').hidden = false;
  let completed = 0; const failures = [], targetFolder=archiveView?null:currentFolder;
  try {
    for (const file of [...pendingFiles]) {
      home('upload-status').textContent = `Uploading ${file.name}…`;
      try {
        if (file.size > 25 * 1024 * 1024) throw new Error('The file exceeds 25 MB.');
        const body = new FormData(); body.append('file', file);
        const uploaded=await MathPDFSession.api('/api/documents', {method: 'POST', body});
        await MathPDFSession.api(`/api/library/items/documents/${uploaded.id}`,jsonWrite('PATCH',{folder_id:targetFolder,archived:false}));
        completed++;
        pendingFiles=pendingFiles.filter(pending=>pending!==file);
      } catch (error) {failures.push(`${file.name}: ${error.message}`);}
    }
    await loadLibrary();
    home('upload-status').textContent = `${completed} ${completed === 1 ? 'file' : 'files'} uploaded.`;
    if (failures.length) throw new Error(failures.join('\n'));
  } catch (error) {uploadFailure=error;showError(error);}
  finally {uploading = false; home('upload-files').disabled = false;}
}
addEventListener('pagehide', () => previews?.destroy());
MathPDFSession.ready.then(async user => {
  const {createLeaveGuard}=await import('/static/leave-guard.js');
  const leave=createLeaveGuard({pending:()=>pendingFiles.map(file=>`${file.name} · Not uploaded`),save:async()=>{
    if(!uploading && pendingFiles.length)uploadTask=uploadFiles();
    await uploadTask;if(pendingFiles.length)throw uploadFailure || new Error('Some files could not be uploaded.');
  }});
  MathPDFSession.setLeaveGuard(()=>leave.confirm(),()=>leave.reset());
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href]');if(!link || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;
    const url=new URL(link.href);if(url.origin!==location.origin || !['/','/workspace'].includes(url.pathname))return;
    event.preventDefault();leave.confirm().then(ok=>{if(ok)location.assign(url.href);}).catch(showError);
  });
  for (const id of ['files-section', 'sets-section']) {
    const section = home(id), key = `mathpdf-${user.id}-${id}-open`;
    try {section.open = localStorage.getItem(key) !== 'false';} catch {}
    section.addEventListener('toggle', () => {try {localStorage.setItem(key, String(section.open));} catch {}});
  }
  await loadLibrary(); home('upload-files').disabled = false;
}).catch(showError);
