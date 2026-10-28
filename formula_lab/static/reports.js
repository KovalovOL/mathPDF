/* Private diagnostic context and manual tester feedback; ingestion never reports itself. */
export function initialize({getUser}) {
  const requests=[],actions=[],queue=[],seen=new Set();let contextProvider=()=>({}),sending=false,automaticCount=0,restoredUser;
  const reference=()=>crypto.randomUUID().replaceAll('-','');
  const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  function clean(value,depth=0) {
    if(depth>22)return {_truncated:true,reason:'nesting limit'};
    if(Array.isArray(value))return value.slice(0,300).map(v=>clean(v,depth+1));
    if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).slice(0,500).map(([k,v])=>[k,(/password|cookie|authorization|secret|api.?key|access.?token|refresh.?token|id.?token|private.?key|access.?key|secter|verifier|nonce/i.test(k)||(k==='input'&&value.loc?.some(p=>/password|cookie|authorization|secret|token|key/i.test(String(p)))))?'[REDACTED]':clean(v,depth+1)]));
    if(typeof value==='string')return value.replace(/sk-(?:proj-)?[A-Za-z0-9_-]{12,}|GOCSPX-[A-Za-z0-9_-]{10,}|Bearer\s+[A-Za-z0-9._~+/-]{12,}/g,'[REDACTED]').slice(0,250000);
    return value;
  }
  function bounded(value,max=1200000) {const result=clean(value),text=JSON.stringify(result),bytes=new TextEncoder().encode(text);return bytes.length<=max?result:{_truncated:true,reason:'browser context byte limit',serialized_prefix:new TextDecoder().decode(bytes.slice(0,max-200))};}
  function action(type,value){actions.push({at:new Date().toISOString(),type,...clean(value)});if(actions.length>100)actions.shift();}
  function persist(){const user=getUser();if(user)try{sessionStorage.setItem(`mathpdf-reports-${user.id}`,JSON.stringify(queue.slice(-10)));}catch{}}
  function restore(){const user=getUser();if(!user||restoredUser===user.id)return;restoredUser=user.id;try{for(const item of JSON.parse(sessionStorage.getItem(`mathpdf-reports-${user.id}`)||'[]'))if(item&&item.context&&!queue.some(q=>q.origin===item.origin&&q.request_id===item.request_id)){queue.push(item);if(item.request_id)seen.add(item.request_id);}}catch{}}
  async function snapshot(){
    let active;try{active=await contextProvider();}catch(error){active={_unavailable:true,reason:error.name};}
    return bounded({page:{path:location.pathname+location.search,title:document.title,build:document.querySelector('meta[name=mathpdf-build]')?.content,
      width:innerWidth,height:innerHeight,scroll:{x:scrollX,y:scrollY},language:navigator.language,time_zone:Intl.DateTimeFormat().resolvedOptions().timeZone,user_agent:navigator.userAgent},
      active,selection:getSelection()?.toString().slice(0,5000),recent_actions:actions.slice(-100),recent_requests:requests.slice(-30)});
  }
  async function send(report){
    const user=getUser();if(!user)throw new Error('Sign in before sending feedback.');
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    try{
      const response=await fetch('/api/reports',{method:'POST',credentials:'same-origin',cache:'no-store',signal:controller.signal,
        headers:{'Content-Type':'application/json','X-MathPDF-User':user.id,'X-MathPDF-Request-ID':reference()},body:JSON.stringify(report)});
      const result=await response.json().catch(()=>null);
      if(!response.ok)throw new Error(result?.detail||`Report service returned HTTP ${response.status}.`);
      return result;
    }finally{clearTimeout(timer);}
  }
  async function drain(){restore();if(sending||!queue.length||!getUser())return;sending=true;
    try{while(queue.length){await send(queue[0]);queue.shift();persist();}}catch{}finally{sending=false;}}
  async function automatic(request_id,extra){
    if(!getUser()||seen.has(request_id)||automaticCount>=10)return;seen.add(request_id);automaticCount++;
    queue.push({origin:'automatic',category:'bug',request_id,context:bounded({...await snapshot(),failure:extra})});persist();drain();
  }
  async function observe(path,options,response){
    const url=new URL(path,location.origin);if(url.origin!==location.origin||!url.pathname.startsWith('/api/')||url.pathname.startsWith('/api/reports')||url.pathname==='/api/client-errors')return;
    let body=null;
    if(options.body instanceof FormData)body={files:[...options.body].map(([key,file])=>typeof file==='string'?{field:key,value:file}:{field:key,name:file.name,size:file.size,type:file.type})};
    else if(typeof options.body==='string')try{body=JSON.parse(options.body);}catch{body={_unreadable:true};}
    let data=null;const mime=response.headers.get('content-type')||'';
    if(mime.includes('json')||response.status>=400){const copy=response.clone();let bytes=0,text='';
      try{const reader=copy.body.getReader();const decoder=new TextDecoder();while(true){const {value,done}=await reader.read();if(done)break;bytes+=value.length;if(bytes>1500000){await reader.cancel();text='';data={_truncated:true,reason:'response size limit'};break;}text+=decoder.decode(value,{stream:true});}
        if(text)try{data=JSON.parse(text);}catch{data={text:text.slice(0,5000),_unreadable:true};}
      }catch{data={_unreadable:true};}}
    const requestId=data?.request_id||response.headers.get('x-mathpdf-request-id')||reference();
    const entry=bounded({at:new Date().toISOString(),path:url.pathname+url.search,method:options.method||'GET',status:response.status,
      request_id:response.headers.get('x-mathpdf-request-id'),request:body,response:data},180000);
    // Polling snapshots repeat large generated content; retain only terminal failures and mutations.
    if((options.method||'GET')!=='GET'||response.status>=400||data?.status==='failed'){requests.push(entry);if(requests.length>30)requests.shift();}
    const expectedQuota=(response.status===429&&data?.code==='generation_limit')||(data?.status==='failed'&&data?.limit?.code==='generation_limit');
    if(!expectedQuota&&(response.status>=400||data?.status==='failed'))await automatic(requestId,entry);
  }
  document.addEventListener('click',event=>{if(event.target.closest('#feedback-dialog'))return;const e=event.target.closest('button,a,summary');if(e)action('click',{id:e.id,label:e.getAttribute('aria-label')||e.textContent.trim().slice(0,180)});},true);
  document.addEventListener('change',event=>{const e=event.target;if(e.closest('#feedback-dialog')||e.type==='password')return;
    if(e.matches('select,input[type=radio],input[type=checkbox],input[type=number]')||['context-comment','set-name','page','zoom'].includes(e.id))action('change',{id:e.id,name:e.name,value:e.type==='checkbox'?e.checked:e.value});},true);
  addEventListener('error',event=>action('browser_error',{message:event.message,filename:event.filename,line:event.lineno}));
  addEventListener('unhandledrejection',event=>action('unhandled_rejection',{message:String(event.reason?.message||event.reason).slice(0,1000)}));
  const dialog=node('dialog');dialog.id='feedback-dialog';dialog.setAttribute('aria-labelledby','feedback-heading');
  const form=node('form'),header=node('div',undefined,'dialog-header'),heading=node('h2','Report a problem');heading.id='feedback-heading';header.append(heading);
  const content=node('div',undefined,'dialog-body'),categoryLabel=node('label','Issue type'),category=node('select');category.id='feedback-category';categoryLabel.htmlFor=category.id;
  for(const [value,label] of [['bug','Something is broken'],['incorrect_content','Incorrect content'],['formatting','Formula or layout formatting'],['too_slow','Response takes too long'],['answer_too_long','Answer is too long'],['other','Other feedback']])category.append(new Option(label,value));
  const commentLabel=node('label','What happened?'),comment=node('textarea');comment.id='feedback-comment';comment.rows=4;comment.maxLength=5000;comment.placeholder='Describe what you expected and what you saw.';commentLabel.htmlFor=comment.id;
  const note=node('p','Includes the current file/card, recent requests and actions, and relevant source files. Administrators can review this context. Passwords and credentials are excluded.','field-note'),error=node('p',undefined,'error');error.hidden=true;error.setAttribute('role','alert');
  content.append(categoryLabel,category,commentLabel,comment,note,error);
  const footer=node('div',undefined,'dialog-footer'),cancel=node('button','Cancel','secondary'),submit=node('button','Send report');cancel.type='button';submit.type='submit';cancel.autofocus=true;
  cancel.addEventListener('click',()=>{if(!submit.disabled)dialog.close();});dialog.addEventListener('cancel',event=>{if(submit.disabled)event.preventDefault();});footer.append(cancel,submit);form.append(header,content,footer);dialog.append(form);document.body.append(dialog);
  form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=cancel.disabled=true;error.hidden=true;
    try{const result=await send({origin:'manual',category:category.value,comment:comment.value,request_id:requests.at(-1)?.request_id||null,context:await snapshot()});
      dialog.close();comment.value='';let toast=document.getElementById('report-receipt');if(!toast){toast=node('div',undefined,'status-message');toast.id='report-receipt';toast.setAttribute('role','status');document.body.append(toast);}toast.textContent=`Report sent. Reference: ${result.id}`;toast.hidden=false;setTimeout(()=>toast.hidden=true,12000);
    }catch(failure){error.textContent=failure.message;error.hidden=false;}finally{submit.disabled=cancel.disabled=false;}});
  restore();const interval=setInterval(drain,10000);addEventListener('online',drain);addEventListener('pagehide',()=>{persist();clearInterval(interval);});
  return {observe,setContextProvider:provider=>contextProvider=provider,button(){const b=node('button','Report a problem','secondary');b.type='button';b.addEventListener('click',()=>{error.hidden=true;dialog.showModal();});return b;}};
}
