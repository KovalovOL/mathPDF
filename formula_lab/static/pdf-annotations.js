/* Editable marks over the immutable source, in unrotated PDF coordinates. */
import {annotationHistory, changedPages, hitMark, mergeTextRects} from '/static/pdf-annotation-model.js';
const NS = 'http://www.w3.org/2000/svg';
const svg = (tag, attributes) => {
  const node = document.createElementNS(NS, tag);
  for (const [key,value] of Object.entries(attributes || {})) node.setAttribute(key, value);
  return node;
};

export function createPdfAnnotations({state, getDocumentId, saved, report}) {
  const history = annotationHistory(state.annotations.items), pages = new Map();
  let tool = 'select', active = false, width = 2, color = '#2563eb', saving = false, gesture, selected = [], selectionFrame, savePromise, lastState;
  const colors = {pen: '#2563eb', highlight: '#facc15'};
  const post = (type, payload) => parent.postMessage({type, documentId: getDocumentId(), ...payload}, location.origin);
  function emit() {
    const value={loaded:true, active, tool, color, width, saving, dirty:history.dirty,
      canUndo:history.canUndo, canRedo:history.canRedo, baseDocumentId:state.base_document.id,
      copyDocument:state.copy_document};
    const key=JSON.stringify(value);if (key===lastState) return;lastState=key;post('annotation-state',value);
  }
  function draw(record, items = history.items) {
    const group = record.annotationGroup; if (!group) return;
    group.replaceChildren(...items.filter(mark => mark.page === record.number).map(mark => {
      if (mark.kind === 'highlight') {
        const node = svg('g', {fill:mark.color, 'fill-opacity':'.28', class:'pdf-highlight'});
        for (const quad of mark.quads) node.append(svg('polygon', {points:quad.map(p=>p.join(',')).join(' ')}));
        return node;
      }
      if (mark.points.length === 1) return svg('circle', {cx:mark.points[0][0],cy:mark.points[0][1],r:mark.width/2,fill:mark.color});
      return svg('polyline', {points:mark.points.map(p=>p.join(',')).join(' '),fill:'none',stroke:mark.color,
        'stroke-width':mark.width,'stroke-linecap':'round','stroke-linejoin':'round'});
    }));
  }
  function update(before) {
    for (const number of changedPages(before, history.items)) if (pages.has(number)) draw(pages.get(number));
    emit();
  }
  function mode() {
    for (const record of pages.values()) {
      record.annotationLayer.classList.toggle('drawing', active && !saving && ['pen','eraser'].includes(tool));
      record.annotationLayer.classList.toggle('erasing', tool === 'eraser');
    }
    emit();
  }
  function viewport(record) {
    const normal = record.page.getViewport({scale:1});
    return record.page.getViewport({scale:record.sheet.getBoundingClientRect().width/normal.width});
  }
  function point(record, event) {
    const box = record.sheet.getBoundingClientRect();
    return viewport(record).convertToPdfPoint(Math.max(0,Math.min(box.width,event.clientX-box.left)),
      Math.max(0,Math.min(box.height,event.clientY-box.top))).map(value=>Math.round(value*10000)/10000);
  }
  function finish(cancelled = false) {
    const current = gesture; if (!current) return;
    gesture = null; current.preview?.remove();
    if (current.record.annotationLayer.hasPointerCapture(current.pointer)) current.record.annotationLayer.releasePointerCapture(current.pointer);
    const before = history.items;
    if (!cancelled) history.commit(current.mark ? [...before,current.mark] : current.items);
    draw(current.record); update(before);
  }
  function move(record, event) {
    if (!gesture || gesture.pointer !== event.pointerId) return;
    event.preventDefault();
    const samples=event.getCoalescedEvents?.();
    for (const sample of samples?.length ? samples : [event]) {
      const next = point(record, sample), scale = viewport(record).scale;
      if (gesture.mark) {
        const points = gesture.mark.points, last = points.at(-1);
        if (Math.hypot(next[0]-last[0],next[1]-last[1])*scale >= .7 && points.length < 20000) points.push(next);
      } else {
        const filtered = gesture.items.filter(mark=>mark.page!==record.number || !hitMark(mark,next,7/scale));
        if (filtered.length !== gesture.items.length) {gesture.items=filtered; draw(record,filtered);}
      }
    }
    if (gesture.mark) gesture.preview.setAttribute('points',gesture.mark.points.map(p=>p.join(',')).join(' '));
  }
  function attach(record, page) {
    record.page = page;
    if (!record.annotationLayer) {
      const layer = svg('svg', {class:'annotation-layer','aria-hidden':'true'}), group = svg('g');
      layer.append(group); record.sheet.append(layer); record.annotationLayer=layer;record.annotationGroup=group;pages.set(record.number,record);
      layer.addEventListener('pointerdown', event => {
        if (!active || saving || event.button!==0 || !event.isPrimary || !['pen','eraser'].includes(tool)) return;
        event.preventDefault(); if (gesture) finish(true);
        const start=point(record,event);
        gesture={record,pointer:event.pointerId,items:history.items}; layer.setPointerCapture(event.pointerId);
        if (tool==='pen') {
          if (history.items.length>=5000) {finish(true);report('This PDF has reached the annotation limit.');return;}
          gesture.mark={id:crypto.randomUUID(),kind:'ink',page:record.number,color,width:width/(page.userUnit||1),points:[start]};
          gesture.preview=svg('polyline',{points:start.join(','),fill:'none',stroke:color,
            'stroke-width':gesture.mark.width,'stroke-linecap':'round','stroke-linejoin':'round'}); group.append(gesture.preview);
        } else move(record,event);
      });
      layer.addEventListener('pointermove',event=>move(record,event));
      layer.addEventListener('pointerup',event=>{move(record,event);finish();});
      layer.addEventListener('pointercancel',()=>finish(true));
      layer.addEventListener('lostpointercapture',()=>finish(true));
    }
    const normal=page.getViewport({scale:1});
    record.annotationLayer.setAttribute('viewBox',`0 0 ${normal.width} ${normal.height}`);
    record.annotationGroup.setAttribute('transform',`matrix(${normal.transform.join(' ')})`);
    draw(record); mode();
  }
  function captureSelection() {
    selected=[];
    const selection=getSelection(); if (!selection || selection.isCollapsed || !selection.rangeCount) return;
    const range=selection.getRangeAt(0);
    for (const record of pages.values()) {
      const text=record.sheet.querySelector('.textLayer'); if (!text) continue;
      const box=record.sheet.getBoundingClientRect(), vp=viewport(record), rectangles=[];
      const walker=document.createTreeWalker(text,NodeFilter.SHOW_TEXT);
      for (let node=walker.nextNode();node;node=walker.nextNode()) {
        if (!range.intersectsNode(node) || !node.textContent.trim()) continue;
        const part=document.createRange();part.selectNodeContents(node);
        if (range.startContainer===node) part.setStart(node,range.startOffset);
        if (range.endContainer===node) part.setEnd(node,range.endOffset);
        for (const rect of part.getClientRects()) {
          const left=Math.max(0,rect.left-box.left),right=Math.min(box.width,rect.right-box.left);
          const top=Math.max(0,rect.top-box.top),bottom=Math.min(box.height,rect.bottom-box.top);
          if (right-left<.2 || bottom-top<.2) continue;
          rectangles.push({left,right,top,bottom});
        }
      }
      const quads=mergeTextRects(rectangles).map(({left,right,top,bottom})=>
        [[left,top],[right,top],[right,bottom],[left,bottom]].map(p=>vp.convertToPdfPoint(...p).map(v=>Math.round(v*10000)/10000)));
      if (quads.length) selected.push({page:record.number,quads});
    }
  }
  function highlight() {
    captureSelection(); if (!selected.length) return;
    const added=selected.map(mark=>({id:crypto.randomUUID(),kind:'highlight',color:colors.highlight,...mark}));
    const before=history.items;history.commit([...before,...added]);getSelection().removeAllRanges();selected=[];update(before);
  }
  document.addEventListener('selectionchange',()=>{cancelAnimationFrame(selectionFrame);selectionFrame=requestAnimationFrame(captureSelection);});
  document.addEventListener('pointerup',()=>{if (active && tool==='highlight' && !saving) setTimeout(highlight,0);});
  function editHistory(redo) {
    if (saving) return;finish(true);const before=history.items;
    if (redo) history.redo();else history.undo();update(before);
  }
  async function save() {
    if (savePromise) return savePromise;
    finish();
    if (!history.dirty) return state;
    saving=true;mode();
    savePromise=(async()=>{
      try {
        const previous=getDocumentId(), items=history.items;
        const result=await MathPDFSession.api(`/api/documents/${encodeURIComponent(previous)}/annotations`,
          {method:'PUT',body:JSON.stringify({schema_version:1,items,expected_revision:state.revision}),timeoutMs:60000});
        history.markSaved(items);state=result;saved(previous,result);return result;
      } finally {saving=false;savePromise=null;mode();}
    })();
    return savePromise;
  }
  async function command(data) {
    if (data.action==='diagnostic') return {document_id:getDocumentId(),base_document_id:state.base_document.id,revision:state.revision,annotations:{schema_version:1,items:history.items},dirty:history.dirty,saving};
    if (data.action==='save') return save();
    if (saving) return;
    if (data.action==='toggle') {
      if (!state.document.original_document_id && state.copy_document) {post('annotation-open-copy',{document:state.copy_document});return;}
      active=!active;if (!active) {finish(true);tool='select';}mode();
    } else if (data.action==='tool') {
      finish(true);active=true;tool=data.tool;
      if (tool==='pen' || tool==='highlight') color=colors[tool];
      mode();if (tool==='highlight') highlight();
    } else if (data.action==='color') {color=data.color;colors[tool==='highlight'?'highlight':'pen']=color;emit();}
    else if (data.action==='width') {width=data.width;emit();}
    else if (data.action==='undo' || data.action==='redo') editHistory(data.action==='redo');
  }
  addEventListener('message',event=>{
    if (event.origin!==location.origin || event.source!==parent || event.data?.type!=='annotation-command' || event.data.documentId!==getDocumentId()) return;
    const data=event.data;
    Promise.resolve(command(data)).then(result=>{
      if (data.requestId) post('annotation-result',{requestId:data.requestId,result});
    }).catch(error=>{
      report(error.message);if (data.requestId) post('annotation-result',{requestId:data.requestId,error:error.message});
    });
  });
  addEventListener('keydown',event=>{
    if (!(event.ctrlKey||event.metaKey) || event.altKey || event.target.closest?.('input,textarea,select,[contenteditable=true]')) return;
    const key=event.key.toLowerCase();
    if (key==='s') {event.preventDefault();save().catch(error=>report(error.message));}
    else if (key==='z' && (active || history.canUndo || history.canRedo)) {event.preventDefault();editHistory(event.shiftKey);}
    else if (key==='y' && active) {event.preventDefault();editHistory(true);}
  });
  emit();
  return {attach, cancel:()=>finish(true)};
}
