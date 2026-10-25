/* Source-pane layout only; document instances and study content remain mounted. */
export function createWorkspaceLayout({preference, onViewport}) {
  const workspace = document.getElementById('workspace'), source = document.getElementById('document-pane');
  const practice = document.getElementById('practice-pane'), splitter = document.getElementById('splitter');
  const hide = document.getElementById('hide-source'), show = document.getElementById('show-source');
  const mobile = matchMedia('(max-width: 640px)');
  let ratio = Number(preference('split-ratio')) || .5;
  let desktopCollapsed = preference('source-collapsed') === 'true', mobileCollapsed = false, gesture;
  const collapsed = () => mobile.matches ? mobileCollapsed : desktopCollapsed;

  function apply(settled = true) {
    workspace.classList.toggle('source-collapsed', collapsed());
    source.inert = collapsed(); source.setAttribute('aria-hidden', String(collapsed()));
    hide.setAttribute('aria-expanded', String(!collapsed())); show.hidden = !collapsed();
    if (!mobile.matches && !collapsed()) {
      const width = workspace.clientWidth - 32;
      const minimum = Math.max(.2, 240 / width), maximum = Math.min(.8, (width - 280) / width);
      ratio = Math.min(maximum, Math.max(minimum, ratio));
      workspace.style.setProperty('--source-size', `${ratio * 100}%`);
    }
    splitter.setAttribute('aria-valuenow', collapsed() ? '0' : String(Math.round(ratio * 100)));
    splitter.setAttribute('aria-valuemin', '0'); splitter.setAttribute('aria-valuemax', '80');
    onViewport(settled);
  }
  function collapseSource() {
    if (mobile.matches) mobileCollapsed = true;
    else {desktopCollapsed = true; preference('source-collapsed', true);}
    apply();
    if (mobile.matches) scrollTo(0, 0);
    show.focus({preventScroll: true});
  }
  function showSource({scroll = false} = {}) {
    if (mobile.matches) mobileCollapsed = false;
    else {desktopCollapsed = false; preference('source-collapsed', false);}
    apply();
    if (mobile.matches && scroll) window.scrollTo({top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  }
  function resize(value) {
    if (mobile.matches) return;
    if (value <= .06) {collapseSource(); return;}
    desktopCollapsed = false; preference('source-collapsed', false); ratio = value; apply(false);
  }
  function finish(event) {
    if (splitter.hasPointerCapture(event.pointerId)) splitter.releasePointerCapture(event.pointerId);
    document.body.classList.remove('resizing'); preference('split-ratio', ratio); onViewport(true);
  }
  hide.addEventListener('click', collapseSource);
  show.addEventListener('click', () => {showSource({scroll: true}); hide.focus({preventScroll: true});});
  splitter.addEventListener('pointerdown', event => {
    if (event.button !== 0 || mobile.matches) return;
    event.preventDefault(); splitter.setPointerCapture(event.pointerId); document.body.classList.add('resizing');
  });
  splitter.addEventListener('pointermove', event => {
    if (!splitter.hasPointerCapture(event.pointerId)) return;
    const box = workspace.getBoundingClientRect(); resize((event.clientX - box.left - 12) / (box.width - 32));
  });
  splitter.addEventListener('pointerup', finish); splitter.addEventListener('pointercancel', finish);
  splitter.addEventListener('lostpointercapture', () => {
    document.body.classList.remove('resizing'); preference('split-ratio', ratio); onViewport(true);
  });
  splitter.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault(); resize(event.key === 'Home' ? 0 : event.key === 'End' ? .8 : ratio + (event.key === 'ArrowRight' ? .03 : -.03));
    preference('split-ratio', ratio);
  });
  let resizeTimer;
  addEventListener('resize', () => {apply(false); clearTimeout(resizeTimer); resizeTimer = setTimeout(() => onViewport(true), 150);});
  mobile.addEventListener('change', () => apply());
  let scrollFrame;
  addEventListener('scroll', () => {
    if (!mobile.matches || collapsed()) return;
    cancelAnimationFrame(scrollFrame);
    scrollFrame = requestAnimationFrame(() => {
      const header = document.querySelector('.app-header').getBoundingClientRect().bottom;
      if (scrollY > 40 && practice.getBoundingClientRect().top <= header + 12) collapseSource();
    });
  }, {passive: true});
  function atTop(target) {
    if (getSelection()?.toString() || target.closest('a, button, input, textarea, select, summary')) return false;
    for (let node = target; node && node !== practice; node = node.parentElement) {
      if (node.scrollTop > 1 || node.scrollLeft > 1) return false;
    }
    return true;
  }
  practice.addEventListener('touchstart', event => {
    gesture = mobile.matches && collapsed() && event.touches.length === 1 && atTop(event.target)
      ? {x: event.touches[0].clientX, y: event.touches[0].clientY} : null;
  }, {passive: true});
  practice.addEventListener('touchmove', event => {
    if (!gesture || event.touches.length !== 1 || !atTop(event.target)) return;
    const touch = event.touches[0];
    if (touch.clientY - gesture.y > 65 && Math.abs(touch.clientX - gesture.x) < 45) {
      event.preventDefault(); gesture = null; showSource({scroll: true});
    }
  }, {passive: false});
  practice.addEventListener('touchend', () => {gesture = null;}, {passive: true});
  practice.addEventListener('touchcancel', () => {gesture = null;}, {passive: true});
  apply();
  return {showSource, collapseSource};
}
