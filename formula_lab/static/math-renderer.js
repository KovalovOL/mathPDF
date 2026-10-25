/* Reusable structured LLM-output renderer. Model text is never inserted as HTML. */
(() => {
  let editorId = 0;
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  const booleanOperand = String.raw`(?:\\(?:neg|lnot)\s*)*(?:\\(?:bar|overline)\s*(?:\{[A-Za-z01]\}|[A-Za-z01])|[A-Za-z01])`;
  const beforeConjunction = new RegExp(String.raw`(?:^|[^A-Za-z])${booleanOperand}\s*$`);
  const afterConjunction = new RegExp(String.raw`^\s*${booleanOperand}(?![A-Za-z])\s*(?:&\s*)?\\(?:Leftrightarrow|leftrightarrow|iff|Rightarrow|Leftarrow|implies)(?![A-Za-z])`);
  const columnEnvironments = new Set(['aligned', 'alignedat', 'array', 'darray', 'matrix', 'pmatrix',
    'bmatrix', 'Bmatrix', 'vmatrix', 'Vmatrix', 'smallmatrix', 'cases', 'dcases', 'rcases', 'drcases', 'subarray', 'CD']);

  function literalAmpersands(latex, initialEnvironment = '') {
    // Column tabs belong to their environment's top level. A raw ampersand
    // elsewhere is a visible glyph, including inside a grouped overbar/text.
    const environments = [{name: initialEnvironment, depth: 0}];
    const tokens = /\\(begin|end)\{([A-Za-z]+\*?)\}|\\(?:[A-Za-z]+|[\s\S])|[{}&]/g;
    let depth = 0, position = 0, output = '';
    for (const match of latex.matchAll(tokens)) {
      const token = match[0];
      output += latex.slice(position, match.index);
      if (match[1] === 'begin') environments.push({name: match[2], depth});
      else if (match[1] === 'end') {
        if (environments.length > 1 && environments.at(-1).name === match[2]) environments.pop();
      } else if (token === '{') depth++;
      else if (token === '}') depth--;
      if (token === '&') {
        const environment = environments.at(-1);
        const name = environment.name.replace(/\*$/, '');
        const column = depth === environment.depth && columnEnvironments.has(name);
        // In a Boolean row, t&t <=> ... is conjunction, while &<=> and
        // conventional a&=b remain alignment. Never reinterpret table cells.
        const conjunction = /^(aligned|alignedat)$/.test(name)
          && beforeConjunction.test(latex.slice(0, match.index))
          && afterConjunction.test(latex.slice(match.index + 1));
        output += column && !conjunction ? '&' : '\\&';
      } else output += token;
      position = match.index + token.length;
    }
    return output + latex.slice(position);
  }

  function displayRows(latex, display) {
    if (!display || /\\begin\{/.test(latex)) return latex;
    const rows = []; let depth = 0, start = 0;
    for (let index = 0; index < latex.length; index++) {
      if (latex[index] === '\\') {
        if (latex[index + 1] === '\\' && depth === 0) {
          rows.push(latex.slice(start, index)); start = index + 2;
        }
        index++; // Escaped braces and nested row breaks remain untouched.
      } else if (latex[index] === '{') depth++;
      else if (latex[index] === '}') depth--;
      if (depth < 0) return latex;
    }
    if (!rows.length || depth !== 0) return latex;
    rows.push(latex.slice(start));
    return '\\begin{aligned}' + rows.map(row => {
      const escaped = literalAmpersands(row, 'aligned');
      return /(?<!\\)&/.test(escaped) ? escaped : '&' + escaped;
    }).join('\\\\') + '\\end{aligned}';
  }

  function completeTextGroup(latex) {
    // One missing closing brace on a terminal text label is syntactic only.
    // Never infer the scope of an unfinished fraction, exponent or overbar.
    const groups = [];
    for (let index = 0; index < latex.length; index++) {
      if (latex[index] === '\\' && /[{}\\]/.test(latex[index + 1] || '')) {index++; continue;}
      if (latex[index] === '{') groups.push(/\\text$/.test(latex.slice(0, index)));
      else if (latex[index] === '}') {if (!groups.length) return latex; groups.pop();}
    }
    return groups.length === 1 && groups[0] ? latex + '}' : latex;
  }

  function renderMath(container, latex, display = true) {
    container.replaceChildren();
    container.classList.remove('math-error', 'math-fallback');
    delete container.dataset.mathError;
    try {
      if (typeof latex !== 'string' || !latex.trim()) throw new Error('Enter a formula.');
      if (latex.length > 5000) throw new Error('Formula exceeds 5,000 characters.');
      if (!window.katex) throw new Error('The math renderer could not be loaded.');
      window.katex.render(literalAmpersands(displayRows(completeTextGroup(latex), display)), container, {
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

  function citation(source, {onSource, sourceUrl, sourceLabel, linkSources = true} = {}, tag = 'p') {
    const caption = element(tag, 'citation');
    const label = sourceLabel ? sourceLabel(source) : `Page ${source.page}`;
    const link = element(linkSources ? 'a' : 'span', '', label);
    if (linkSources) {
      link.href = sourceUrl ? sourceUrl(source) : `/source.pdf#page=${source.page}`;
      link.target = '_blank'; link.rel = 'noopener';
    }
    if (linkSources && onSource) link.addEventListener('click', event => {
      event.preventDefault(); onSource(source);
    });
    caption.append(link); return caption;
  }

  function mathBlock(block, options = {}) {
    const {editable = true} = options;
    const figure = element('figure', 'math-block');
    const output = element('div', 'math-output');
    renderMath(output, block.latex, block.display);
    figure.append(output);
    if (block.source) figure.append(citation(block.source, options, 'figcaption'));
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

  // Bounded legacy recovery for mathematical fragments, not English sentences.
  // No operator substitutions, entity decoding or missing-content inference.
  let group = String.raw`\{[^{}\n]*\}`;
  for (let depth = 0; depth < 3; depth++) group = String.raw`\{(?:[^{}\n]|${group})*\}`;
  const argument = String.raw`(?:${group}|[A-Za-z0-9])`;
  const parens = String.raw`\((?:[^()\n]|\([^()\n]*\))*\)`;
  const command = String.raw`\\[A-Za-z]+(?:\s*${group}){0,2}`;
  const atom = String.raw`(?:\\(?:neg|lnot)\s*)*(?:${command}|\\[&{}]|[A-Za-z](?![A-Za-z])|\d+(?:\.\d+)?|\|[^|\n]+\|)(?:${parens}|[_^]${argument}|!)*`;
  const operator = String.raw`(?:\\(?:Rightarrow|Leftarrow|Leftrightarrow|rightarrow|leftarrow|leftrightarrow|implies|iff|lor|vee|land|wedge|cap|cup|in|notin|subseteq|subset|supseteq|supset|times|cdot|equiv|neq|leq|geq|downarrow|uparrow|oplus|setminus|mid)(?![A-Za-z])|\\&|[&=+*/<>−-])`;
  const bareMath = new RegExp(String.raw`(?<![A-Za-z\\])${atom}(?:\s*${operator}\s*${atom})*(?![A-Za-z])`, 'g');

  function* legacyTextParts(text) {
    let position = 0;
    for (const match of text.matchAll(bareMath)) {
      const expression = match[0];
      // Plain words, sentence numbers, initials and articles stay plain text.
      if (!/[\\^_=|!&]/.test(expression) && !/^[A-Za-z]\(/.test(expression)) continue;
      const withoutCommands = expression.replace(/\\[A-Za-z]+/g, '');
      if (/\b[A-Za-z]{3,}\b/.test(withoutCommands)) continue;
      yield {text: text.slice(position, match.index)};
      yield {latex: expression, display: false, raw: expression, explicit: false};
      position = match.index + expression.length;
    }
    yield {text: text.slice(position)};
  }

  function* textParts(text) {
    // Explicit delimiters and complete environments take precedence over any
    // legacy fragment scanning. Preserve every source character inside math.
    const pattern = /\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]|\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$|(\\begin\{(aligned|alignedat|gathered|array|matrix|pmatrix|bmatrix|Bmatrix|vmatrix|Vmatrix|smallmatrix|cases)\}[\s\S]*?\\end\{\6\})/g;
    let position = 0;
    for (const match of text.matchAll(pattern)) {
      yield* legacyTextParts(text.slice(position, match.index));
      const display = match[2] !== undefined || match[3] !== undefined || match[5] !== undefined;
      yield {latex: match[1] ?? match[2] ?? match[3] ?? match[4] ?? match[5],
        display, raw: match[0], explicit: true};
      position = match.index + match[0].length;
    }
    yield* legacyTextParts(text.slice(position));
  }

  function renderText(container, text) {
    for (const part of textParts(text)) {
      if (part.text !== undefined) {container.append(document.createTextNode(part.text)); continue;}
      const math = element('span', part.display ? 'inline-math display-math' : 'inline-math');
      const rendered = renderMath(math, part.latex, part.display);
      // Preserve the existing plain-text fallback for unsupported bare TeX.
      container.append(rendered || part.explicit ? math : document.createTextNode(part.raw));
    }
  }

  function renderBlocks(container, blocks, options = {}) {
    container.replaceChildren();
    const seen = new Set();
    for (const block of blocks) {
      if (block.kind === 'text') {
        const paragraph = element('p', 'text-block'); renderText(paragraph, block.text); container.append(paragraph);
      }
      else if (block.kind === 'math') {
        const key = JSON.stringify([block.latex.trim(), block.source, block.original_latex, block.change, block.display]);
        if (seen.has(key)) continue;
        seen.add(key); container.append(mathBlock(block, options));
      }
      else container.append(element('p', 'error', 'Unsupported content block.'));
    }
  }

  function flashcardSides(item) {
    // Older saved sets and browser drafts put the answer formula in question.
    // Project both faces without mutating those records or losing citations.
    const question = [], moved = [];
    const answerMath = new Set(item.answer.filter(block => block.kind === 'math').map(block => block.latex.trim()));
    for (const block of item.question) {
      if (block.kind === 'math') {moved.push(block); continue;}
      const parts = [...textParts(block.text)], maths = parts.filter(part => part.latex !== undefined);
      if (!maths.length) {question.push(block); continue;}
      const text = parts.filter(part => part.text !== undefined).map(part => part.text).join('')
        .replace(/\(\s*\)|\[\s*\]/g, '').replace(/[ \t]+([,.;:!?])/g, '$1').replace(/[ \t]{2,}/g, ' ').trim();
      if (/[\p{L}\p{N}]/u.test(text)) question.push({...block, text});
      for (const part of maths) {
        if (answerMath.has(part.latex.trim())) continue;
        // Keep inline mathematics in a canonical text block; do not invent a
        // citation or alter the source expression, even when KaTeX rejects it.
        moved.push({kind: 'text', text: part.explicit ? part.raw : `\\(${part.latex}\\)`});
      }
    }
    const answer = [], seen = new Set();
    for (const block of [...moved, ...item.answer]) {
      if (block.kind === 'math') {
        const key = JSON.stringify([block.latex, block.source, block.original_latex, block.change]);
        if (seen.has(key)) continue;
        seen.add(key);
      }
      answer.push(block);
    }
    return {...item, question: question.length ? question : [{kind: 'text', text: 'Recall the formula.'}], answer};
  }

  function variantBlocks(item) {
    const seen = new Set();
    return [...item.question, ...item.answer].filter(block => {
      if (block.kind !== 'math' || !block.original_latex) return false;
      const key = JSON.stringify([block.latex, block.source, block.original_latex, block.change]);
      if (seen.has(key)) return false;
      seen.add(key); return true;
    });
  }
  window.MathPDF = {renderMath, renderBlocks, mathBlock, citation, flashcardSides, variantBlocks};
})();
