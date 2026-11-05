import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "node:http";
import http from "node:http";
import { AssetServer } from "./assets-server.mjs";

const directory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../dist",
);
const assets = new AssetServer(directory);
const backend = process.env.MATHPDF_BACKEND_URL || "http://127.0.0.1:8765";
const admin = process.env.MATHPDF_ADMIN_URL || "http://127.0.0.1:8767";
const reports = process.env.MATHPDF_REPORTS_URL || "http://127.0.0.1:8768";
const host = process.env.HOST || "127.0.0.1";

function proxy(request, response, target) {
  const headers = { ...request.headers, "x-mathpdf-original-uri": "" };
  const upstream = http.request(
    new URL(request.url, target),
    { method: request.method, headers },
    (result) => {
      response.writeHead(result.statusCode, result.headers);
      result.pipe(response);
    },
  );
  upstream.on("error", () =>
    response
      .writeHead(503, { "Content-Type": "application/json" })
      .end(JSON.stringify({ detail: "The backend is unavailable." })),
  );
  request.pipe(upstream);
}

async function authorize(request, response) {
  const check = await fetch(backend + "/internal/access", {
    headers: {
      cookie: request.headers.cookie || "",
      "x-mathpdf-original-uri": request.url,
    },
    redirect: "manual",
  });
  if (check.status === 401) {
    response
      .writeHead(303, {
        Location:
          check.headers.get("x-mathpdf-signin") ||
          "/login?next=" + encodeURIComponent(request.url),
        "Cache-Control": "no-store",
      })
      .end();
    return false;
  }
  if (!check.ok) {
    response
      .writeHead(
        check.headers.get("x-mathpdf-access-status") === "404"
          ? 404
          : check.status,
      )
      .end();
    return false;
  }
  return true;
}

async function handle(request, response) {
  try {
    const url = new URL(request.url, "http://local");
    if (url.pathname.startsWith("/internal/")) {
      response.writeHead(404).end();
      return;
    }
    if (url.pathname.startsWith("/api/admin/"))
      return proxy(request, response, admin);
    if (url.pathname.startsWith("/api/reports"))
      return proxy(request, response, reports);
    if (
      url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/auth/") ||
      url.pathname === "/login"
    )
      return proxy(request, response, backend);
    if (url.pathname === "/health") {
      response.writeHead(200).end("ok");
      return;
    }
    const pages = {
      "/": "home.html",
      "/workspace": "index.html",
      "/login": "login.html",
      "/admin": "admin.html",
    };
    const name =
      pages[url.pathname] ||
      (url.pathname.startsWith("/static/") ? url.pathname.slice(8) : null);
    if (!name) {
      response.writeHead(404).end();
      return;
    }
    const protectedPage = name.endsWith(".html") && name !== "login.html";
    if (protectedPage && !(await authorize(request, response))) return;
    request.url = "/" + name;
    response.setHeader(
      "Cache-Control",
      name.endsWith(".html") ? "no-store" : "no-cache",
    );
    response.setHeader("Referrer-Policy", "no-referrer");
    response.setHeader("X-Frame-Options", "SAMEORIGIN");
    await assets.handle(request, response);
  } catch {
    response.writeHead(503).end("The service is temporarily unavailable.");
  }
}

assets.listen(Number(process.env.ASSET_PORT || 8771), host);
if (!process.argv.includes("--assets-only"))
  createServer(handle).listen(Number(process.env.PORT || 8770), host);
console.log("Frontend ready");
