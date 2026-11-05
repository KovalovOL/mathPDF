async () => {
  const { createVisualCache } = await import("/static/visual-cache.js");
  const entry = await createVisualCache("viewer-owner").get(
    { id: "viewer-file", sha256: "original" },
    "page",
    1,
  );
  return entry?.bytes?.byteLength > 100;
};
