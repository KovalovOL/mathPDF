(async () => {
  try {
    const result = JSON.parse(document.getElementById('study-data').textContent);
    const element = (tag, text) => {const item = document.createElement(tag); item.textContent = text; return item;};
    document.title = result.title;
    document.getElementById('title').textContent = result.title;
    document.getElementById('source').textContent = `${result.document.filename} · source pages ${result.pages.join(', ')}`;
    const options = {editable: false, linkSources: false, sourceLabel: ref => `${result.document.filename} · page ${ref.page}`};
    for (const [index, item] of result.items.entries()) {
      for (const side of ['question', 'answer']) {
        const section = document.createElement('section'); section.className = 'print-item';
        section.append(element('h3', `${index + 1}. ${item.title}`));
        const blocks = document.createElement('div'); MathPDF.renderBlocks(blocks, item[side], options);
        section.append(blocks);
        if (side === 'answer') for (const block of item.question.filter(b => b.kind === 'math' && b.original_latex)) {
          section.append(element('p', block.change));
          section.append(MathPDF.mathBlock({...block, latex: block.original_latex}, options));
        }
        document.getElementById(side === 'question' ? 'questions' : 'answers').append(section);
      }
    }
    if (document.querySelector('.math-error')) throw new Error('A formula contains unsupported TeX. Correct it before exporting.');
    await document.fonts.ready;
    for (const output of document.querySelectorAll('.math-output')) {
      if (output.scrollWidth > output.clientWidth + 1) {
        const ratio = output.clientWidth / output.scrollWidth;
        if (ratio < 0.5) throw new Error('A formula is too wide for the PDF page. Split it into aligned lines before exporting.');
        output.style.fontSize = `${16 * ratio * .98}px`;
        if (output.scrollWidth > output.clientWidth + 2) throw new Error('A formula does not fit the PDF page. Adjust its layout before exporting.');
      }
    }
    document.documentElement.dataset.exportStatus = 'ready';
  } catch (error) {
    document.getElementById('export-error').textContent = error.message;
    document.documentElement.dataset.exportStatus = 'error';
  }
})();
