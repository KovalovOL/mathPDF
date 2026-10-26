/* Account-owned files and saved sets. Names are always inserted as text. */
const home = id => document.getElementById(id);
let uploading = false;
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
function chooseFiles() {if (!uploading) home('library-file-input').click();}
function deleteButton(kind, id, title) {
  const control = node('button', 'small delete-action', 'Delete'); control.type = 'button';
  control.setAttribute('aria-label', `Delete ${title}`);
  control.addEventListener('click', () => confirmDeletion(kind, id).catch(showError)); return control;
}
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
async function loadLibrary() {
  const [files, sets, previewRenderer] = await Promise.all([MathPDFSession.api('/api/documents'), MathPDFSession.api('/api/study-sets'), previewModule]);
  previews?.destroy();
  previews = previewRenderer?.createFilePreviews({request: MathPDFSession.request, userId: MathPDFSession.user.id,
    onAuthFailure: () => MathPDFSession.api('/api/me').catch(() => {})});
  home('files-count').textContent = String(files.length); home('sets-count').textContent = String(sets.length);
  home('library-files').classList.toggle('file-library', files.length > 0);
  home('library-files').replaceChildren(...files.map(file => {
    const entry = node('article', 'file-card');
    if (file.original_document_id) entry.classList.add('annotated-file');
    const link = node('a', 'file-card-link'); link.href = `/workspace?${new URLSearchParams({document: file.id})}`;
    const preview = node('div', 'file-preview', previews ? 'Loading preview…' : 'Preview unavailable');
    const details = node('div', 'file-card-details');
    details.append(node('span', 'library-item-title', file.filename), node('span', 'library-item-meta', fileMetadata(file)));
    if (file.original_document_id) {
      details.prepend(node('span','edited-copy-label','Edited copy'));
      const original=files.find(item=>item.id===file.original_document_id);
      if (original) details.append(node('span','library-item-meta',`From ${original.filename}`));
    }
    link.append(preview, details); entry.append(link);
    const footer = node('div', 'file-card-footer');
    const download = node('a', 'library-download', 'Download');
    download.href = `/api/documents/${encodeURIComponent(file.id)}/file?download=true`;
    download.setAttribute('aria-label', `Download ${file.filename}`);
    footer.append(download, deleteButton('documents', file.id, file.filename)); entry.append(footer);
    previews?.observe(preview, file); return entry;
  }));
  if (!files.length) {
    const empty = node('div', 'library-empty');
    const upload = node('button', '', 'Upload PDF'); upload.type = 'button'; upload.addEventListener('click', chooseFiles);
    empty.append(node('p', '', 'Upload a PDF to start studying.'), upload); home('library-files').append(empty);
  }
  home('library-sets').replaceChildren(...sets.map(set => {
    const kind = set.mode === 'flashcards' ? (set.item_count === 1 ? 'flashcard' : 'flashcards') : (set.item_count === 1 ? 'problem' : 'problems');
    const date = new Date(set.updated_at).toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});
    const entry = row(set.title, `${set.item_count} ${kind} · Saved ${date}`, `/workspace?${new URLSearchParams({set: set.id})}`);
    entry.append(deleteButton('study-sets', set.id, set.title)); return entry;
  }));
  if (!sets.length) home('library-sets').append(node('p', 'library-empty', 'Study sets you save will appear here.'));
}
function showError(error) {home('library-error').textContent = error.message; home('library-error').hidden = false;}
home('upload-files').addEventListener('click', chooseFiles);
home('library-file-input').addEventListener('change', async () => {
  const files = [...home('library-file-input').files]; home('library-file-input').value = '';
  if (!files.length || uploading) return;
  uploading = true; home('upload-files').disabled = true; home('library-error').hidden = true;
  home('upload-status').hidden = false;
  let completed = 0; const failures = [];
  try {
    for (const file of files) {
      home('upload-status').textContent = `Uploading ${file.name}…`;
      try {
        if (file.size > 25 * 1024 * 1024) throw new Error('The file exceeds 25 MB.');
        const body = new FormData(); body.append('file', file);
        await MathPDFSession.api('/api/documents', {method: 'POST', body}); completed++;
      } catch (error) {failures.push(`${file.name}: ${error.message}`);}
    }
    await loadLibrary();
    home('upload-status').textContent = `${completed} ${completed === 1 ? 'file' : 'files'} uploaded.`;
    if (failures.length) throw new Error(failures.join('\n'));
  } catch (error) {showError(error);}
  finally {uploading = false; home('upload-files').disabled = false;}
});
addEventListener('beforeunload', event => {if (uploading) {event.preventDefault(); event.returnValue = '';}});
addEventListener('pagehide', () => previews?.destroy());
MathPDFSession.ready.then(async user => {
  for (const id of ['files-section', 'sets-section']) {
    const section = home(id), key = `mathpdf-${user.id}-${id}-open`;
    try {section.open = localStorage.getItem(key) !== 'false';} catch {}
    section.addEventListener('toggle', () => {try {localStorage.setItem(key, String(section.open));} catch {}});
  }
  await loadLibrary(); home('upload-files').disabled = false;
}).catch(showError);
