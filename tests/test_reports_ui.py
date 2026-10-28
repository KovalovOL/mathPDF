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
