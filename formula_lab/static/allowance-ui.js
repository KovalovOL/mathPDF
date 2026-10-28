/* User-facing allowances use percentages; raw accounting stays in administration. */
export function createAllowanceUI({api}){
  const header=document.querySelector('.app-header');let state,refreshing;
  const bar=document.createElement('div');bar.className='allowance-header';bar.hidden=true;if(header)header.after(bar);
  function render(target,compact=false){target.replaceChildren();target.hidden=!state?.limited;if(target.hidden)return;
    const label=document.createElement('span');label.textContent=`Generation · ${state.remaining_percent}% remaining`;
    const progress=document.createElement('progress');progress.max=100;progress.value=state.remaining_percent;progress.setAttribute('aria-label','Generation allowance remaining');progress.setAttribute('aria-valuetext',`${state.remaining_percent}% remaining`);
    const reset=document.createElement('span');reset.className='allowance-reset';reset.textContent=`Renews ${new Date(state.resets_at).toLocaleDateString('en-GB',{month:'short',day:'numeric',timeZone:'UTC'})} (UTC)`;
    target.append(label,progress,reset);if(state.reserved_tokens>0){target.title='Includes an estimated hold for pending or unconfirmed generation usage.';if(!compact){const note=document.createElement('p');note.className='field-note';note.textContent=target.title;target.append(note);}}else target.removeAttribute('title');
  }
  function draw(){render(bar,true);for(const box of document.querySelectorAll('[data-generation-allowance]'))render(box);document.documentElement.style.setProperty('--allowance-height',bar.hidden?'0px':'38px');}
  async function refresh(){if(refreshing)return refreshing;refreshing=(async()=>{try{state=await api('/api/generation/allowance');draw();}catch{}finally{refreshing=null;}})();return refreshing;}
  addEventListener('mathpdf-allowance-changed',refresh);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  return {refresh};
}
