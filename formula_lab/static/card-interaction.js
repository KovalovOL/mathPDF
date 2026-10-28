/* Card gestures stay independent from rendering, generation and review storage. */
export function wireFlashcard(card,{flip,previous,next}){
  let start,touch=false,moved=false;
  card.addEventListener('pointerdown',event=>{
    touch=event.pointerType==='touch';moved=false;start=touch?{x:event.clientX,y:event.clientY}:null;
    if(touch&&event.isPrimary===false)moved=true;
  });
  card.addEventListener('pointermove',event=>{if(start&&Math.hypot(event.clientX-start.x,event.clientY-start.y)>8)moved=true;});
  card.addEventListener('pointercancel',()=>{moved=true;start=null;});
  card.addEventListener('click',event=>{
    if(event.target.closest('a,button,input,textarea,select,summary'))return;
    if(moved){moved=false;start=null;return;}
    const selection=window.getSelection();
    if(!touch&&selection?.toString()&&card.contains(selection.anchorNode))return;
    if(touch&&selection?.toString()&&card.contains(selection.anchorNode))selection.removeAllRanges();
    start=null;touch=false;flip();
  });
  card.addEventListener('keydown',event=>{
    if(event.target!==card)return;
    if(event.code==='Space'||event.key==='Enter'){event.preventDefault();flip();}
    if(event.key==='ArrowLeft'){event.preventDefault();previous();}
    if(event.key==='ArrowRight'){event.preventDefault();next();}
  });
}
