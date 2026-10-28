/* Shared daily-allowance meter and recoverable generation-limit dialog. */
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
function resetText(state,now=Date.now()){
  const minutes=Math.max(0,Math.ceil((Date.parse(state.resets_at)-now)/60000));
  return `Resets in ${Math.floor(minutes/60)}h ${String(minutes%60).padStart(2,'0')}m · 00:00 UTC`;
}
function renderMeter(target,state,{compact=false}={}){
  target.replaceChildren();target.hidden=!state?.limited;if(target.hidden)return;
  const left=Math.max(0,Math.min(100,Number(state.remaining_percent)||0)),used=Number((100-left).toFixed(1));
  target.dataset.level=left===0?'empty':left<=20?'low':'normal';
  const heading=node('div',undefined,'allowance-heading');if(!compact)heading.append(node('span','Daily AI allowance'));heading.append(node('strong',`${left}% left`,'allowance-left'));
  const track=node('div',undefined,'allowance-track'),fill=node('span',undefined,'allowance-fill');fill.style.width=`${left}%`;track.append(fill);
  track.setAttribute('role','progressbar');track.setAttribute('aria-label','Daily generation allowance remaining');track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax','100');track.setAttribute('aria-valuenow',String(left));track.setAttribute('aria-valuetext',`${left}% remaining, ${used}% used`);
  target.append(heading,track);
  if(compact){target.title=`Daily AI allowance: ${left}% left. ${resetText(state)}${state.reserved_tokens>0?'. Pending or unconfirmed generations are included.':''}`;return;}
  const legend=node('div',undefined,'allowance-legend'),usedLabel=node('span',`${used}% used`,'allowance-used-label'),reset=node('span',resetText(state),'allowance-reset');legend.append(usedLabel,reset);
  target.append(legend);
  if(state.reserved_tokens>0)target.append(node('p','Pending or unconfirmed generations are included.','allowance-pending'));
}

export function createAllowanceUI({api}){
  const header=document.querySelector('.app-header'),actions=header?.querySelector('.header-actions');let state,refreshing;
  const bar=node('section',undefined,'allowance-header');bar.setAttribute('aria-label','Daily generation allowance');bar.tabIndex=0;bar.hidden=true;
  const primary=actions?.querySelector('#open-generation,#upload-files');if(primary)primary.before(bar);else (actions||header)?.prepend(bar);
  function draw(){renderMeter(bar,state,{compact:true});for(const box of document.querySelectorAll('[data-generation-allowance]'))renderMeter(box,state);dispatchEvent(new CustomEvent('mathpdf-allowance-updated',{detail:state}));}
  async function refresh(){if(refreshing)return refreshing;refreshing=(async()=>{try{state=await api('/api/generation/allowance');draw();}catch{}finally{refreshing=null;}})();return refreshing;}
  function tick(){if(document.hidden)return;if(state?.limited&&Date.now()>=Date.parse(state.resets_at))refresh();else if(state)draw();}
  const visible=()=>{if(!document.hidden)refresh();},timer=setInterval(tick,60000);addEventListener('mathpdf-allowance-changed',refresh);document.addEventListener('visibilitychange',visible);
  return {refresh,destroy(){clearInterval(timer);bar.remove();removeEventListener('mathpdf-allowance-changed',refresh);document.removeEventListener('visibilitychange',visible);}};
}

export function createGenerationLimitDialog({onAdjust}){
  const dialog=node('dialog',undefined,'allowance-dialog');dialog.setAttribute('aria-labelledby','allowance-dialog-title');
  const body=node('div',undefined,'allowance-dialog-body'),icon=node('div','◷','allowance-dialog-icon');icon.setAttribute('aria-hidden','true');
  const title=node('h2');title.id='allowance-dialog-title';const description=node('p',undefined,'allowance-description'),meter=node('div',undefined,'generation-allowance'),tip=node('p',undefined,'allowance-tip');
  const actions=node('div',undefined,'dialog-footer'),close=node('button','Close','secondary'),adjust=node('button','Adjust request');close.type=adjust.type='button';
  close.addEventListener('click',()=>dialog.close());adjust.addEventListener('click',()=>{dialog.close();onAdjust();});actions.append(close,adjust);body.append(icon,title,description,meter,tip);dialog.append(body,actions);document.body.append(dialog);
  let failure;
  function draw(){if(!failure)return;const state=failure.allowance,disabled=state.limited&&state.daily_tokens===0,ready=!state.limited||(!disabled&&(failure.reason==='insufficient'?typeof failure.required_percent==='number'&&failure.required_percent<=state.remaining_percent:state.remaining_percent>0));
    title.textContent=disabled?'Generation is paused for your plan':ready?'Your allowance is ready':failure.reason==='insufficient'?'This request needs more allowance':"You've used today's allowance";
    description.textContent=disabled?'Your free plan currently has no generation allowance.':ready?'You can return to your settings and generate your study set.':failure.reason==='insufficient'?`You have ${state.remaining_percent}% left. A smaller request may fit your remaining daily allowance.`:'Your full daily allowance will be available again at 00:00 UTC.';
    renderMeter(meter,state);
    const estimate=typeof failure.required_percent==='number'?`Estimated request: ${failure.required_percent}% of your daily allowance. `:'';
    tip.textContent=disabled?'Your administrator can update your daily allowance.':ready?'Your selected files, pages and comments are still there.':failure.reason==='insufficient'?(failure.required_percent>100?'This request exceeds a full daily allowance. Select fewer pages, fewer items or less additional context.':estimate+'Try fewer pages, fewer items or less additional context.'):'Come back after the reset. Your selected files, pages and comments are still there.';
    adjust.hidden=disabled;adjust.textContent=ready?'Continue':'Adjust request';
  }
  addEventListener('mathpdf-allowance-updated',event=>{if(!dialog.open||!failure||!event.detail)return;failure={...failure,allowance:event.detail};draw();});
  return {show(error){failure=error;draw();if(!dialog.open)dialog.showModal();adjust.hidden?close.focus():adjust.focus();}};
}
