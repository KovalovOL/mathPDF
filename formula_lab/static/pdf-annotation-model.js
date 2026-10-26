/* Annotation geometry and history are independent of the viewer and generated math. */
export function annotationHistory(initial = []) {
  let states = [structuredClone(initial)], index = 0, saved = JSON.stringify(initial);
  return {
    get items() {return states[index];},
    get dirty() {return JSON.stringify(states[index]) !== saved;},
    get canUndo() {return index > 0;},
    get canRedo() {return index < states.length - 1;},
    commit(items) {
      if (items.length === states[index].length && items.every((item, n) => item === states[index][n])) return false;
      states = states.slice(0, index + 1); states.push(items.slice());
      if (states.length > 101) states.shift();
      index = states.length - 1; return true;
    },
    undo() {if (index) index--;},
    redo() {if (index < states.length - 1) index++;},
    markSaved(items = states[index]) {saved = JSON.stringify(items);},
  };
}

export function segmentDistance([x,y], [ax,ay], [bx,by]) {
  const dx = bx-ax, dy = by-ay;
  const t = dx || dy ? Math.max(0, Math.min(1, ((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy))) : 0;
  return Math.hypot(x-ax-t*dx, y-ay-t*dy);
}
function inside(point, polygon) {
  let hit = false;
  for (let i=0,j=polygon.length-1; i<polygon.length; j=i++) {
    const [x,y]=point, [ax,ay]=polygon[i], [bx,by]=polygon[j];
    if ((ay>y)!==(by>y) && x<(bx-ax)*(y-ay)/(by-ay)+ax) hit=!hit;
  }
  return hit;
}
export function hitMark(mark, point, radius) {
  if (mark.kind === 'highlight') return mark.quads.some(quad => inside(point, quad));
  const points = mark.points, tolerance = radius + mark.width/2;
  if (points.length === 1) return segmentDistance(point, points[0], points[0]) <= tolerance;
  return points.slice(1).some((end, i) => segmentDistance(point, points[i], end) <= tolerance);
}

export function changedPages(before, after) {
  const old = new Map(before.map(item => [item.id,item])), pages = new Set();
  for (const item of after) {
    if (old.get(item.id) !== item) pages.add(item.page);
    old.delete(item.id);
  }
  for (const item of old.values()) pages.add(item.page);
  return pages;
}

export function mergeTextRects(rectangles) {
  const runs=[];
  for (const rect of rectangles.slice().sort((a,b)=>a.top-b.top || a.left-b.left)) {
    const height=rect.bottom-rect.top;
    const line=runs.find(run=>{
      const overlap=Math.min(run.bottom,rect.bottom)-Math.max(run.top,rect.top);
      const gap=Math.max(rect.left-run.right,run.left-rect.right,0);
      return overlap/Math.min(height,run.bottom-run.top)>.55 && gap<=Math.max(3,height*.8);
    });
    if (line) {line.left=Math.min(line.left,rect.left);line.right=Math.max(line.right,rect.right);
      line.top=Math.min(line.top,rect.top);line.bottom=Math.max(line.bottom,rect.bottom);}
    else runs.push({...rect});
  }
  return runs;
}
