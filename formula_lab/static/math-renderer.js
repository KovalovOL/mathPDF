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
    container.classList.remove('math-error');
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
      container.classList.add('math-error');
      container.append(element('span', '', `Cannot render this formula: ${error.message}`));
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
      if (block.source.line_start != null) {
        const start = block.source.line_start, end = block.source.line_end;
        caption.append(document.createTextNode(` · ${start === end ? `line ${start}` : `lines ${start}–${end}`} (model-reported)`));
      }
      if (block.source.quote) caption.title = block.source.quote;
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

  function renderText(container, text) {
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
