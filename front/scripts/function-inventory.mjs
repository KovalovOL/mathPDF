/** AST spans for application code, tooling and executable browser fixtures. */
import { parse } from "acorn";
import { format } from "prettier";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

async function filesAt(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (
      ["vendor", "node_modules", "dist", ".venv", "__pycache__"].includes(
        entry.name,
      )
    )
      continue;
    const name = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await filesAt(name)));
    else if (/\.(?:m?js|cjs|html)$/.test(name)) files.push(name);
  }
  return files;
}
function functions(node, file, output, offset = 0) {
  if (!node || typeof node !== "object") return;
  if (
    [
      "FunctionDeclaration",
      "FunctionExpression",
      "ArrowFunctionExpression",
    ].includes(node.type)
  ) {
    const lines = node.loc.end.line - node.loc.start.line + 1;
    if (lines > 50)
      output.push({
        file,
        line: offset + node.loc.start.line,
        name: node.id?.name || "<callback>",
        lines,
      });
  }
  for (const [key, value] of Object.entries(node)) {
    if (key === "loc") continue;
    if (Array.isArray(value))
      value.forEach((item) => functions(item, file, output, offset));
    else if (value && typeof value === "object")
      functions(value, file, output, offset);
  }
}
function inspect(source, file, output, offset = 0) {
  const tree = parse(source, {
    ecmaVersion: "latest",
    sourceType: file.endsWith(".cjs") ? "script" : "module",
    locations: true,
  });
  functions(tree, file, output, offset);
}
function html(source, file, output) {
  let index = 0;
  for (const match of source.matchAll(
    /<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi,
  )) {
    if (/\bsrc\s*=|application\/(?:json|ld\+json)/i.test(match[1])) continue;
    const offset =
      source.slice(0, match.index + match[0].indexOf(">") + 1).split("\n")
        .length - 1;
    inspect(match[2], `${file}:script-${++index}`, output, offset);
  }
}
async function main() {
  const args = process.argv.slice(2),
    snippetIndex = args.indexOf("--snippets");
  const snippetFile =
    snippetIndex >= 0 ? args.splice(snippetIndex, 2)[1] : null;
  const roots = args.length
    ? args
    : ["front/app", "front/scripts", "front/tests/fixtures"];
  const output = [];
  for (const root of roots)
    for (const file of await filesAt(root)) {
      const source = await readFile(file, "utf8");
      file.endsWith(".html")
        ? html(source, file, output)
        : inspect(source, file, output);
    }
  if (snippetFile)
    for (const snippet of JSON.parse(await readFile(snippetFile, "utf8"))) {
      const readable = await format(snippet.source, { parser: "babel" });
      inspect(
        readable,
        `${snippet.file}:embedded-JavaScript`,
        output,
        snippet.line - 1,
      );
    }
  console.log(JSON.stringify(output, null, 2));
  process.exitCode = output.length ? 1 : 0;
}
await main();
