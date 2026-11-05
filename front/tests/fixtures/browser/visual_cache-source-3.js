class CacheMigrationScenario {
  #cache;
  #file = { id: "image-file", sha256: "original" };
  #blob;
  #db;
  #stored;
  #legacy;
  #cachedImage;
  async run() {
    await this.#prepare();
    const result = {
      ...(await this.#legacyMigration()),
      ...(await this.#decodeRecovery()),
      fallbackWorks: await this.#fallback(),
    };
    this.#db.close();
    return result;
  }
  async #prepare() {
    const { createVisualCache, cachedImage, canvasBlob } =
      await import("/cache.js");
    this.#cachedImage = cachedImage;
    this.#cache = createVisualCache("image-owner");
    const canvas = document.createElement("canvas");
    canvas.width = 20;
    canvas.height = 30;
    canvas.getContext("2d").fillRect(0, 0, 20, 30);
    this.#blob = await canvasBlob(canvas);
    await this.#cache.put(this.#file, "preview", 1, { blob: this.#blob });
    this.#db = await new Promise((resolve) => {
      const request = indexedDB.open("mathpdf-visual-cache", 1);
      request.onsuccess = () => resolve(request.result);
    });
    this.#stored = (await this.#raw((store) => store.getAll()))[0];
  }
  #raw(operation) {
    return new Promise((resolve) => {
      const tx = this.#db.transaction("entries", "readwrite"),
        store = tx.objectStore("entries");
      let value;
      const request = operation(store);
      request.onsuccess = () => {
        value = request.result;
      };
      tx.oncomplete = () => resolve(value);
    });
  }
  async #legacyMigration() {
    const stored = this.#stored;
    const byteStorage = stored.bytes instanceof ArrayBuffer && !stored.blob;
    this.#legacy = {
      ...stored,
      blob: new Blob([stored.bytes], { type: stored.mediaType }),
    };
    delete this.#legacy.bytes;
    delete this.#legacy.written;
    await this.#raw((store) => store.put(this.#legacy));
    const restored = await this.#cache.get(this.#file),
      image = await this.#cachedImage(restored, "Legacy preview");
    const migrated = await this.#raw((store) => store.get(stored.key));
    const legacyReadable =
      image?.image.naturalWidth === 20 &&
      image.image.naturalHeight === 30 &&
      !migrated.blob &&
      migrated.bytes instanceof ArrayBuffer;
    if (image) URL.revokeObjectURL(image.url);
    await this.#raw((store) =>
      store.put({ ...this.#legacy, blob: new Blob(["unreadable-image"]) }),
    );
    const original = Blob.prototype.arrayBuffer;
    Blob.prototype.arrayBuffer = function () {
      return this.size === 16
        ? Promise.reject(new Error("Unavailable persisted Blob"))
        : original.call(this);
    };
    const unreadable = await this.#cache.get(this.#file);
    Blob.prototype.arrayBuffer = original;
    const badRemoved = !(await this.#raw((store) => store.get(stored.key)));
    return { byteStorage, legacyReadable, unreadable, badRemoved };
  }
  async #decodeRecovery() {
    const cache = this.#cache,
      file = this.#file;
    await cache.put(file, "preview", 1, {
      blob: new Blob(["not an image"], { type: "image/png" }),
    });
    const invalid = await cache.get(file),
      invalidImage = await this.#cachedImage(invalid, "Invalid");
    await cache.remove(file, "preview", 1, invalid);
    const decodeRemoved = !(await cache.get(file));
    await cache.put(file, "preview", 1, { blob: this.#blob });
    await cache.remove(file, "preview", 1, invalid);
    const replacement = await this.#cachedImage(
      await cache.get(file),
      "Replacement",
    );
    const replacementReadable = !!replacement;
    if (replacement) URL.revokeObjectURL(replacement.url);
    return { invalidImage, decodeRemoved, replacementReadable };
  }
  async #fallback() {
    const fallbackFile = {
      id: "fallback",
      sha256: "hash",
      media_type: "image/png",
      filename: "example.png",
    };
    await this.#cache.put(fallbackFile, "preview", 1, {
      blob: new Blob(["broken"], { type: "image/png" }),
    });
    const { createFilePreviews } = await import("/static/file-previews.js");
    const container = document.createElement("div");
    document.body.append(container);
    let downloads = 0;
    const renderer = createFilePreviews({
      userId: "image-owner",
      request: async () => {
        downloads++;
        return new Response(this.#blob);
      },
      onAuthFailure: () => {},
    });
    const ready = this.#waitForCanvas(container);
    renderer.observe(container, fallbackFile);
    await ready;
    const works =
      downloads === 1 &&
      !container.querySelector("img") &&
      !!container.querySelector("canvas");
    renderer.destroy();
    return works;
  }
  #waitForCanvas(container) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        observer.disconnect();
        reject(new Error("Preview fallback did not complete"));
      }, 5000);
      const observer = new MutationObserver(() => {
        if (container.querySelector("canvas")) {
          clearTimeout(timer);
          observer.disconnect();
          resolve();
        }
      });
      observer.observe(container, { childList: true });
    });
  }
}
new CacheMigrationScenario().run();
