/* Reusable structured LLM-output renderer. Model text is never inserted as HTML. */
(() => {
  let editorId = 0;
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderMath(container, latex, display = true) {
    container.replaceChildren();
    container.classList.remove('math-error', 'math-fallback');
    delete container.dataset.mathError;
    try {
      if (typeof latex !== 'string' || !latex.trim()) throw new Error('Enter a formula.');
      if (latex.length > 5000) throw new Error('Formula exceeds 5,000 characters.');
      if (!window.katex) throw new Error('The math renderer could not be loaded.');
      window.katex.render(latex, container, {
        displayMode: display, output: 'htmlAndMathml',
        throwOnError: true, trust: false, strict: 'error',
        maxExpand: 1000, maxSize: 20,
      });
      return true;
    } catch (error) {
      container.replaceChildren();
      container.classList.add('math-fallback');
      container.dataset.mathError = error.message;
      container.append(element('span', 'raw-formula', typeof latex === 'string' ? latex : ''));
      return false;
    }
  }

  function mathBlock(block, {onSource, editable = true, sourceUrl, sourceLabel, linkSources = true} = {}) {
    const figure = element('figure', 'math-block');
    const output = element('div', 'math-output');
    renderMath(output, block.latex, block.display);
    figure.append(output);
    if (block.source) {
      const caption = element('figcaption', 'citation');
      const label = sourceLabel ? sourceLabel(block.source) : `Page ${block.source.page}`;
      const link = element(linkSources ? 'a' : 'span', '', label);
      if (linkSources) {
        link.href = sourceUrl ? sourceUrl(block.source) : `/source.pdf#page=${block.source.page}`;
        link.target = '_blank'; link.rel = 'noopener';
      }
      if (linkSources && onSource) link.addEventListener('click', event => {
        event.preventDefault(); onSource(block.source);
      });
      caption.append(link);
      figure.append(caption);
    }
    if (!editable) return figure;
    const details = element('details', 'math-editor');
    details.append(element('summary', '', 'Edit formula'));
    const label = element('label', '', 'TeX');
    const input = element('textarea');
    input.id = `math-editor-${++editorId}`;
    input.value = block.latex; input.rows = 3; input.maxLength = 5000;
    input.spellcheck = false; label.htmlFor = input.id;
    const preview = element('button', 'secondary', 'Preview change');
    preview.type = 'button';
    const edited = element('div', 'edited-formula'); edited.hidden = true;
    preview.addEventListener('click', () => {
      edited.hidden = false;
      edited.replaceChildren(element('p', 'field-note', 'Edited preview · original preserved'));
      const math = element('div', 'math-output');
      renderMath(math, input.value, block.display); edited.append(math);
    });
    details.append(label, input, preview, edited); figure.append(details);
    return figure;
  }

  function renderDelimitedText(container, text) {
    // Models sometimes put delimited inline TeX in prose. Parse only math
    // delimiters; every other character remains a DOM text node.
    const pattern = /\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]|\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$/g;
    let position = 0;
    for (const match of text.matchAll(pattern)) {
      container.append(document.createTextNode(text.slice(position, match.index)));
      const math = element('span', 'inline-math');
      const display = match[2] !== undefined || match[3] !== undefined;
      renderMath(math, match[1] ?? match[2] ?? match[3] ?? match[4], display);
      container.append(math); position = match.index + match[0].length;
    }
    container.append(document.createTextNode(text.slice(position)));
  }

  function renderText(container, text) {
    // Older sets sometimes contain a whole TeX expression on a prose list line.
    // Only recover clearly mathematical standalone lines; never typeset an English paragraph.
    if (['$', '\\(', '\\['].some(marker => text.includes(marker))) {
      renderDelimitedText(container, text); return;
    }
    const lines = text.split('\n');
    lines.forEach((line, index) => {
      if (index) container.append(document.createTextNode('\n'));
      const prefix = line.match(/^\s*(?:(?:\d+[.)]|[-*•])\s+)?/)[0];
      const expression = line.slice(prefix.length).trim();
      const withoutCommands = expression.replace(/\\[A-Za-z]+/g, '');
      const standalone = /\\[A-Za-z]+/.test(expression) &&
        /^(?:[\\\d+\-({\[]|[A-Za-z](?=[\s_^=<>]))/.test(expression) &&
        !/\b[A-Za-z]{3,}\b/.test(withoutCommands);
      if (standalone) {
        const math = element('span', 'inline-math');
        if (renderMath(math, expression, false)) {
          container.append(document.createTextNode(prefix), math); return;
        }
      }
      renderDelimitedText(container, line);
    });
  }

  function renderBlocks(container, blocks, options = {}) {
    container.replaceChildren();
    for (const block of blocks) {
      if (block.kind === 'text') {
        const paragraph = element('p', 'text-block'); renderText(paragraph, block.text); container.append(paragraph);
      }
      else if (block.kind === 'math') container.append(mathBlock(block, options));
      else container.append(element('p', 'error', 'Unsupported content block.'));
    }
  }
  window.MathPDF = {renderMath, renderBlocks, mathBlock};
})();
