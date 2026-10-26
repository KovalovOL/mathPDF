/* Parent-side controls and save/generation choices; drawing stays in the PDF iframe. */
const $ = id => document.getElementById(id);
const icons={select:'M4 3l15 9-7 1-3 7-5-17z',highlight:'M5 14l9-9 5 5-9 9H5v-5z M3 21h18',
  pen:'M4 20l4-1L20 7l-3-3L5 16l-1 4z M14 7l3 3',eraser:'M3 14l9-10 9 9-7 7H9l-6-6z M7 10l9 9 M14 20h7',
  undo:'M9 5L4 10l5 5 M4 10h9a6 6 0 010 12',redo:'M15 5l5 5-5 5 M20 10h-9a6 6 0 000 12',
  save:'M5 3h12l4 4v14H3V3h2z M7 3v6h10V3 M7 21v-8h10v8'};
function iconButton(name,label) {
  const button=document.createElement('button');button.type='button';button.className='annotation-button';
  button.title=label;button.setAttribute('aria-label',label);
  const image=document.createElementNS('http://www.w3.org/2000/svg','svg');image.setAttribute('viewBox','0 0 24 24');image.setAttribute('aria-hidden','true');
  const path=document.createElementNS(image.namespaceURI,'path');path.setAttribute('d',icons[name]);image.append(path);button.append(image);return button;
}
export function createAnnotationToolbar({activeDocument, documentFor, frameFor, onSaved, onOpenCopy, onChange, notifyViewport, report}) {
  const states=new Map(), requests=new Map(), pendingOpen=new Set(), controls=new Map();
  const root=$('annotation-toolbar'), tools=$('annotation-tools'), toggle=$('annotate-pdf');
  for (const [name,label] of [['select','Select text'],['highlight','Highlight selected text'],['pen','Draw'],
    ['eraser','Erase stroke or highlight'],['undo','Undo notes'],['redo','Redo notes']]) {
    const button=iconButton(name,label);controls.set(name,button);tools.append(button);
    button.addEventListener('mousedown',event=>event.preventDefault());
    button.addEventListener('click',()=>command(activeDocument()?.id,
      ['undo','redo'].includes(name) ? {action:name} : {action:'tool',tool:name}));
  }
  const save=iconButton('save','Save PDF notes (Ctrl/Cmd+S)');controls.set('save',save);$('annotation-options').append(save);
  save.addEventListener('click',()=>saveNotes(activeDocument()?.id).catch(error=>report(error.message)));
  function command(id,data) {
    const frame=frameFor(id);if (!frame) return;
    frame.contentWindow.postMessage({type:'annotation-command',documentId:id,...data},location.origin);
  }
  function refresh() {
    const wasHidden=root.hidden;
    const doc=activeDocument(), state=states.get(doc?.id), pdf=!!doc?.page_count;
    toggle.hidden=!pdf;toggle.disabled=!state?.loaded || state.saving;
    toggle.setAttribute('aria-expanded',String(!!state?.active));
    root.hidden=!pdf || !state?.active;
    for (const [name,button] of controls) {
      button.disabled=!state?.loaded || state.saving || (name==='undo' && !state.canUndo) ||
        (name==='redo' && !state.canRedo) || (name==='save' && !state.dirty);
      if (['select','highlight','pen','eraser'].includes(name)) button.setAttribute('aria-pressed',String(state?.tool===name));
    }
    if (state) {
      for(const swatch of $('annotation-color').querySelectorAll('button')) {
        swatch.setAttribute('aria-pressed',String(swatch.dataset.color===state.color));swatch.disabled=state.saving;
      }
      $('annotation-width').value=String(state.width);
      $('annotation-width').disabled=state.saving || state.tool!=='pen';
      $('annotation-status').textContent=state.saving ? 'Saving…' : state.dirty ? 'Unsaved notes' : doc.original_document_id ? 'Saved' : 'Original';
    }
    if (wasHidden!==root.hidden) notifyViewport(true);
  }
  toggle.addEventListener('click',()=>command(activeDocument()?.id,{action:'toggle'}));
  for(const swatch of $('annotation-color').querySelectorAll('button')) {
    swatch.addEventListener('mousedown',event=>event.preventDefault());
    swatch.addEventListener('click',()=>command(activeDocument()?.id,{action:'color',color:swatch.dataset.color}));
  }
  $('annotation-width').addEventListener('change',()=>command(activeDocument()?.id,{action:'width',width:Number($('annotation-width').value)}));
  async function saveNotes(id) {
    const state=states.get(id);if (!state?.dirty) return {document:{id}};
    const source=frameFor(id)?.contentWindow;if (!source) throw new Error('Open this PDF to save its notes.');
    return new Promise((resolve,reject)=>{
      const requestId=crypto.randomUUID(), timer=setTimeout(()=>{requests.delete(requestId);reject(new Error('Saving notes timed out. Your changes remain open.'));},65000);
      requests.set(requestId,{source,resolve,reject,timer});command(id,{action:'save',requestId});
    });
  }
  function choose(id,generation) {
    const dialog=$('annotation-choice');dialog.returnValue='cancel';
    const filename=documentFor(id)?.filename || 'This PDF';
    $('annotation-choice-title').textContent=generation ? 'Use unsaved PDF notes?' : 'Save PDF notes before closing?';
    $('annotation-choice-message').textContent=generation
      ? `${filename} has unsaved notes. Send its unchanged original, or save and use the edited copy. Your notes stay open if you use the original.`
      : `${filename} has unsaved notes. Save them to its edited copy before closing?`;
    $('annotation-choice-discard').textContent=generation ? 'Use original PDF' : 'Discard changes';
    $('annotation-choice-save').textContent=generation ? 'Save and use edited copy' : 'Save and close';
    dialog.showModal();
    return new Promise(resolve=>dialog.addEventListener('close',()=>resolve(dialog.returnValue),{once:true}));
  }
  addEventListener('message',event=>{
    const data=event.data;if (event.origin!==location.origin || !data?.type?.startsWith('annotation-')) return;
    if (data.type==='annotation-result') {
      const pending=requests.get(data.requestId);if (!pending || pending.source!==event.source) return;
      requests.delete(data.requestId);clearTimeout(pending.timer);
      if (data.error) pending.reject(new Error(data.error));else pending.resolve(data.result);return;
    }
    if (event.source!==frameFor(data.documentId)?.contentWindow) return;
    if (data.type==='annotation-state') {
      states.set(data.documentId,data);refresh();onChange();
      if (pendingOpen.delete(data.documentId) && !data.active) command(data.documentId,{action:'toggle'});
    } else if (data.type==='annotation-saved') {
      const previous=states.get(data.documentId);states.delete(data.documentId);
      states.set(data.document.id,{...previous,dirty:false,copyDocument:data.document});
      onSaved(data.documentId,data.document);refresh();
    } else if (data.type==='annotation-open-copy') {
      pendingOpen.add(data.document.id);Promise.resolve(onOpenCopy(data.document)).then(()=>{
        const state=states.get(data.document.id);
        if (state?.loaded && pendingOpen.delete(data.document.id) && !state.active) command(data.document.id,{action:'toggle'});
      }).catch(error=>report(error.message));
    } else if (data.type==='annotation-error') report(data.message);
  });
  addEventListener('keydown',event=>{
    if (!(event.ctrlKey||event.metaKey) || event.altKey || !activeDocument()?.page_count) return;
    const key=event.key.toLowerCase(),id=activeDocument().id,state=states.get(id);
    if (key==='s' && state?.loaded) {event.preventDefault();saveNotes(id).catch(error=>report(error.message));return;}
    if (event.target.closest?.('input,textarea,select,[contenteditable=true]') || !(state?.active || state?.canUndo || state?.canRedo) ||
        !event.target.closest?.('#document-pane')) return;
    if (key==='z' || key==='y') {event.preventDefault();command(id,{action:key==='y'||event.shiftKey?'redo':'undo'});}
  });
  return {
    refresh, dirty:id=>!!states.get(id)?.dirty, anyDirty:()=>[...states.values()].some(state=>state.dirty || state.saving),
    dirtyDocuments:()=>[...states].filter(([,state])=>state.dirty || state.saving).map(([id])=>id),
    async saveAll() {for(const id of this.dirtyDocuments())await saveNotes(id);},
    forget:id=>states.delete(id),
    async close(id) {
      if (!states.get(id)?.dirty) return id;
      const answer=await choose(id,false);
      if (answer==='save') return (await saveNotes(id)).document.id;
      return answer==='discard' ? id : null;
    },
    async prepare(request) {
      const selections=[{id:request.document_id,replace:id=>{request.document_id=id;}},
        ...(request.context || []).map(entry=>({id:entry.document_id,replace:id=>{entry.document_id=id;}}))];
      for (const entry of selections) {
        const state=states.get(entry.id);if (!state?.dirty) continue;
        const answer=await choose(entry.id,true);
        if (answer==='save') entry.replace((await saveNotes(entry.id)).document.id);
        else if (answer==='discard') entry.replace(state.baseDocumentId);
        else return null;
      }
      return request;
    },
  };
}
