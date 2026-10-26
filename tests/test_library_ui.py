"""Isolated library controls with in-memory state, no accounts or live application."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright
from formula_lab.pdf_export import chromium_executable


def test_library_drag_archive_restore_and_root_destination():
    static=Path(__file__).parents[1]/'formula_lab/static'
    account='''const state={folders:[{id:'folder',name:'Algebra',parent_id:null}],files:[
      {id:'doc',filename:'Notes.txt',media_type:'text/plain',page_count:null,size:10,sha256:'hash',folder_id:null,archived:false}],
      sets:[{id:'set',title:'Recall',mode:'flashcards',item_count:2,updated_at:'2026-10-26',
      document_id:'doc',document_filename:'Notes.txt',difficulty:4,folder_id:null,archived:false}]};
      window.MathPDFSession={user:{id:'owner'},ready:Promise.resolve({id:'owner'}),setLeaveGuard(){},
      async api(url,options={}){if(url==='/api/library')return structuredClone(state);
        if(url.startsWith('/api/library/items/')){const [,kind,id]=url.match(/items\\/([^/]+)\\/(.+)$/);
          Object.assign((kind==='documents'?state.files:state.sets).find(x=>x.id===id),JSON.parse(options.body));return {};}
        throw new Error('Unexpected isolated request');}};'''

    async def check():
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page(viewport={'width':1280,'height':900})
                async def local(route):
                    name=route.request.url.rsplit('/',1)[-1]
                    if name=='account.js':body,kind=account,'text/javascript'
                    elif name=='file-previews.js':body,kind='export function createFilePreviews(){return {observe(){},destroy(){}}}','text/javascript'
                    elif name=='leave-guard.js':body,kind='export function createLeaveGuard(){return {confirm:async()=>true,reset(){}}}','text/javascript'
                    elif name in {'home.js','style.css'}:body,kind=(static/name).read_text(),'text/css' if name.endswith('css') else 'text/javascript'
                    elif name=='favicon.svg':body,kind=(static/name).read_text(),'image/svg+xml'
                    else:body,kind=(static/'home.html').read_text(),'text/html'
                    await route.fulfill(body=body,content_type=kind)
                await page.route('**/*',local)
                await page.goto('http://library.local/')
                await page.get_by_role('button',name='Open folder Algebra',exact=True).wait_for()
                assert await page.locator('.source-group-heading').inner_text()=='Notes.txt\n1'
                await page.locator('.file-card').drag_to(page.get_by_role('button',name='Open folder Algebra',exact=True))
                await page.wait_for_function("document.querySelector('#files-count').textContent==='0'")
                await page.get_by_role('button',name='Open folder Algebra',exact=True).click()
                await page.locator('.file-card').wait_for()
                assert await page.locator('#sets-count').inner_text()=='0' # Moving the source did not move its set.
                await page.locator('summary[aria-label="Actions for Notes.txt"]').click()
                await page.get_by_role('button',name='Archive Notes.txt',exact=True).click()
                await page.wait_for_function("document.querySelector('#files-count').textContent==='0'")
                await page.locator('#archive-view').click()
                await page.locator('.file-card').wait_for()
                assert 'Your library / Algebra' in await page.locator('.file-card-details').inner_text()
                await page.locator('summary[aria-label="Actions for Notes.txt"]').click()
                await page.get_by_role('button',name='Restore Notes.txt',exact=True).click()
                await page.wait_for_function("document.querySelector('#files-count').textContent==='0'")
                await page.get_by_role('button',name='Your library',exact=True).click()
                await page.get_by_role('button',name='Open folder Algebra',exact=True).click()
                await page.locator('summary[aria-label="Actions for Notes.txt"]').click()
                await page.get_by_role('button',name='Move Notes.txt',exact=True).click()
                await page.get_by_label('Destination folder',exact=True).select_option('')
                await page.get_by_role('button',name='Move',exact=True).click()
                await page.wait_for_function("!document.querySelector('#move-dialog').open && document.querySelector('#files-count').textContent==='0'")
                await page.get_by_role('button',name='Your library',exact=True).click()
                await page.locator('.file-card').wait_for()
                assert await page.locator('#sets-count').inner_text()=='1'
            finally:await browser.close()
    asyncio.run(check())
