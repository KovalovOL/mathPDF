async () => {
  const { createVisualCache, clearVisualCache } = await import("/cache.js");
  const file = { id: "file-one", sha256: "original" },
    cache = createVisualCache("owner-one");
  for (let page = 1; page <= 10; page++) {
    await cache.put(file, "page", page, {
      blob: new Blob(["page" + page]),
      ratio: 1.4,
    });
    await new Promise((resolve) => setTimeout(resolve, 2));
  }
  await cache.get(file, "page", 1);
  await new Promise((resolve) => setTimeout(resolve, 3));
  await cache.put(file, "page", 11, { blob: new Blob(["page11"]), ratio: 1.4 });
  const count = (await cache.pages(file)).length;
  const recent = !!(await cache.get(file, "page", 1)),
    oldest = !!(await cache.get(file, "page", 2));
  const other = await createVisualCache("owner-two").get(file, "page", 1);
  const changed = await cache.get({ ...file, sha256: "changed" }, "page", 1);
  await cache.put(file, "preview", 1, { text: "Cached excerpt" });
  const preview = (await cache.get(file)).text;
  await clearVisualCache("owner-one", file.id);
  await cache.put(file, "preview", 1, {
    text: "Late write must not restore a deleted file",
  });
  const deleted = await cache.get(file);
  const second = { id: "file-two", sha256: "original" };
  await cache.put(second, "preview", 1, { text: "Second file" });
  await clearVisualCache("owner-one");
  await cache.put(second, "preview", 1, { text: "Late write after sign-out" });
  return {
    count,
    recent,
    oldest,
    other,
    changed,
    preview,
    deleted,
    signedOut: await cache.get(second),
  };
};
