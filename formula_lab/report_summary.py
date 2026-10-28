"""Small read-time incident summaries; historical report evidence remains untouched."""
from .diagnostics import error_identity,route_label
from .report_safety import sanitize


def obj(value):return value if isinstance(value,dict) else {}
def seq(value):return value if isinstance(value,list) else []
def text(value):return value[:200] if isinstance(value,str) else None

def summarize(report):
    payload=obj(report.get('payload'));client=obj(payload.get('client'));server=obj(payload.get('server'))
    failure=obj(client.get('failure'))
    path=text(server.get('path')) or text(failure.get('path')) or ''
    status=server.get('status') or failure.get('status')
    if not isinstance(status,int) or isinstance(status,bool):status=None
    exceptions=seq(server.get('exception'))
    kind=next((text(e.get('type')) for e in exceptions if isinstance(e,dict) and text(e.get('type'))),None)
    details=obj(server.get('error_details')) or error_identity(route=path,status=status or 500,exception_type=kind)
    # Historical incidents carry only stack locations; derive the useful origin.
    location=details.get('location')
    if not location:
        frames=[frame for entry in exceptions if isinstance(entry,dict) for frame in seq(entry.get('frames')) if isinstance(frame,str)]
        location=next((f for f in reversed(frames) if f.split(':')[0] in {'library.py','study.py','workspace.py','providers.py','app.py'}),None)
    ui=obj(server.get('ui'));active=obj(client.get('active'));workspace=obj(active.get('workspace'))
    actions=seq(client.get('recent_actions'))
    action=text(ui.get('action')) or next((text(a.get('label')) or text(a.get('id')) for a in reversed(actions) if isinstance(a,dict) and (a.get('label') or a.get('id'))),None)
    page=obj(client.get('page'));page_path=text(page.get('path')) or ''
    screen=ui.get('screen') or ('library' if page_path.split('?')[0]=='/' else 'workspace' if page_path.split('?')[0]=='/workspace' else None)
    manifest=obj(report.get('manifest'));sources=seq(manifest.get('sources'))
    document=obj(workspace.get('active_document'))
    documents=[{'id':s.get('id'),'name':s.get('filename')} for s in sources if isinstance(s,dict)]
    if not documents and document.get('id'):documents=[{'id':document.get('id'),'name':document.get('filename')}]
    timeline=[];seen=set()
    for request in [server,*seq(payload.get('recent_requests')),*seq(client.get('recent_requests'))]:
        if not isinstance(request,dict) or not text(request.get('path')):continue
        key=text(request.get('request_id')) or (text(request.get('method')),text(request.get('path')),request.get('status') if isinstance(request.get('status'),int) else None)
        if key in seen:continue
        seen.add(key);route=route_label(request['path'].split('?')[0]);method=text(request.get('method'));response_status=request.get('status') if isinstance(request.get('status'),int) else None
        matching=next((r for r in timeline if (r['method'],r['route'],r['status'])==(method,route,response_status)),None)
        if matching:matching['count']+=1
        elif len(timeline)<8:timeline.append({'method':method,'route':route,'status':response_status,'request_id':text(request.get('request_id')),'duration_ms':request.get('duration_ms') if isinstance(request.get('duration_ms'),(int,float)) else None,'count':1})
    manual=report.get('origin')=='manual'
    return sanitize({'title':report.get('category','Feedback').replace('_',' ').capitalize() if manual else details.get('summary','Request failed'),
        'error_code':details.get('error_code'),'error_type':details.get('error_type') or kind,'location':location,
        'route':route_label(path.split('?')[0]) if path else None,'method':server.get('method') or failure.get('method'),'status':status,
        'screen':screen,'action':action or ('Load library' if path=='/api/library' else None),'documents':documents[:6],
        'page':ui.get('page') or obj(workspace.get('reading')).get('page'),'item_index':ui.get('item_index',workspace.get('item_index')),
        'request_id':report.get('request_id'),'user_id':report.get('user_id'),'timeline':timeline,
        'steps':[{'at':text(a.get('at')),'action':text(a.get('label')) or text(a.get('id'))} for a in actions[-8:] if isinstance(a,dict) and a.get('type')=='click']})
