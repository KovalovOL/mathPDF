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
  async function remove(file, kind = 'preview', page = 1, expected) {
    await transaction(store => {
      const request = store.get(key(file, kind, page));
      request.onsuccess = () => {
        const entry = request.result;
        if (entry && (!expected || (entry.written ? entry.written === expected.written : entry.used === expected.used))) store.delete(entry.key);
      };
    });
  }
  async function restore(file, entry) {
    if (!entry || !allowed(file)) return null;
    if (entry.blob) {
      // Never write an IndexedDB-backed Blob back to IndexedDB (WebKit 240216).
      try {
        entry = {...entry, bytes: await imageBytes(entry.blob), mediaType: entry.blob.type};
        delete entry.blob;
        await transaction(store => {if (allowed(file)) store.put(entry);});
      } catch {await remove(file, entry.kind, entry.page, entry); return null;}
    }
    return allowed(file) ? entry : null;
  }
  return {
    remove,
    async get(file, kind = 'preview', page = 1) {
      if (!allowed(file)) return null;
      const entry = await transaction((store, done) => {
        const request = store.get(key(file, kind, page));
        request.onsuccess = () => {
          const entry = request.result;
          if (entry && allowed(file)) {
            if (!entry.blob) {entry.used = Date.now(); store.put(entry);}
            done(entry);
          }
        };
      });
      return restore(file, entry);
    },
    async pages(file) {
      if (!allowed(file)) return [];
      const entries = await transaction((store, done) => {
        const request = store.getAll(); request.onsuccess = () => done(request.result.filter(entry =>
          entry.userId === userId && entry.fileId === file.id && entry.hash === file.sha256 &&
          entry.revision === REVISION && entry.kind === 'page'));
      }) || [];
      return (await Promise.all(entries.map(entry => restore(file, entry)))).filter(Boolean);
    },
    async put(file, kind, page, value) {
      if (!allowed(file)) return;
      let stored = {...value};
      if (value.blob) {
        try {stored.bytes = await imageBytes(value.blob); stored.mediaType = value.blob.type; delete stored.blob;}
        catch {return;}
      }
      const size = stored.bytes?.byteLength || (stored.text?.length || 0) * 2;
      if (size > 6 * 1024 * 1024) return;
      await transaction(store => {
        if (!allowed(file)) return;
        const entry = {...stored, key: key(file, kind, page), revision: REVISION, userId,
          fileId: file.id, hash: file.sha256, kind, page, size, used: Date.now(), written: `${Date.now()}:${Math.random()}`};
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

async function imageBytes(blob) {
  let timer;
  try {
    return await Promise.race([blob.arrayBuffer(), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('Cached image unavailable')), 1500);
    })]);
  } finally {clearTimeout(timer);}
}

export async function cachedImage(entry, alt) {
  let url, timer;
  try {
    const image = new Image();
    const blob = entry.bytes ? new Blob([entry.bytes], {type: entry.mediaType}) : entry.blob;
    url = URL.createObjectURL(blob); image.alt = alt; image.src = url;
    await Promise.race([image.decode(), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('Cached image unavailable')), 1500);
    })]);
    return {image, url};
  } catch {if (url) URL.revokeObjectURL(url); return null;}
  finally {clearTimeout(timer);}
}

export function canvasBlob(canvas) {
  return new Promise(resolve => {
    try {canvas.toBlob(resolve, 'image/webp', .86);} catch {resolve(null);}
  });
}
