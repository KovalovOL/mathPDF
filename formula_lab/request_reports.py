"""ASGI request/response tee: bounded context without buffering file transfers."""
import asyncio
import json
import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers
from .report_safety import bounded,MAX_CONTEXT_BYTES
from .reports import ReportInput
from .web_assets import build_id


class RequestReports:
    def __init__(self,app,reports):self.app,self.reports=app,reports
    async def __call__(self,scope,receive,send):
        path=scope.get('path','')
        if scope['type']!='http' or not path.startswith('/api/') or path.startswith(('/api/reports','/api/client-errors')):
            return await self.app(scope,receive,send)
        headers=Headers(scope=scope);request_body=bytearray();response_body=bytearray();status=500;response_headers={};start=perf_counter()
        request_json='application/json' in headers.get('content-type','')
        async def tee_receive():
            message=await receive()
            if request_json and message['type']=='http.request' and len(request_body)<=MAX_CONTEXT_BYTES:
                request_body.extend(message.get('body',b'')[:MAX_CONTEXT_BYTES+1-len(request_body)])
            return message
        async def tee_send(message):
            nonlocal status,response_headers
            if message['type']=='http.response.start':
                status=message['status'];response_headers=dict(Headers(raw=message.get('headers',[])))
            if message['type']=='http.response.body' and 'application/json' in response_headers.get('content-type','') and len(response_body)<=MAX_CONTEXT_BYTES:
                response_body.extend(message.get('body',b'')[:MAX_CONTEXT_BYTES+1-len(response_body)])
            await send(message)
        try:
            await self.app(scope,tee_receive,tee_send)
        finally:
            user=scope.get('state',{}).get('user')
            if user:
                reference=response_headers.get('x-mathpdf-request-id') or headers.get('x-mathpdf-request-id') or uuid4().hex
                if not re.fullmatch(r'[a-f0-9]{32}',reference):reference=uuid4().hex
                def decode(data):
                    if not data:return None
                    if len(data)>MAX_CONTEXT_BYTES:return {'_truncated':True,'reason':'HTTP JSON limit'}
                    try:return json.loads(data)
                    except (ValueError,UnicodeError):return {'_unreadable':True,'bytes':len(data)}
                parsed_response=decode(response_body)
                expected_quota=status==429 and isinstance(parsed_response,dict) and parsed_response.get('code')=='generation_limit'
                event=bounded({'request_id':reference,'method':scope['method'],'path':path,
                    'request':decode(request_body),'response':parsed_response,'status':status,
                    'exception':scope.get('state',{}).get('exception'),
                    'duration_ms':round((perf_counter()-start)*1000),'server_build':build_id(),
                    'user_agent':headers.get('user-agent','')[:500],
                    'request_content_type':headers.get('content-type',''),'response_content_type':response_headers.get('content-type','')})
                # Successful polls and bulk listings add little diagnostic value. Mutations and failures retain full business JSON.
                if scope['method'] not in {'GET','HEAD'} or status>=400:
                    try:
                        await asyncio.to_thread(self.reports.event,user,event)
                    except Exception as error:
                        logging.getLogger(__name__).warning('Request report persistence unavailable type=%s',type(error).__name__)

                    if status>=400 and not expected_quota:
                        try:
                            await asyncio.to_thread(self.reports.record,user,ReportInput(origin='automatic',request_id=reference,context={'server':event}))
                        except Exception as error:
                            logging.getLogger(__name__).warning('Automatic report unavailable type=%s',type(error).__name__)
