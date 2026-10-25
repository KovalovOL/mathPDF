/* Match PDF text without trusting model-reported physical line numbers. */
function normalizedCharacters(value) {
  return value.normalize('NFKC').toLowerCase().replace(/[\s\u00ad\u200b]+/gu, '');
}

export function quotationRange(layer, quote) {
  if (typeof quote !== 'string' || quote.length > 1200) return null;
  const needle = normalizedCharacters(quote);
  if (needle.length < 10) return null;
  const positions = [];
  let text = '';
  for (const span of layer.textDivs) {
    const node = span.firstChild;
    if (!node || node.nodeType !== Node.TEXT_NODE) continue;
    let offset = 0;
    for (const character of node.data) {
      const normalized = normalizedCharacters(character);
      for (let index = 0; index < normalized.length; index++) {
        positions.push({node, start: offset, end: offset + character.length});
      }
      text += normalized; offset += character.length;
    }
  }
  const start = text.indexOf(needle);
  if (start < 0 || text.indexOf(needle, start + 1) >= 0) return null;
  const first = positions[start], last = positions[start + needle.length - 1];
  if (!first || !last) return null;
  const range = document.createRange();
  range.setStart(first.node, first.start); range.setEnd(last.node, last.end);
  return range;
}

let animationFrame = 0, animationResolve;
export function cancelNavigation() {
  cancelAnimationFrame(animationFrame); animationFrame = 0;
  animationResolve?.(); animationResolve = null;
}

export function scrollToSource(top, animated) {
  cancelNavigation();
  const target = Math.max(0, Math.min(top, document.documentElement.scrollHeight - innerHeight));
  if (!animated || matchMedia('(prefers-reduced-motion: reduce)').matches) {
    scrollTo(scrollX, target); return Promise.resolve();
  }
  const start = scrollY, began = performance.now(), duration = 300;
  return new Promise(resolve => {
    animationResolve = resolve;
    const tick = now => {
      const progress = Math.min(1, (now - began) / duration);
      const eased = 1 - (1 - progress) ** 3;
      scrollTo(scrollX, start + (target - start) * eased);
      if (progress < 1) animationFrame = requestAnimationFrame(tick);
      else {animationFrame = 0; animationResolve = null; resolve();}
    };
    animationFrame = requestAnimationFrame(tick);
  });
}
