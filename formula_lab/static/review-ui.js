/* Durable self-assessment is separate from formula rendering and saved study payloads. */
export function createReviewUI({api,userId,onChange,select,onError}){
  const states=new Map(),make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const storageKey=id=>`mathpdf-${userId}-review-pending-${id}`;
  function pending(id){try{const item=JSON.parse(localStorage.getItem(storageKey(id))||'null');return item&&typeof item.correct==='boolean'&&Number.isInteger(item.index)&&/^[a-f0-9]{32}$/.test(item.round_id)?item:null;}catch{return null;}}
  function store(id,value){try{value?localStorage.setItem(storageKey(id),JSON.stringify({schema_version:1,...value})):localStorage.removeItem(storageKey(id));}catch{}}
  async function replay(record,state){const item=state.pending||pending(record.id);if(!item)return;await api(`/api/reviews/${item.round_id}/answers`,{method:'POST',body:JSON.stringify({index:item.index,correct:item.correct})});state.pending=null;store(record.id,null);}
  async function load(record,state,newRound=false,useSaved=false){if(state.loading)return;state.loading=true;state.error=null;
    try{if(!useSaved)await replay(record,state);state.data=await api(`/api/study-sets/${record.id}/reviews`,{method:'POST',body:JSON.stringify({content:record.data,new_round:newRound})});
      if(useSaved){state.pending=null;state.conflict=false;store(record.id,null);}
      if(!state.data.completed_at){const answered=new Set(state.data.answers.map(a=>a.index));if(answered.has(record.itemIndex)){record.itemIndex=record.data.items.findIndex((_,i)=>!answered.has(i));record.flipped=false;}}
    }catch(error){state.error=error.message;state.conflict=error.status===409;}finally{state.loading=false;onChange(record);}}
  function get(record){const key=JSON.stringify(record.data.items);let state=states.get(record.id);if(!state||state.key!==key){state={key,data:null,loading:false,saving:false,error:null};states.set(record.id,state);load(record,state);}return state;}
  async function grade(record,correct){const state=get(record);if(state.loading||state.saving||!state.data)return;state.saving=true;state.error=null;
    const answer=state.pending||{round_id:state.data.id,index:record.itemIndex,correct};state.pending=answer;store(record.id,answer);onChange(record);
    try{state.data=await api(`/api/reviews/${answer.round_id}/answers`,{method:'POST',body:JSON.stringify({index:answer.index,correct:answer.correct})});state.pending=null;store(record.id,null);
      state.saving=false;record.reviewBrowse=false;
      if(!state.data.completed_at){const rated=new Set(state.data.answers.map(a=>a.index));select(record,record.data.items.findIndex((_,i)=>!rated.has(i)));}
      else onChange(record);
    }catch(error){state.saving=false;state.error=error.message;state.conflict=error.status===409;onChange(record);onError(error.message);}}
  function controls(record){const state=get(record),root=make('section',undefined,'review-controls'),status=make('p',undefined,'review-status');status.setAttribute('aria-live','polite');root.append(status);
    const actions=make('div',undefined,'review-actions'),correct=make('button','✓ Correct','review-correct'),incorrect=make('button','✕ Incorrect','review-incorrect');correct.type=incorrect.type='button';correct.addEventListener('click',()=>grade(record,true));incorrect.addEventListener('click',()=>grade(record,false));actions.append(incorrect,correct);root.append(actions);
    function update(flipped){const rated=state.data?.answers.find(a=>a.index===record.itemIndex);actions.hidden=!flipped||!!rated||!state.data;
      correct.disabled=incorrect.disabled=state.saving||state.loading||!!state.pending;
      status.textContent=state.error?state.error:state.saving?'Saving…':state.loading?'Loading progress…':rated?`Marked ${rated.correct?'correct':'incorrect'}`:'';status.hidden=!status.textContent;root.hidden=actions.hidden&&!status.textContent;}
    if(state.error){const retry=make('button',state.conflict?'Use saved progress':state.pending?'Retry saving answer':'Retry progress','small secondary');retry.type='button';retry.addEventListener('click',()=>state.conflict?load(record,state,false,true):state.pending?grade(record,state.pending.correct):load(record,state));root.append(retry);}
    return {root,update};}
  function summary(record){const state=get(record),data=state.data;if(!data?.completed_at)return null;
    const box=make('section',undefined,'review-summary');box.append(make('span','Round complete','review-eyebrow'),make('h2',`${data.score_percent}% correct`),make('p',`${data.correct_count} correct · ${data.incorrect_count} incorrect · ${data.item_count} cards`));
    const previous=data.history.find(r=>r.id!==data.id);
    if(previous){const delta=Number((data.score_percent-previous.score_percent).toFixed(1));box.append(make('p',`${delta>0?'+':''}${delta} percentage points compared with your previous round.`,'field-note'));}
    const actions=make('div',undefined,'review-actions'),again=make('button',state.loading?'Starting…':'Practice again'),browse=make('button','Review cards','secondary');again.type=browse.type='button';again.disabled=browse.disabled=state.loading||state.saving;
    again.addEventListener('click',()=>{record.itemIndex=0;record.flipped=false;record.reviewBrowse=false;load(record,state,true);onChange(record);});browse.addEventListener('click',()=>{record.reviewBrowse=true;record.itemIndex=0;record.flipped=false;onChange(record);});actions.append(again,browse);box.append(actions);
    if(state.error)box.append(make('p',state.error,'error'));
    box.append(make('h3','Recent progress'));const history=make('ol',undefined,'review-history');for(const round of [...data.history.slice(0,10)].reverse()){const row=make('li'),date=make('span',new Date(round.completed_at).toLocaleDateString('en-GB',{day:'numeric',month:'short'})),bar=make('progress');bar.max=100;bar.value=round.score_percent;bar.setAttribute('aria-label',`Round score ${round.score_percent}%`);row.append(date,bar,make('strong',`${round.score_percent}%`));history.append(row);}box.append(history);return box;}
  return {controls,summary};
}
