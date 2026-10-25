/* Private, bounded caches of derived source previews. Never cache API responses. */
const REVISION = 'pdfjs-6.4-visual-v1', DB_NAME = 'mathpdf-visual-cache';
const blockedUsers = new Set(), blockedFiles = new Set();
let database, channel;
try {
  channel = new BroadcastChannel('mathpdf-visual-cache');
  channel.onmessage = event => invalidate(event.data);
} catch {}
function invalidate(event) {
  if (!event || typeof event.userId !== 'string') return;
  if (event.fileId) blockedFiles.add(`${event.userId}:${event.fileId}`);
  else blockedUsers.add(event.userId);
}
function openDatabase() {
  if (!database) database = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore('entries', {keyPath: 'key'});
    request.onsuccess = () => {request.result.onversionchange = () => request.result.close(); resolve(request.result);};
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('Cache unavailable'));
  }).catch(() => null);
  return database;
}
async function transaction(operation) {
  try {
    const db = await openDatabase(); if (!db) return null;
    return await new Promise((resolve, reject) => {
      const tx = db.transaction('entries', 'readwrite'), store = tx.objectStore('entries');
      let value;
      operation(store, result => {value = result;});
      tx.oncomplete = () => resolve(value);
      tx.onerror = tx.onabort = () => reject(tx.error);
    });
  } catch {return null;} // Private browsing, eviction and quota limits are cache misses.
}
function removeMatching(userId, fileId) {
  return transaction(store => {
    const request = store.openCursor();
    request.onsuccess = () => {
      const cursor = request.result; if (!cursor) return;
      if (cursor.value.userId === userId && (!fileId || cursor.value.fileId === fileId)) cursor.delete();
      cursor.continue();
    };
  });
}
export async function clearVisualCache(userId, fileId) {
  const event = {userId, fileId}; invalidate(event); channel?.postMessage(event);
  await removeMatching(userId, fileId);
}
export function createVisualCache(userId) {
  const allowed = file => !blockedUsers.has(userId) && !blockedFiles.has(`${userId}:${file.id}`);
  const key = (file, kind, page) => `${REVISION}:${userId}:${kind}:${file.id}:${file.sha256}:${page}`;
  return {
    async get(file, kind = 'preview', page = 1) {
      if (!allowed(file)) return null;
      return transaction((store, done) => {
        const request = store.get(key(file, kind, page));
        request.onsuccess = () => {
          const entry = request.result;
          if (entry && allowed(file)) {entry.used = Date.now(); store.put(entry); done(entry);}
        };
      });
    },
    async pages(file) {
      if (!allowed(file)) return [];
      return await transaction((store, done) => {
        const request = store.getAll(); request.onsuccess = () => done(request.result.filter(entry =>
          entry.userId === userId && entry.fileId === file.id && entry.hash === file.sha256 &&
          entry.revision === REVISION && entry.kind === 'page'));
      }) || [];
    },
    async put(file, kind, page, value) {
      if (!allowed(file)) return;
      const size = value.blob?.size || (value.text?.length || 0) * 2;
      if (size > 6 * 1024 * 1024) return;
      await transaction(store => {
        if (!allowed(file)) return;
        const entry = {...value, key: key(file, kind, page), revision: REVISION, userId,
          fileId: file.id, hash: file.sha256, kind, page, size, used: Date.now()};
        store.put(entry);
        const request = store.getAll();
        request.onsuccess = () => {
          const entries = request.result.filter(item => item.userId === userId && item.kind === kind)
            .sort((a, b) => b.used - a.used || (a.key === entry.key ? -1 : 1));
          let bytes = 0;
          for (const [index, item] of entries.entries()) {
            bytes += item.size;
            if (index >= (kind === 'page' ? 10 : 150) || bytes > 30 * 1024 * 1024) store.delete(item.key);
          }
        };
      });
    },
  };
}

export function canvasBlob(canvas) {
  return new Promise(resolve => {
    try {canvas.toBlob(resolve, 'image/webp', .86);} catch {resolve(null);}
  });
}
