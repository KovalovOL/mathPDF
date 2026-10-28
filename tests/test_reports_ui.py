"""Isolated reporting component checks; no production browser or real user content."""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

from formula_lab.math_validation import chromium_executable


def test_automatic_and_manual_context_redact_secrets_and_do_not_recurse():
    static=Path(__file__).parents[1]/'formula_lab/static'
    html='''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="account"></div>
    <script src="/static/account.js"></script><script>
    MathPDFSession.setContextProvider(()=>({document:{id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',filename:'fixture.pdf',sha256:'b'.repeat(64),media_type:'application/pdf'},page:4,item_index:2,answer:'Preserved formula: \\\\cap',clientSecret:'never retain',cookies:['never retain']}));
    </script>'''
    async def check():
        received=[];outage=False
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page(viewport={'width':390,'height':844})
                async def route(r):
                    nonlocal outage
                    path=r.request.url.split('localhost',1)[1].split('?',1)[0]
                    if path.startswith('/static/'):await r.fulfill(content_type='text/javascript',body=(static/path.removeprefix('/static/')).read_text())
                    elif path=='/api/me':await r.fulfill(json={'id':'c'*32,'email':'fixture@example.invalid','name':'Fixture user','role':'free'})
                    elif path=='/api/reports':
                        received.append(json.loads(r.request.post_data))
                        await r.fulfill(status=503 if outage else 202,json={'id':'d'*32,'status':'new'})
                    elif path=='/api/client-errors':await r.fulfill(status=204)
                    elif path=='/api/bad':await r.fulfill(status=400,json={'detail':'Invalid fixture','request_id':'e'*32},headers={'x-mathpdf-request-id':'e'*32})
                    elif path=='/api/outage':await r.fulfill(status=500,json={'detail':'Offline fixture','request_id':'b'*32},headers={'x-mathpdf-request-id':'b'*32})
                    elif path=='/api/server-error':await r.fulfill(status=500,json={'detail':'Failure fixture','request_id':'f'*32},headers={'x-mathpdf-request-id':'f'*32})
                    elif path=='/api/failed-job':await r.fulfill(json={'status':'failed','error':'Fixture failure','request_id':'a'*32})
                    elif path=='/api/allowance-limited':await r.fulfill(status=429,json={'code':'generation_limit','reason':'exhausted','detail':'Daily allowance used up.','allowance':{'remaining_percent':0}})
                    elif path=='/api/quota-job':await r.fulfill(json={'status':'failed','error':'Daily allowance used up.','limit':{'code':'generation_limit','reason':'insufficient'}})
                    else:await r.fulfill(content_type='text/html',body=html)
                await page.route('**/*',route);await page.goto('http://localhost/')
                await page.locator('.account-menu summary').click();await page.get_by_role('button',name='Report a problem',exact=True).wait_for()
                for path in ['/api/bad','/api/server-error','/api/failed-job']:
                    await page.evaluate('(path)=>MathPDFSession.api(path,{method:"POST",body:JSON.stringify({document_id:"a".repeat(32),count:5,clientSecret:"secret",cookies:["credential"]})}).catch(()=>{})',path)
                await page.wait_for_function('JSON.parse(sessionStorage.getItem("mathpdf-reports-"+"c".repeat(32))||"[]").length===0')
                # A manual report includes the exact current item/page and categorized comment.
                await page.get_by_role('button',name='Report a problem',exact=True).click()
                await page.get_by_label('Issue type',exact=True).select_option('answer_too_long')
                await page.get_by_label('What happened?',exact=True).fill('Use a shorter explanation.')
                await page.get_by_role('button',name='Send report',exact=True).click()
                await page.get_by_text('Report sent. Reference:',exact=False).wait_for()
                assert len(received)==4
                quota=await page.evaluate('MathPDFSession.api("/api/allowance-limited",{method:"POST"}).catch(e=>({code:e.code,status:e.status,reason:e.reason}))')
                assert quota=={'code':'generation_limit','status':429,'reason':'exhausted'}
                await page.evaluate('MathPDFSession.api("/api/quota-job").catch(()=>{})')
                await page.wait_for_function('JSON.parse(sessionStorage.getItem("mathpdf-reports-"+"c".repeat(32))||"[]").length===0')
                assert len(received)==4
                assert {r['request_id'] for r in received[:3]}=={'e'*32,'f'*32,'a'*32}
                assert received[-1]['category']=='answer_too_long' and received[-1]['comment']=='Use a shorter explanation.'
                assert received[-1]['context']['active']['page']==4 and received[-1]['context']['active']['item_index']==2
                serialized=json.dumps(received)
                assert 'never retain' not in serialized and 'credential' not in serialized
                assert received[-1]['context']['active']['answer'].endswith('\\cap')
                # A failing report endpoint is queued without recursively reporting itself.
                outage=True
                await page.evaluate('MathPDFSession.api("/api/bad",{method:"POST"}).catch(()=>{})')
                assert len(received)==4  # already seen incident, no duplicate
                await page.evaluate('MathPDFSession.api("/api/outage",{method:"POST"}).catch(()=>{})')
                await page.wait_for_function('JSON.parse(sessionStorage.getItem("mathpdf-reports-"+"c".repeat(32))||"[]").length===1')
                outage=False
                await page.reload();await page.locator('.account-menu summary').click();await page.get_by_role('button',name='Report a problem',exact=True).wait_for()
                await page.evaluate('dispatchEvent(new Event("online"))')
                await page.wait_for_function('JSON.parse(sessionStorage.getItem("mathpdf-reports-"+"c".repeat(32))||"[]").length===0')
                assert len(received)==6 and received[-1]['request_id']=='b'*32
            finally:await browser.close()
    asyncio.run(check())


def test_admin_report_starts_with_readable_summary_and_collapsed_original_evidence():
    static=Path(__file__).parents[1]/'formula_lab/static'
    async def check():
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page(viewport={'width':1100,'height':900})
                report={'id':'d'*32,'origin':'automatic','category':'bug','status':'new','collection_status':'ready','created_at':'2026-10-28T12:00:00Z','comment':'','note':'','user_id':'c'*32,'request_id':'e'*32,
                    'payload':{'user':{'email':'fixture@example.invalid'},'retained':'Original evidence'},'manifest':{},
                    'summary':{'title':'Stored JSON contains an unsupported database character.','error_code':'library_metadata_decode_failed','error_type':'UntranslatableCharacter','screen':'library','action':'Open library','method':'GET','route':'/api/library','status':500,'location':'library.py:132:snapshot','documents':[{'name':'Notes.pdf'}],'timeline':[{'method':'GET','route':'/api/library','status':500,'count':3,'duration_ms':12}]}}
                async def local(route):
                    path=route.request.url.split('admin.local',1)[1].split('?',1)[0]
                    if path=='/static/account.js':await route.fulfill(content_type='text/javascript',body="window.MathPDFSession={ready:Promise.resolve({role:'owner'}),api:async path=>(await fetch(path)).json()};")
                    elif path.startswith('/static/'):
                        file=static/path.removeprefix('/static/')
                        await route.fulfill(body=file.read_bytes(),content_type='text/css' if file.suffix=='.css' else 'text/javascript' if file.suffix=='.js' else 'image/svg+xml')
                    elif path=='/api/admin/reports':await route.fulfill(json=[{**report,'email':'fixture@example.invalid'}])
                    elif path.startswith('/api/admin/reports/'):await route.fulfill(json=report)
                    elif path=='/api/admin/overview':await route.fulfill(json={'users':1,'roles':[],'reports':[],'history_note':''})
                    elif path=='/api/admin/usage':await route.fulfill(json={'totals':{},'daily':[],'users':[],'models':[]})
                    elif path=='/api/admin/users':await route.fulfill(json=[])
                    elif path=='/api/admin/generation-limits':await route.fulfill(json={'daily_tokens':200000})
                    else:await route.fulfill(body=(static/'admin.html').read_text(),content_type='text/html')
                await page.route('**/*',local);await page.goto('http://admin.local/admin')
                await page.locator('[data-tab="reports"]').click()
                await page.locator('#report-list button').click()
                await page.locator('.incident-code').wait_for()
                assert 'Open library' in await page.locator('.incident-summary').inner_text()
                assert 'Notes.pdf' in await page.locator('.incident-summary').inner_text()
                assert await page.locator('.incident-advanced').get_attribute('open') is None
                assert not await page.locator('.admin-context').is_visible()
                await page.get_by_text('Advanced: full diagnostic JSON',exact=True).click()
                assert 'Original evidence' in await page.locator('.admin-context').inner_text()
            finally:await browser.close()
    asyncio.run(check())
