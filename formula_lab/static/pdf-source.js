/* Brief, interruptible page navigation; resize anchoring stays immediate. */
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
