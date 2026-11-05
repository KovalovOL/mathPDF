import { readFile, writeFile, mkdir, cp, readdir, rm } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "dist");
const mapping = JSON.parse(
  await readFile(path.join(root, "asset-map.json"), "utf8"),
);
const digest = (data) => createHash("sha256").update(data).digest("hex");

async function filesAt(directory, prefix = "") {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relative = path.posix.join(prefix, entry.name);
    if (entry.isDirectory())
      result.push(
        ...(await filesAt(path.join(directory, entry.name), relative)),
      );
    else result.push(relative);
  }
  return result;
}

async function copyAssets() {
  await rm(out, { recursive: true, force: true });
  await mkdir(out, { recursive: true });
  for (const [name, source] of Object.entries(mapping)) {
    await cp(path.join(root, "app", source), path.join(out, name), {
      recursive: true,
    });
  }
}

async function build() {
  await copyAssets();
  const files = await filesAt(out);
  const hashes = {};
  for (const file of files.filter((name) => name !== "manifest.json")) {
    hashes[file] = digest(await readFile(path.join(out, file)));
  }
  const build = digest(JSON.stringify(hashes)).slice(0, 12);
  for (const file of files.filter((name) => name.endsWith(".html"))) {
    let html = await readFile(path.join(out, file), "utf8");
    html = html.replace(
      "<head>",
      `<head>\n<meta name="mathpdf-build" content="${build}">`,
    );
    html = html.replace(
      /((?:src|href)=["'])(\/static\/([^"'?]+)\.(?:js|mjs|css))(["'])/g,
      (all, start, url, name, end) =>
        `${start}${url}?v=${hashes[url.slice(8)]?.slice(0, 12) || build}${end}`,
    );
    await writeFile(path.join(out, file), html);
    hashes[file] = digest(html);
  }
  await writeFile(
    path.join(out, "manifest.json"),
    JSON.stringify({ version: 1, build, assets: hashes }),
  );
  console.log(`Frontend ${build}: ${Object.keys(hashes).length} assets`);
}

await build();
