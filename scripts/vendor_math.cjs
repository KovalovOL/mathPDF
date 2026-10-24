/* Keep frontend runtime assets local; Python deployment does not need Node. */
const fs = require('node:fs');
const path = require('node:path');
const source = path.dirname(require.resolve('katex/package.json'));
const destination = path.resolve(__dirname, '../formula_lab/static/vendor/katex');
fs.mkdirSync(destination, {recursive: true});
for (const file of ['katex.min.js', 'katex.min.css']) {
  fs.copyFileSync(path.join(source, 'dist', file), path.join(destination, file));
}
fs.cpSync(path.join(source, 'dist/fonts'), path.join(destination, 'fonts'), {recursive: true});
fs.copyFileSync(path.join(source, 'LICENSE'), path.join(destination, 'LICENSE'));
const pdfSource = path.dirname(require.resolve('pdfjs-dist/package.json'));
const pdfDestination = path.resolve(__dirname, '../formula_lab/static/vendor/pdfjs');
fs.mkdirSync(pdfDestination, {recursive: true});
for (const file of ['pdf.mjs', 'pdf.worker.mjs']) {
  fs.copyFileSync(path.join(pdfSource, 'legacy/build', file), path.join(pdfDestination, file));
}
for (const directory of ['cmaps', 'standard_fonts', 'wasm']) {
  fs.cpSync(path.join(pdfSource, directory), path.join(pdfDestination, directory), {recursive: true});
}
fs.copyFileSync(path.join(pdfSource, 'LICENSE'), path.join(pdfDestination, 'LICENSE'));
console.log('Local KaTeX and PDF.js assets updated.');
