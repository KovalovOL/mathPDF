import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";

const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".json": "application/json",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".wasm": "application/wasm",
};

export class AssetServer {
  #directory;
  constructor(directory) {
    this.#directory = path.resolve(directory);
  }
  async handle(request, response) {
    try {
      const name = decodeURIComponent(
        new URL(request.url, "http://local").pathname,
      );
      const target = path.resolve(this.#directory, "." + name);
      if (
        !target.startsWith(this.#directory + path.sep) ||
        !["GET", "HEAD"].includes(request.method)
      ) {
        response.writeHead(404).end();
        return;
      }
      if (!(await stat(target)).isFile()) {
        response.writeHead(404).end();
        return;
      }
      response.writeHead(200, {
        "Content-Type":
          types[path.extname(target)] || "application/octet-stream",
        "X-Content-Type-Options": "nosniff",
      });
      response.end(
        request.method === "HEAD" ? undefined : await readFile(target),
      );
    } catch {
      response.writeHead(404).end();
    }
  }
  listen(port, host) {
    return createServer(this.handle.bind(this)).listen(port, host);
  }
}
