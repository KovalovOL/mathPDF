/* Local document and study workspace. Prompts and provider requests stay on the server. */
const $ = id => document.getElementById(id);
const documents = new Map(), views = new Map(), reading = new Map(), sets = new Map(), contextChoices = new Map();
const pendingUploads = new Map();
let openDocumentIds = [];
let activeDocumentId, activeSetId, config, generationActive = false, generationPreparing = false, setEpoch = 0, saveIntent, notes;
let generationController,lastGenerationSelection;
let statusTimer, practiceObserver, viewportNotice, viewportSettled = false, layout, initializing = true;
let preferencePrefix,reviewUI,limitDialog,wireFlashcard;

function el(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}
function button(text, className, action, label) {
  const item = el('button', className, text); item.type = 'button';
  if (label) item.setAttribute('aria-label', label);
  if (action) item.addEventListener('click', action);
  return item;
}
function message(text, error = false, duration = 6000) {
  clearTimeout(statusTimer);
  $('message').hidden = !text; $('message').textContent = text;
  $('message').className = `status-message${error ? ' error' : ''}`;
  if (duration && text && !error) statusTimer = setTimeout(() => {$('message').hidden = true;}, duration);
}
async function api(path, options = {}) {
  return MathPDFSession.api(path, options);
}
async function action(operation) {try {await operation();} catch (error) {message(error.message, true, 10000);}}
function preference(key, value) {
  if (!preferencePrefix) return;
  try {
    if (value === undefined) return localStorage.getItem(`${preferencePrefix}${key}`);
    localStorage.setItem(`${preferencePrefix}${key}`, String(value));
  } catch {}
}
function fileUrl(id, download = false) {return `/api/documents/${encodeURIComponent(id)}/file${download ? '?download=true' : ''}`;}
function readState(id) {
  if (!reading.has(id)) {
    let stored; try {stored = JSON.parse(preference(`reading-${id}`));} catch {}
    reading.set(id, {page: Number.isInteger(stored?.page) && stored.page > 0 ? stored.page : 1,
      zoom: ['fit', '1', '1.25', '1.5'].includes(stored?.zoom) ? stored.zoom : 'fit'});
  }
  return reading.get(id);
}
function makeTab(text, selected, operation, unsaved = false) {
  const tab = button('', 'tab', operation);
  tab.setAttribute('role', 'tab'); tab.setAttribute('aria-selected', String(selected));
  tab.tabIndex = selected ? 0 : -1; tab.title = text + (unsaved ? ' · Unsaved' : '');
  tab.append(el('span', '', text));
  if (unsaved) {const mark = el('span', 'unsaved-mark'); mark.setAttribute('aria-label', 'Unsaved'); tab.append(mark);}
  return tab;
}
function closableTab(text, selected, operation, closeOperation, unsaved = false) {
  const wrapper = el('div', 'closable-tab'); wrapper.setAttribute('role', 'presentation');
  const tab = makeTab(text, selected, operation, unsaved);
  const close = button('×', 'tab-close', closeOperation, `Close ${text}`); close.title = `Close ${text}`;
  wrapper.append(tab, close); return wrapper;
}
function wireTabs(container) {
  container.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const tabs = [...container.querySelectorAll('[role="tab"]')];
    const current = tabs.indexOf(document.activeElement); if (current < 0) return;
    event.preventDefault();
    const index = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 :
      (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    tabs[index].click();
    requestAnimationFrame(() => container.querySelector('[aria-selected="true"]')?.focus());
  });
}
function renderDocumentTabs() {
  $('document-tabs').replaceChildren(...openDocumentIds.map(id => {
    const doc = documents.get(id) || pendingUploads.get(id);
    const wrapper = closableTab(doc.filename, id === activeDocumentId, () => action(() => openDocument(id)),
      () => action(() => closeDocument(id)), pendingUploads.has(id) || notes?.dirty(id));
    wrapper.querySelector('[role="tab"]').setAttribute('aria-controls', `document-view-${id}`); return wrapper;
  }));
  $('document-tabs').querySelector('[aria-selected="true"]')?.closest('.closable-tab').scrollIntoView({block: 'nearest', inline: 'nearest'});
  preference('open-files', JSON.stringify(openDocumentIds.filter(id => documents.has(id))));
}
function updateDocumentToolbar() {
  const doc = documents.get(activeDocumentId);
  $('document-toolbar').hidden = !doc;
  if (!doc) {notes?.refresh();return;}
  const isPdf = doc.media_type === 'application/pdf', state = readState(doc.id);
  $('pdf-controls').hidden = !isPdf; $('file-type').hidden = isPdf;
  $('file-type').textContent = doc.media_type.startsWith('image/') ? 'Image' : doc.media_type === 'text/markdown' ? 'Markdown' : 'Text';
  $('download-file').href = fileUrl(doc.id, true); $('download-file').download = doc.filename;
  if (isPdf) {
    $('page').value = state.page; $('page').max = doc.page_count;
    $('page-count').textContent = `/ ${doc.page_count}`; $('zoom').value = state.zoom;
    $('previous-page').disabled = state.page <= 1; $('next-page').disabled = state.page >= doc.page_count;
  }
  notes?.refresh();
}
async function openDocument(id, targetPage, sourceRef = null) {
  const doc = documents.get(id) || pendingUploads.get(id); if (!doc) throw new Error('This source file is not available.');
  if (!initializing || sourceRef) layout?.showSource({scroll: !!sourceRef});
  const state = readState(id);
  if (targetPage !== undefined) {
    if (!doc.page_count || !Number.isInteger(targetPage) || targetPage < 1 || targetPage > doc.page_count) throw new Error('That PDF page does not exist.');
    state.page = targetPage;
  }
  if (!openDocumentIds.includes(id)) openDocumentIds.push(id);
  activeDocumentId = id; if (documents.has(id)) preference('active-file', id);
  $('document-views').querySelector('.document-empty')?.remove();
  for (const [viewId, view] of views) view.hidden = viewId !== id;
  let view = views.get(id);
  if (!view) {
    view = el('div', 'document-view'); view.id = `document-view-${id}`;
    views.set(id, view); $('document-views').append(view);
    if (pendingUploads.has(id)) {
      view.append(el('div', 'upload-state'));
    } else if (doc.page_count) {
      const iframe = el('iframe'); iframe.title = doc.filename;
      iframe.src = `/static/pdf-viewer.html?document=${encodeURIComponent(id)}&page=${state.page}&zoom=${encodeURIComponent(state.zoom)}`;
      iframe.addEventListener('load', () => {
        iframe.contentWindow.postMessage({type: 'pdf-zoom', zoom: state.zoom}, location.origin);
        iframe.contentWindow.postMessage({type: 'pdf-viewport', settled: true}, location.origin);
      });
      view.append(iframe);
    } else if (doc.media_type.startsWith('image/')) {
      const image = el('img', 'image-preview'); image.alt = doc.filename; image.src = fileUrl(id); view.append(image);
    } else {
      const preview = el('pre', 'text-preview', 'Loading file…'); view.append(preview);
      MathPDFSession.request(fileUrl(id)).then(response => {
        if (!response.ok) throw new Error('This file could not be loaded.');
        return response.text();
      }).then(text => {preview.textContent = text;}).catch(error => {preview.textContent = error.message;});
    }
  }
  if (pendingUploads.has(id)) renderUploadState(id);
  view.hidden = false;
  if (targetPage !== undefined) {
    const iframe = view.querySelector('iframe');
    if (iframe) {
      const navigation = {type: 'go-to-page', page: targetPage, animated: !!sourceRef};
      if (iframe.dataset.ready) iframe.contentWindow.postMessage(navigation, location.origin);
      else iframe.pendingNavigation = navigation;
    }
  }
  renderDocumentTabs(); updateDocumentToolbar();
  notifyPdfViewport(true);
}
function jumpPage(page) {return openDocument(activeDocumentId, page);}
function renderUploadState(id) {
  const pending = pendingUploads.get(id), content = views.get(id)?.querySelector('.upload-state');
  if (!pending || !content) return;
  content.replaceChildren(el('p', '', pending.filename), el('p', pending.error ? 'error' : 'field-note', pending.error || 'Saving to server…'));
  if (pending.error) content.append(button('Retry upload', 'secondary', () => action(() => saveUpload(id))));
}
function showEmptyDocuments() {
  activeDocumentId = null;
  for (const view of views.values()) view.hidden = true;
  $('document-views').querySelector('.document-empty')?.remove();
  const empty = el('div', 'document-empty');
  empty.append(el('p', '', documents.size ? 'No open files.' : 'Upload a PDF to start studying.'), button('Upload PDF', '', chooseFiles));
  if (documents.size) empty.append(button('Open saved files', 'secondary', () => action(showFiles)));
  $('document-views').append(empty); renderDocumentTabs(); updateDocumentToolbar();
}
async function closeDocument(id) {
  if (!openDocumentIds.includes(id)) return;
  if (pendingUploads.has(id)) {
    const pending = pendingUploads.get(id);
    const dialog = $('close-file-dialog'); dialog.returnValue = '';
    $('close-file-message').textContent = `${pending.filename} has not been saved to the server. Close this file and cancel its upload?`;
    dialog.showModal();
    const discard = await new Promise(resolve => dialog.addEventListener('close', () => resolve(dialog.returnValue === 'discard'), {once: true}));
    if (!discard) return;
    // An upload can finish while the confirmation is open; never delete a saved file.
    pendingUploads.get(id)?.controller?.abort(); pendingUploads.delete(id);
    id = pending.savedId || id;
  }
  if (documents.has(id)) {id = await notes.close(id);if (!id) return;}
  const index = openDocumentIds.indexOf(id); if (index < 0) return;
  openDocumentIds.splice(index, 1); views.get(id)?.remove(); views.delete(id);
  notes?.forget(id);
  if (activeDocumentId === id) {
    const next = openDocumentIds[Math.min(index, openDocumentIds.length - 1)];
    if (next) await openDocument(next); else showEmptyDocuments();
    $('document-tabs').querySelector('[aria-selected="true"]')?.focus();
  } else renderDocumentTabs();
}
async function showFiles() {
  const loaded = await api('/api/documents'); loaded.forEach(doc => documents.set(doc.id, doc));
  updateGenerationAvailability();
  $('files-list').replaceChildren(...loaded.map(doc => {
    const entry = button('', '', () => action(async () => {$('files-dialog').close(); await openDocument(doc.id);}));
    entry.append(el('span', '', doc.filename), el('small', '', openDocumentIds.includes(doc.id) ? 'Open' : doc.page_count ? `${doc.page_count} pages` : 'Saved'));
    return entry;
  }));
  if (!loaded.length) $('files-list').append(el('p', 'field-note', 'No saved files. Use Add files to upload a document.'));
  $('files-dialog').showModal();
}
window.addEventListener('message', event => {
  const data = event.data;
  if (event.origin === location.origin && data?.type === 'session-expired' &&
      [...views.values()].some(view => event.source === view.querySelector('iframe')?.contentWindow)) {
    action(() => MathPDFSession.api('/api/me')); return;
  }
  if (event.origin !== location.origin || !data || !['pdf-page', 'pdf-ready'].includes(data.type)) return;
  const view = views.get(data.documentId), doc = documents.get(data.documentId);
  const iframe = view?.querySelector('iframe');
  if (!iframe || event.source !== iframe.contentWindow || !doc) return;
  if (data.type === 'pdf-ready') {
    iframe.dataset.ready = 'true';
    if (iframe.pendingNavigation) {
      iframe.contentWindow.postMessage(iframe.pendingNavigation, location.origin);
      delete iframe.pendingNavigation;
    }
    return;
  }
  if (!Number.isInteger(data.page) || data.page < 1 || data.page > doc.page_count) return;
  readState(doc.id).page = data.page;
  preference(`reading-${doc.id}`, JSON.stringify(readState(doc.id)));
  if (activeDocumentId === doc.id && document.activeElement !== $('page')) updateDocumentToolbar();
});

function renderSetTabs() {
  $('set-tabs').replaceChildren(...[...sets.values()].map(record => {
    const wrapper = closableTab(record.title, record.id === activeSetId, () => action(() => openSet(record.id)),
      () => action(() => closeSet(record.id)), !record.saved);
    wrapper.querySelector('[role="tab"]').setAttribute('aria-controls', 'practice-content'); return wrapper;
  }));
  $('set-tabs').querySelector('[aria-selected="true"]')?.closest('.closable-tab').scrollIntoView({block: 'nearest', inline: 'nearest'});
  preference('open-study-sets', JSON.stringify([...sets.values()].filter(record => record.saved).map(record => record.id)));
  preference('active-study-set', activeSetId || '');
}
async function removeSetTab(id) {
  const ids = [...sets.keys()], index = ids.indexOf(id); if (index < 0) return;
  sets.delete(id);
  if (activeSetId === id) {
    ++setEpoch; activeSetId = null;
    const next = [...sets.keys()][Math.min(index, sets.size - 1)];
    if (next) await openSet(next); else renderPractice();
    renderSetTabs(); $('set-tabs').querySelector('[aria-selected="true"]')?.focus();
  } else renderSetTabs();
}
async function closeSet(id) {
  const record = sets.get(id); if (!record) return;
  if (!record.saved) {
    const dialog = $('close-set-dialog'); dialog.returnValue = '';
    $('close-set-message').textContent = `“${record.title}” has not been saved.`;
    dialog.showModal();
    const choice = await new Promise(resolve => dialog.addEventListener('close', () => resolve(dialog.returnValue), {once: true}));
    if (choice === 'save') {openSaveDialog(id, true); return;}
    if (choice !== 'discard') return;
  }
  await removeSetTab(id);
}
function openSaveDialog(id, closeAfterSave = false) {
  const record = sets.get(id); if (!record?.data) return;
  saveIntent = {id, closeAfterSave, cancelled: false};
  $('set-name').value = record.title; $('save-error').hidden = true;
  $('confirm-save').textContent = closeAfterSave ? 'Save and close' : 'Save';
  $('save-dialog').showModal();
}
function sourceOptions(result) {
  return {editable: false,
    onSource: ref => action(() => {
      const id = ref.document_id || result.document.id;
      if (!documents.has(id) && id === result.document.id) documents.set(id, result.document);
      updateGenerationAvailability(); return openDocument(id, ref.page, ref);
    }),
    sourceUrl: ref => `${fileUrl(ref.document_id || result.document.id)}#page=${ref.page}`,
    sourceLabel: ref => `Source · page ${ref.page}`};
}
function renderAnswer(container, item, result) {
  const options = sourceOptions(result); MathPDF.renderBlocks(container, item.answer, options);
  if (item.source) container.append(MathPDF.citation(item.source, options));
  for (const block of MathPDF.variantBlocks(item)) {
    container.append(el('p', 'text-block', block.change));
    container.append(el('p', 'field-note', 'Original source formula'));
    container.append(MathPDF.mathBlock({...block, latex: block.original_latex}, options));
  }
}
function fitFormulas(root) {
  for (const output of root.querySelectorAll('.math-output')) {
    output.style.fontSize = '';
    if (output.clientWidth && output.scrollWidth > output.clientWidth + 1) {
      const base = parseFloat(getComputedStyle(output).fontSize);
      output.style.fontSize = `${base * Math.max(.65, output.clientWidth / output.scrollWidth) * .98}px`;
    }
  }
}
function selectItem(index) {
  const record = sets.get(activeSetId); if (!record?.data) return;
  if (index < 0 || index >= record.data.items.length) return;
  record.itemIndex = index; record.flipped = false; record.reviewBrowse=true; renderPractice();
}
function flashcard(record, item) {
  item = MathPDF.flashcardSides(item);
  const deck = el('div', 'deck'), card = el('section', 'flashcard');
  card.tabIndex = 0; card.setAttribute('aria-label', `Card ${record.itemIndex + 1}. Press Space to flip this card.`);
  const inner = el('div', 'card-inner');
  const front = el('div', 'card-face card-front'), back = el('div', 'card-face card-back');
  const frontLabel = el('div', 'card-label'); frontLabel.append(el('span', '', 'Question'), el('span', '', `${record.itemIndex + 1} / ${record.data.items.length}`));
  const frontBody = el('div', 'card-body');
  const question = el('div', 'card-blocks'); MathPDF.renderBlocks(question, item.question, {editable: false}); frontBody.append(question);
  front.append(frontLabel, frontBody, el('p', 'card-hint', 'Tap the card or press Space to reveal'));
  const backLabel = el('div', 'card-label'); backLabel.append(el('span', '', 'Answer'), el('span', '', `${record.itemIndex + 1} / ${record.data.items.length}`));
  const backBody = el('div', 'card-body'); backBody.append(el('h2', '', item.title));
  const answer = el('div', 'card-blocks'); renderAnswer(answer, item, record.data); backBody.append(answer);
  back.append(backLabel, backBody, el('p', 'card-hint', 'Click to return to the question'));
  inner.append(front, back); card.append(inner);
  const assessment=reviewUI?.controls(record);
  let counter;
  function updateFace() {
    assessment?.update(!!record.flipped);
    if(counter)counter.hidden=!!record.flipped;
    card.classList.toggle('flipped', !!record.flipped);
    front.inert = !!record.flipped; back.inert = !record.flipped;
    front.setAttribute('aria-hidden', String(!!record.flipped)); back.setAttribute('aria-hidden', String(!record.flipped));
  }
  function flip() {record.flipped = !record.flipped; updateFace();}
  wireFlashcard(card,{flip,previous:()=>selectItem(record.itemIndex-1),next:()=>selectItem(record.itemIndex+1)});
  const navigation = el('div', 'deck-footer');navigation.setAttribute('aria-label','Card navigation and self-assessment');
  const previous = button('‹', 'secondary icon-button', () => selectItem(record.itemIndex - 1), 'Previous card');
  const next = button('›', 'secondary icon-button', () => selectItem(record.itemIndex + 1), 'Next card');
  previous.disabled = record.itemIndex === 0; next.disabled = record.itemIndex === record.data.items.length - 1;
  const center=el('div','deck-footer-center');counter=el('span','deck-counter',`${record.itemIndex+1} / ${record.data.items.length}`);center.append(counter);if(assessment)center.append(assessment.root);
  navigation.append(previous,center,next);deck.append(card,navigation);updateFace();return deck;
}
function renderPractice() {
  practiceObserver?.disconnect();
  const record = sets.get(activeSetId), result = record?.data;
  $('practice-content').replaceChildren(); $('item-tabs').replaceChildren();
  $('item-tabs').hidden = !result?.items.length;
  $('rename-set').disabled=!result?.items.length;
  $('save-set').disabled = !result?.items.length || !!record?.saved;
  $('save-set').textContent = record?.saved ? 'Saved' : 'Save';
  $('export-set').disabled = !result?.items.length;
  const itemWord = result?.mode === 'flashcards' ? 'card' : 'problem';
  $('set-status').textContent = result ? `${record.saved ? 'Saved' : 'Unsaved'} · ${result.items.length} ${itemWord}${result.items.length === 1 ? '' : 's'} · Level ${result.difficulty ?? 3}${result.mode === 'problems' ? ' · Beta' : ''}` : 'Study material';
  $('set-status').title = result ? 'Source transcription has not been verified against the PDF.' : '';
  $('study-notes').hidden = !result?.notes.length;
  const notes = el('details'); notes.append(el('summary', '', 'Generation notes'));
  notes.append(...(result?.notes || []).map(note => el('p', '', note)));
  $('study-notes').replaceChildren(notes);
  if (!result?.items.length) {
    $('practice-content').append(el('p', 'empty-state', result ? 'No study items were generated. Try different source pages.' : generationActive ? 'Your study set will appear here when it is ready.' : 'Generate a study set to start practicing.'));
    return;
  }
  record.itemIndex = Math.min(record.itemIndex || 0, result.items.length - 1);
  const itemLabel = result.mode === 'flashcards' ? 'Card' : 'Problem';
  $('item-tabs').replaceChildren(...result.items.map((item, index) =>
    makeTab(`${itemLabel} ${index + 1}`, index === record.itemIndex, () => selectItem(index))));
  const item = result.items[record.itemIndex];
  if (result.mode === 'flashcards'){const summary=reviewUI?.summary(record);$('practice-content').append(summary&&!record.reviewBrowse?summary:flashcard(record,item));}
  else {
    const problem = el('article', 'problem'); problem.append(el('h2', '', item.title));
    const question = el('div'); MathPDF.renderBlocks(question, item.question, sourceOptions(result));
    const solution = el('details', 'solution'); solution.append(el('summary', '', 'Solution'));
    const answer = el('div'); renderAnswer(answer, item, result); solution.append(answer);
    problem.append(question, solution); $('practice-content').append(problem);
  }
  practiceObserver = new ResizeObserver(() => fitFormulas($('practice-content')));
  practiceObserver.observe($('practice-content'));
  document.fonts.ready.then(() => fitFormulas($('practice-content')));
}
async function openSet(id) {
  const record = sets.get(id); if (!record) return;
  activeSetId = id; const epoch = ++setEpoch; renderSetTabs();
  if (!record.data) {
    $('practice-content').replaceChildren(el('p', 'empty-state', 'Loading study set…'));
    record.data = await api(`/api/study-sets/${encodeURIComponent(id)}`);
  }
  if (epoch !== setEpoch) return;
  record.title = record.data.title; renderPractice();
}
async function uploadFiles(files) {
  if (!files.length) return;
  const ids = [];
  for (const file of files) {
    if (file.size > 25 * 1024 * 1024) {message(`${file.name} exceeds the 25 MB upload limit.`, true); continue;}
    const id = `local-${crypto.randomUUID()}`; ids.push(id);
    pendingUploads.set(id, {filename: file.name, file, controller: null, error: null}); openDocumentIds.push(id);
  }
  if (ids.length) await openDocument(ids[ids.length - 1]);
  for (const id of ids) await saveUpload(id);
}
function saveUpload(id) {
  const pending=pendingUploads.get(id);if(!pending)return Promise.resolve();
  if(pending.promise)return pending.promise;
  pending.promise=performUpload(id,pending).finally(()=>{pending.promise=null;});
  return pending.promise;
}
async function performUpload(id,pending) {
  pending.error = null; pending.controller = new AbortController(); renderUploadState(id);
  const body = new FormData(); body.append('file', pending.file);
  try {
    const doc = await api('/api/documents', {method: 'POST', body, signal: pending.controller.signal});
    documents.set(doc.id, doc);
    updateGenerationAvailability();
    if (!pendingUploads.has(id)) return;
    pending.savedId = doc.id;
    const selected = activeDocumentId === id;
    openDocumentIds = openDocumentIds.filter(openId => openId !== doc.id).map(openId => openId === id ? doc.id : openId);
    pendingUploads.delete(id); views.get(id)?.remove(); views.delete(id);
    if (selected) await openDocument(doc.id); else renderDocumentTabs();
    if ($('generation-dialog').open) {updateSourceChoices(); renderContextChoices(); updateGenerationSummary();}
    message(`${doc.filename} saved to server.`);
  } catch (error) {
    if (!pendingUploads.has(id) || error.name === 'AbortError') return;
    pending.error = error.message; renderUploadState(id); message(`${pending.filename}: ${error.message}`, true);
  } finally {pending.controller = null;}
}
function sourceDocument() {return documents.get($('source-document').value);}
function updateGenerationAvailability() {
  const hasPdf = [...documents.values()].some(doc => doc.page_count);
  $('open-generation').disabled = generationActive || !hasPdf;
  $('open-generation').title = hasPdf ? '' : 'Upload a PDF to generate study material.';
}
function updateSourceChoices() {
  const selected = $('source-document').value;
  $('source-document').replaceChildren(...[...documents.values()].filter(doc => doc.page_count).map(doc => new Option(doc.filename, doc.id)));
  if (documents.get(selected)?.page_count) $('source-document').value = selected;
}
function sourceChanged() {
  const doc = sourceDocument(); if (!doc) return;
  const page = readState(doc.id).page;
  $('source-from').max = doc.page_count; $('source-to').max = doc.page_count;
  $('source-from').value = page; $('source-to').value = page;
  renderContextChoices(); updateRangeDisabled(); updateGenerationSummary();
}
function updateRangeDisabled() {
  const all = $('source-scope').value === 'all';
  $('source-from').disabled = all; $('source-to').disabled = all;
}
function rangePages(doc, scope, start, end) {
  if (scope === 'all') return null;
  const from = Number(start), to = Number(end);
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 1 || to < from || to > doc.page_count) {
    throw new Error(`${doc.filename}: choose a range from 1 to ${doc.page_count}, with the end at or after the start.`);
  }
  return Array.from({length: to - from + 1}, (_, index) => from + index);
}
function selectionRequest() {
  const source = sourceDocument(); if (!source) throw new Error('Add a PDF and choose it as the source.');
  const pages = rangePages(source, $('source-scope').value, $('source-from').value, $('source-to').value);
  const context = [];
  let totalPages = pages?.length || source.page_count;
  for (const [id, choice] of contextChoices) {
    if (!choice.enabled || id === source.id) continue;
    const doc = documents.get(id); if (!doc) continue;
    const contextPages = doc.page_count ? rangePages(doc, choice.scope, choice.from, choice.to) : null;
    totalPages += doc.page_count ? contextPages?.length || doc.page_count : 0;
    context.push({document_id: id, pages: contextPages});
  }
  if (context.length > 6) throw new Error('Attach up to 6 context files per request.');
  if (totalPages > 100) throw new Error('Select up to 100 PDF pages across the source and context files.');
  const count = Number($('count').value), maximum = config?.max_items || Number($('count').max);
  if (!Number.isInteger(count) || count < 1 || count > maximum) throw new Error(`Choose between 1 and ${maximum} items.`);
  return {document_id: source.id, pages, context, comment: $('context-comment').value.trim(), mode: $('mode').value, count, difficulty: Number(document.querySelector('input[name=difficulty]:checked').value)};
}
function updateGenerationSummary() {
  try {
    const selection = selectionRequest(); const doc = documents.get(selection.document_id);
    const count = selection.pages?.length || doc.page_count;
    $('generation-summary').textContent = `${selection.count} ${selection.mode === 'flashcards' ? 'flashcards' : 'problems (Beta)'} · Level ${selection.difficulty} · ${count} source ${count === 1 ? 'page' : 'pages'} · ${selection.context.length} context ${selection.context.length === 1 ? 'file' : 'files'}`;
    $('generation-summary').className = 'selection-summary';
  } catch (error) {$('generation-summary').textContent = error.message; $('generation-summary').className = 'selection-summary error';}
}
function renderContextChoices() {
  const candidates = [...documents.values()].filter(doc => doc.id !== $('source-document').value);
  if (!candidates.length) {
    $('context-files').replaceChildren(el('p', 'field-note', 'No additional files. Add PDFs, text, Markdown, or images.')); return;
  }
  const rows = candidates.map(doc => {
    if (!contextChoices.has(doc.id)) contextChoices.set(doc.id, {enabled: false, scope: 'all', from: 1, to: doc.page_count || 1});
    const choice = contextChoices.get(doc.id), row = el('div', 'context-file');
    const label = el('label', 'context-check'), checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.checked = choice.enabled;
    label.append(checkbox, el('span', '', doc.filename)); row.append(label);
    const rangeInputs = [];
    function refreshDisabled() {for (const input of rangeInputs) input.disabled = !choice.enabled || (input.type === 'number' && choice.scope === 'all');}
    checkbox.addEventListener('change', () => {choice.enabled = checkbox.checked; refreshDisabled(); updateGenerationSummary();});
    if (doc.page_count) {
      const controls = el('div', 'range-controls');
      const scopeLabel = el('label', '', 'Pages'), scope = el('select');
      scope.append(new Option('Entire PDF', 'all'), new Option('Page range', 'range')); scope.value = choice.scope;
      scope.setAttribute('aria-label', `Pages for ${doc.filename}`); scopeLabel.append(scope); controls.append(scopeLabel); rangeInputs.push(scope);
      scope.addEventListener('change', () => {choice.scope = scope.value; refreshDisabled(); updateGenerationSummary();});
      for (const [key, name] of [['from', 'From'], ['to', 'To']]) {
        const inputLabel = el('label', '', name), input = el('input'); input.type = 'number';
        input.min = 1; input.max = doc.page_count; input.value = choice[key]; input.required = true;
        input.setAttribute('aria-label', `${name} page for ${doc.filename}`); inputLabel.append(input); controls.append(inputLabel); rangeInputs.push(input);
        input.addEventListener('input', () => {choice[key] = input.value; updateGenerationSummary();});
      }
      row.append(controls); refreshDisabled();
    } else row.append(el('p', 'field-note', 'Entire file'));
    return row;
  });
  $('context-files').replaceChildren(...rows);
}
function openGeneration() {
  dispatchEvent(new Event('mathpdf-allowance-changed'));
  updateSourceChoices();
  if (documents.get(activeDocumentId)?.page_count) $('source-document').value = activeDocumentId;
  if (!sourceDocument()) {message('Upload a PDF to generate study material.'); return;}
  sourceChanged(); $('generation-error').hidden = true;
  $('generation-dialog').showModal();
}
async function generate(event) {
  event.preventDefault(); if (generationActive || generationPreparing) return;
  let request;
  try {request = selectionRequest();}
  catch (error) {$('generation-error').textContent = error.message; $('generation-error').hidden = false; return;}
  generationPreparing=true;$('generate').disabled=true;
  try {request=await notes.prepare(request);}
  finally {generationPreparing=false;$('generate').disabled=false;}
  if (!request) return;
  lastGenerationSelection=request;
  generationActive = true; $('generation-dialog').close();
  $('open-generation').disabled = true; $('open-generation').textContent = 'Generating…';
  message('');
  const word = request.mode === 'flashcards' ? 'flashcard' : 'problem';
  $('generation-progress-label').textContent = `Generating ${request.count} ${word}${request.count === 1 ? '' : 's'}…`;
  $('generation-progress').hidden = false; $('open-generation').setAttribute('aria-busy', 'true');
  if (!sets.get(activeSetId)?.data) renderPractice();
  const started = performance.now();
  function updateElapsed() {
    const seconds = Math.floor((performance.now() - started) / 1000);
    $('generation-elapsed').textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  }
  updateElapsed(); const timer = setInterval(updateElapsed, 1000);
  const controller = new AbortController(); generationController = controller;
  const deadline = setTimeout(() => controller.abort(new Error('Generation timed out. Please try again.')),
    ((config.generation_timeout_seconds || 150) + 30) * 1000);
  let jobId, terminal = false;
  $('cancel-generation').disabled = false;
  $('generation-progress-detail').textContent = 'Preparing source files…';
  function showProgress(job) {
    const phases = {preparing: 'Preparing source files',
      generating: 'Generating your study set', checking: 'Finishing your study set'};
    $('generation-progress-detail').textContent = `${phases[job.phase] || 'Generating'}…`;
  }
  function pollDelay() {
    return new Promise((resolve, reject) => {
      if (controller.signal.aborted) {reject(controller.signal.reason); return;}
      const aborted = () => {clearTimeout(wait); reject(controller.signal.reason);};
      const wait = setTimeout(() => {controller.signal.removeEventListener('abort', aborted); resolve();}, 1200);
      controller.signal.addEventListener('abort', aborted, {once: true});
    });
  }
  try {
    let job = await api('/api/study/jobs', {method: 'POST', body: JSON.stringify(request), signal: controller.signal, timeoutMs: 15000});
    jobId = job.id;
    dispatchEvent(new Event('mathpdf-allowance-changed'));
    showProgress(job);
    while (job.status === 'running') {
      await pollDelay();
      job = await api(`/api/study/jobs/${encodeURIComponent(jobId)}`, {signal: controller.signal, timeoutMs: 15000});
      showProgress(job);
    }
    terminal = true;
    if (job.status === 'failed') {
      if(job.limit?.code==='generation_limit')throw Object.assign(new Error(job.error),job.limit);
      const reference = /^[a-f0-9]{32}$/.test(job.request_id || '') ? ` Reference: ${job.request_id}` : '';
      throw new Error((job.error || 'Generation failed. Please try again.') + reference);
    }
    if (job.status !== 'completed') {message('Generation cancelled.'); return;}
    const data = job.result;
    if (data.items.length !== request.count) throw new Error('The complete requested set was not returned. Please try again.');
    sets.set(data.id, {id: data.id, title: data.title, data, saved: false, itemIndex: 0, flipped: false});
    await openSet(data.id);
    message(`Created ${data.items.length} ${data.mode === 'flashcards' ? 'flashcards' : 'problems'}.`);
  } catch (error) {
    if (controller.signal.reason?.name === 'AbortError') {message('Generation cancelled.'); return;}
    if(error.code==='generation_limit'){
      const {createGenerationLimitDialog}=await import('/static/allowance-ui.js');
      limitDialog??=createGenerationLimitDialog({onAdjust:()=>{$('generation-dialog').showModal();$('count').focus();}});
      limitDialog.show(error);return;
    }
    throw error;
  } finally {
    clearInterval(timer); clearTimeout(deadline); generationController = null;
    if (jobId && !terminal) {
      $('cancel-generation').disabled = true;
      $('generation-progress-detail').textContent = 'Stopping generation…';
      await api(`/api/study/jobs/${encodeURIComponent(jobId)}`, {method: 'DELETE', timeoutMs: 15000}).catch(() => {});
    }
    $('generation-progress').hidden = true; $('open-generation').setAttribute('aria-busy', 'false');
    dispatchEvent(new Event('mathpdf-allowance-changed'));
    generationActive = false; updateGenerationAvailability(); $('open-generation').textContent = 'Generate';
    if (!sets.get(activeSetId)?.data) renderPractice();
  }
}
async function persistSet(record,title=record.title) {
  if(!record.data)throw new Error('This study set has not finished loading.');
  const result=await api('/api/study-sets',{method:'POST',body:JSON.stringify({...record.data,title:title.trim()})});
  record.data=result;record.title=result.title;record.saved=true;
  renderSetTabs();if(record.id===activeSetId)renderPractice();
}
async function saveSet(event) {
  event.preventDefault(); const intent = saveIntent, record = sets.get(intent?.id); if (!record?.data) return;
  $('confirm-save').disabled = true;
  try {
    await persistSet(record,$('set-name').value);
    const close = intent.closeAfterSave && !intent.cancelled;
    if (saveIntent === intent && $('save-dialog').open) $('save-dialog').close();
    if (close) await removeSetTab(record.id);
    else {renderSetTabs(); if (record.id === activeSetId) renderPractice();}
    message('Study set saved.');
  } catch (error) {
    if (saveIntent === intent && $('save-dialog').open) {$('save-error').hidden = false; $('save-error').textContent = error.message;}
    else message(error.message, true);
  }
  finally {$('confirm-save').disabled = false;}
}
async function exportSet() {
  const record = sets.get(activeSetId); if (!record?.data) return;
  $('export-set').disabled = true; $('export-set').textContent = 'Exporting…'; message('Formatting your PDF…', false, 0);
  try {
    const response = await MathPDFSession.request('/api/study/export.pdf', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(record.data)});
    if (!response.ok) {
      const error = await response.json(); throw new Error(typeof error.detail === 'string' ? error.detail : 'This set could not be exported.');
    }
    const url = URL.createObjectURL(await response.blob());
    const link = el('a'); link.href = url; link.download = `${record.title.replaceAll('/', '-')}.pdf`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 30000);
    message('PDF ready.');
  } finally {$('export-set').disabled = !sets.get(activeSetId)?.data?.items.length; $('export-set').textContent = 'Download';}
}
async function showSaved() {
  $('saved-list').replaceChildren(el('p', 'field-note', 'Loading saved sets…')); $('saved-dialog').showModal();
  const saved = await api('/api/study-sets');
  $('saved-list').replaceChildren(...saved.map(meta => {
    const entry = button('', '', () => action(async () => {
      if (!sets.has(meta.id)) sets.set(meta.id, {...meta, saved: true, data: null, itemIndex: 0});
      $('saved-dialog').close(); await openSet(meta.id);
    }));
    entry.append(el('span', '', meta.title), el('small', '', `${meta.item_count} ${meta.mode === 'flashcards' ? 'cards' : 'problems'}`)); return entry;
  }));
  if (!saved.length) $('saved-list').append(el('p', 'field-note', 'No saved study sets yet.'));
}
function notifyPdfViewport(settled = false) {
  viewportSettled ||= settled;
  cancelAnimationFrame(viewportNotice);
  viewportNotice = requestAnimationFrame(() => {
    views.get(activeDocumentId)?.querySelector('iframe')?.contentWindow.postMessage({type: 'pdf-viewport', settled: viewportSettled}, location.origin);
    viewportSettled = false;
  });
}
for (const container of [$('document-tabs'), $('set-tabs'), $('item-tabs')]) wireTabs(container);
function chooseFiles() {
  ($('generation-dialog').open ? $('generation-dialog') : document.body).append($('file-input'));
  $('file-input').click();
}
$('add-files').addEventListener('click', chooseFiles);
$('upload-pdf').addEventListener('click', chooseFiles);
$('open-files').addEventListener('click', () => action(showFiles));
$('add-context').addEventListener('click', chooseFiles);
$('file-input').addEventListener('change', () => {const files = [...$('file-input').files]; $('file-input').value = ''; action(() => uploadFiles(files));});
$('page-form').addEventListener('submit', event => {event.preventDefault(); action(() => jumpPage(Number($('page').value))); $('page').blur();});
$('previous-page').addEventListener('click', () => action(() => jumpPage(readState(activeDocumentId).page - 1)));
$('next-page').addEventListener('click', () => action(() => jumpPage(readState(activeDocumentId).page + 1)));
$('zoom').addEventListener('change', () => {
  readState(activeDocumentId).zoom = $('zoom').value;
  preference(`reading-${activeDocumentId}`, JSON.stringify(readState(activeDocumentId)));
  views.get(activeDocumentId)?.querySelector('iframe')?.contentWindow.postMessage({type: 'pdf-zoom', zoom: $('zoom').value}, location.origin);
});
$('open-generation').addEventListener('click', () => action(openGeneration));
$('source-document').addEventListener('change', sourceChanged);
$('source-scope').addEventListener('change', () => {updateRangeDisabled(); updateGenerationSummary();});
for (const input of [$('source-from'), $('source-to'), $('mode'), $('count')]) input.addEventListener('input', updateGenerationSummary);
const difficultyDescriptions = ['Recall core facts and meanings.', 'Explain conditions and apply one idea.', 'Apply concepts with a few reasoning steps.', 'Connect ideas and justify careful distinctions.', 'Explore deeper reasoning, proofs and edge cases.'];
for (const input of document.querySelectorAll('input[name=difficulty]')) input.addEventListener('change', () => {
  $('difficulty-description').textContent = `${difficultyDescriptions[Number(input.value)-1]} Items become harder within this level.`;
  updateGenerationSummary();
});
$('generate-form').addEventListener('submit', event => action(() => generate(event)));
$('cancel-generation').addEventListener('click', () => generationController?.abort());
$('save-set').addEventListener('click', () => openSaveDialog(activeSetId));
$('save-dialog').addEventListener('cancel', () => {if (saveIntent) saveIntent.cancelled = true;});
$('save-form').addEventListener('submit', saveSet);
$('export-set').addEventListener('click', () => action(exportSet));
$('open-saved').addEventListener('click', () => action(showSaved));
function pendingWork() {
  return [...(notes?.dirtyDocuments() || []).map(id=>`${documents.get(id)?.filename || 'PDF'} · Unsaved notes`),
    ...[...pendingUploads.values()].map(file=>`${file.filename} · Not uploaded`),
    ...[...sets.values()].filter(record=>!record.saved).map(record=>`${record.title} · Unsaved study set`),
    ...(generationActive || generationPreparing?['Study generation in progress']:[])];
}
async function savePendingWork() {
  if(generationActive || generationPreparing)throw new Error('Wait for generation to finish or cancel it, then save and leave.');
  for(const id of [...pendingUploads.keys()]) {
    await saveUpload(id);
    if(pendingUploads.has(id))throw new Error(pendingUploads.get(id).error || 'The file has not finished uploading.');
  }
  await notes.saveAll();
  for(const record of sets.values())if(!record.saved)await persistSet(record);
}
document.querySelectorAll('.close-dialog').forEach(control => control.addEventListener('click', () => {
  if (control.dataset.dialog === 'save-dialog' && saveIntent) saveIntent.cancelled = true;
  $(control.dataset.dialog).close();
}));
action(async () => {
  const user = await MathPDFSession.ready;
  ({wireFlashcard}=await import('/static/card-interaction.js'));
  preferencePrefix = `mathpdf-${user.id}-`;
  const {createReviewUI}=await import('/static/review-ui.js');
  reviewUI=createReviewUI({api,userId:user.id,onChange:record=>{if(record.id===activeSetId)renderPractice();},select:(record,index)=>{record.itemIndex=index;record.flipped=false;if(record.id===activeSetId)renderPractice();},onError:text=>message(text,true)});
  const {createWorkspaceLayout} = await import('/static/workspace-layout.js');
  layout = createWorkspaceLayout({preference, onViewport: notifyPdfViewport});
  const {createAnnotationToolbar}=await import('/static/annotation-toolbar.js');
  notes=createAnnotationToolbar({activeDocument:()=>documents.get(activeDocumentId),
    documentFor:id=>documents.get(id),
    frameFor:id=>views.get(id)?.querySelector('iframe'),notifyViewport:notifyPdfViewport,
    report:text=>message(text,true,10000),onChange:()=>renderDocumentTabs(),
    onOpenCopy:async doc=>{documents.set(doc.id,doc);await openDocument(doc.id);},
    onSaved:(previous,doc)=>{
      documents.set(doc.id,doc);
      if (previous!==doc.id) {
        const view=views.get(previous);views.delete(previous);
        if (view) {view.id=`document-view-${doc.id}`;view.querySelector('iframe').title=doc.filename;views.set(doc.id,view);}
        if (!openDocumentIds.includes(doc.id)) openDocumentIds.splice(openDocumentIds.indexOf(previous)+1,0,doc.id);
        reading.set(doc.id,{...readState(previous)});
        if (activeDocumentId===previous) {activeDocumentId=doc.id;preference('active-file',doc.id);}
      }
      renderDocumentTabs();updateDocumentToolbar();message('PDF notes saved.');
    }});
  const {createLeaveGuard}=await import('/static/leave-guard.js');
  const leave=createLeaveGuard({pending:pendingWork,save:savePendingWork});
  MathPDFSession.setLeaveGuard(()=>leave.confirm(),()=>leave.reset());
  document.querySelector('a.brand').addEventListener('click',event=>{
    if(event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;
    event.preventDefault();action(async()=>{if(await leave.confirm())location.assign('/');});
  });
  const [loadedDocuments, configuration, saved] = await Promise.all([api('/api/documents'), api('/api/generation/config'), api('/api/study-sets')]);
  config = configuration; $('count').max = config.max_items; loadedDocuments.forEach(doc => documents.set(doc.id, doc));
  updateGenerationAvailability();
  let storedFiles;
  try {storedFiles = JSON.parse(preference('open-files'));} catch {}
  openDocumentIds = Array.isArray(storedFiles) ? [...new Set(storedFiles.filter(id => documents.has(id)))] : [...documents.keys()];
  const selection = new URLSearchParams(location.search);
  const selectedDocument = selection.get('document');
  if (selectedDocument && documents.has(selectedDocument) && !openDocumentIds.includes(selectedDocument)) openDocumentIds.push(selectedDocument);
  const initial = documents.has(selectedDocument) ? selectedDocument : openDocumentIds.includes(preference('active-file')) ? preference('active-file') : openDocumentIds[0];
  if (initial) await openDocument(initial); else showEmptyDocuments();
  let storedSets;
  try {storedSets = JSON.parse(preference('open-study-sets'));} catch {}
  const savedById = new Map(saved.map(meta => [meta.id, meta]));
  const openSaved = Array.isArray(storedSets) ? [...new Set(storedSets)].filter(id => savedById.has(id)) : saved.map(meta => meta.id);
  const requestedSet = selection.get('set');
  if (savedById.has(requestedSet) && !openSaved.includes(requestedSet)) openSaved.push(requestedSet);
  for (const id of openSaved) sets.set(id, {...savedById.get(id), saved: true, data: null, itemIndex: 0});
  const selectedSet = sets.has(requestedSet) ? requestedSet : sets.has(preference('active-study-set')) ? preference('active-study-set') : openSaved[0];
  if (selectedSet) await openSet(selectedSet); else {renderSetTabs(); renderPractice();}
  if (requestedSet && sets.get(requestedSet)?.data) {
    const source = sets.get(requestedSet).data.document;
    await openDocument(source.id, preference(`reading-${source.id}`) ? readState(source.id).page : sets.get(requestedSet).data.pages[0]);
  }
  initializing = false;
  if (!config.configured) message('Generation is currently unavailable. You can still read files and open saved sets.', true, 10000);
});

MathPDFSession.setContextProvider?.(async()=>({workspace:{active_document:documents.get(activeDocumentId)||null,reading:activeDocumentId?readState(activeDocumentId):null,
  study_set:sets.get(activeSetId)?.data||null,item_index:sets.get(activeSetId)?.itemIndex??null,
  generation_selection:lastGenerationSelection||null,generation_running:generationActive,
  unsaved_notes:await notes?.diagnosticContext?.()||[]}}));
MathPDFSession.setUIContextProvider?.(()=>({document_id:activeDocumentId,study_set_id:activeSetId,file_name:documents.get(activeDocumentId)?.filename,page:activeDocumentId?readState(activeDocumentId).page:undefined,item_index:sets.get(activeSetId)?.itemIndex}));

let nameDialog;
async function renameActive(kind){
  const record=kind==='documents'?documents.get(activeDocumentId):sets.get(activeSetId);if(!record)return;
  nameDialog??=(await import('/static/rename-ui.js')).createRenameDialog();
  const previous=kind==='documents'?record.filename:record.title;
  nameDialog.open({name:previous,kind,save:async name=>{
    if(kind==='study-sets'&&!record.saved){
      name=name.trim();if(!name)throw new Error('Enter a study set name.');record.title=record.data.title=name;
    }else{
      const updated=await api(`/api/library/items/${kind}/${record.id}/name`,{method:'PATCH',body:JSON.stringify({name,expected_name:previous})});
      if(kind==='documents'){documents.set(updated.id,updated);const frame=views.get(updated.id)?.querySelector('iframe');if(frame)frame.title=updated.filename;}
      else{record.title=updated.title;record.data=updated;}
    }
    renderDocumentTabs();updateDocumentToolbar();renderSetTabs();renderPractice();message('Name saved.');
  }});
}
$('rename-file').addEventListener('click',()=>action(()=>renameActive('documents')));
$('rename-set').addEventListener('click',()=>action(()=>renameActive('study-sets')));
