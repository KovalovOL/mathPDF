async () => {
  Object.defineProperty(window, "indexedDB", {
    value: {
      open() {
        throw new Error("Storage disabled");
      },
    },
  });
  const { createVisualCache } = await import("/cache.js"),
    cache = createVisualCache("owner");
  const file = { id: "file", sha256: "hash" };
  await cache.put(file, "preview", 1, { text: "No storage" });
  return { entry: await cache.get(file), pages: await cache.pages(file) };
};
