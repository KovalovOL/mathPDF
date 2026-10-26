"""Isolated parent bridge: dirty context, cancellation, original and failed save."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from formula_lab.pdf_export import chromium_executable


def test_generation_choices_preserve_notes_and_wait_for_a_successful_save():
    static=Path(__file__).parents[1]/'formula_lab/static'
    html='''<!doctype html><button id="annotate-pdf"></button>
        <div id="annotation-toolbar" hidden><div id="annotation-tools"></div>
        <div id="annotation-options"><select id="annotation-color"><option>#2563eb</option></select>
        <select id="annotation-width"><option>2</option></select><span id="annotation-status"></span></div></div>
        <dialog id="annotation-choice"><form method="dialog"><h2 id="annotation-choice-title"></h2>
        <p id="annotation-choice-message"></p><button value="cancel">Cancel</button>
        <button id="annotation-choice-discard" value="discard"></button><button id="annotation-choice-save" value="save"></button></form></dialog>
        <iframe id="frame" srcdoc="<!doctype html><p>Isolated context document</p>"></iframe>
        <script type="module">
        import {createAnnotationToolbar} from '/static/annotation-toolbar.js';
        const doc={id:'context-copy',filename:'Context - annotated.pdf',page_count:1,original_document_id:'context-original'};
        const frame=document.querySelector('#frame');window.commands=[];
        const toolbar=createAnnotationToolbar({activeDocument:()=>doc,documentFor:()=>doc,frameFor:id=>id===doc.id?frame:null,
          onSaved:()=>{},onOpenCopy:()=>{},onChange:()=>{},notifyViewport:()=>{},report:()=>{}});
        window.state=()=>dispatchEvent(new MessageEvent('message',{origin:location.origin,source:frame.contentWindow,
          data:{type:'annotation-state',documentId:doc.id,loaded:true,dirty:true,active:true,tool:'pen',color:'#2563eb',width:2,baseDocumentId:'context-original'}}));
        window.finishSave=(error)=>{
          const command=window.commands.at(-1);dispatchEvent(new MessageEvent('message',{origin:location.origin,source:frame.contentWindow,
            data:{type:'annotation-result',requestId:command.requestId,error,result:error?null:{document:doc}}}));
        };
        function ready(){
          frame.contentWindow.addEventListener('message',event=>{if(event.data.action==='save')window.commands.push(event.data);});
          window.state();window.ready=true;
        }
        if(frame.contentDocument.readyState==='complete')ready();else frame.addEventListener('load',ready,{once:true});
        window.prepare=()=>{
          window.result=undefined;window.failure=undefined;
          toolbar.prepare({document_id:'source',context:[{document_id:doc.id,page_start:1,page_end:1}]}).then(value=>window.result=value).catch(error=>window.failure=error.message);
        };window.hasNotes=()=>toolbar.anyDirty();
        </script>'''

    async def check():
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page()
                async def local(route):
                    name=route.request.url.rsplit('/',1)[-1]
                    await route.fulfill(content_type='text/javascript' if name.endswith('.js') else 'text/html',
                        body=(static/name).read_text() if name.endswith('.js') else html)
                await page.route('**/*',local)
                await page.goto('http://localhost/')
                await page.wait_for_function('window.ready')
                await page.evaluate('window.prepare()')
                assert 'Context - annotated.pdf' in await page.locator('#annotation-choice-message').inner_text()
                await page.get_by_role('button',name='Cancel',exact=True).click()
                await page.wait_for_function('window.result===null')
                assert await page.evaluate('window.hasNotes()')
                await page.evaluate('window.prepare()')
                await page.get_by_role('button',name='Use original PDF',exact=True).click()
                await page.wait_for_function('window.result')
                assert await page.evaluate('window.result.context[0].document_id')=='context-original'
                assert await page.evaluate('window.hasNotes()')
                await page.evaluate('window.prepare()')
                await page.get_by_role('button',name='Save and use edited copy',exact=True).click()
                await page.wait_for_function('window.commands.length===1')
                assert await page.evaluate('window.result===undefined')
                await page.evaluate("window.finishSave('Simulated save conflict')")
                await page.wait_for_function('window.failure')
                assert await page.evaluate('window.failure')=='Simulated save conflict'
                assert await page.evaluate('window.result===undefined && window.hasNotes()')
                await page.evaluate('window.prepare()')
                await page.get_by_role('button',name='Save and use edited copy',exact=True).click()
                await page.wait_for_function('window.commands.length===2')
                await page.evaluate('window.finishSave()')
                await page.wait_for_function('window.result')
                assert await page.evaluate('window.result.context[0].document_id')=='context-copy'
            finally:await browser.close()
    asyncio.run(check())
