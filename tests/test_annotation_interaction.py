"""Isolated annotation component: history, selection, pointer gestures and shortcuts."""
import asyncio
import io
import mimetypes
from pathlib import Path

import pytest
from playwright.async_api import async_playwright
from pypdf import PdfWriter
from pypdf.generic import RectangleObject

from formula_lab.pdf_export import chromium_executable


def test_editable_marks_and_keyboard_history_in_an_isolated_runtime():
    static=Path(__file__).parents[1]/'formula_lab/static'
    html='''<!doctype html><style>
        body{margin:0}.sheet{position:relative;width:600px;height:800px;background:white}
        .annotation-layer{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
        .annotation-layer.drawing{pointer-events:auto;touch-action:none}.textLayer span{position:absolute;left:80px;top:80px;font:20px serif}
        </style><div class="sheet"><div class="textLayer"><span>Source text can be highlighted.</span></div></div>
        <script type="module">
        import {createPdfAnnotations} from '/static/pdf-annotations.js';
        let identifier='original';const document={id:identifier,original_document_id:null};
        window.saved=[];window.states=[];
        window.MathPDFSession={api:async(path,options)=>{
          if(window.failSave)throw new Error('Simulated save failure');
          const request=JSON.parse(options.body);window.saved.push({path,request});
          return {document:{id:'copy',original_document_id:'original'},base_document:{id:'original'},
            copy_document:{id:'copy'},revision:request.expected_revision+1,annotations:{schema_version:1,items:request.items}};
        }};
        window.addEventListener('message',event=>{if(event.data?.type==='annotation-state')window.states.push(event.data);});
        const editor=createPdfAnnotations({state:{document,base_document:document,copy_document:null,revision:0,annotations:{schema_version:1,items:[]}},
          getDocumentId:()=>identifier,saved:(old,result)=>{identifier=result.document.id;},report:text=>{window.error=text;}});
        const sheet=window.document.querySelector('.sheet');
        editor.attach({sheet,number:1},{userUnit:1,getViewport:({scale})=>({width:600*scale,height:800*scale,scale,
          transform:[scale,0,0,-scale,0,800*scale],convertToPdfPoint:(x,y)=>[x/scale,800-y/scale]})});
        window.command=data=>new Promise((resolve,reject)=>{
          const requestId=crypto.randomUUID();const listener=event=>{
            if(event.data?.requestId!==requestId || event.data.type!=='annotation-result')return;
            removeEventListener('message',listener);if(event.data.error)reject(new Error(event.data.error));else resolve();
          };addEventListener('message',listener);postMessage({type:'annotation-command',documentId:identifier,requestId,...data},location.origin);
        });window.ready=true;
        </script>'''

    async def check():
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page(viewport={'width':800,'height':900})
                async def local(route):
                    name=route.request.url.rsplit('/',1)[-1]
                    await route.fulfill(content_type='text/javascript' if name.endswith('.js') else 'text/html',
                                        body=(static/name).read_text() if name.endswith('.js') else html)
                await page.route('**/*',local)
                await page.goto('http://localhost/')
                await page.wait_for_function('window.ready')
                await page.evaluate("window.command({action:'tool',tool:'pen'})")
                await page.mouse.move(150,200);await page.mouse.down();await page.mouse.move(250,250,steps=10);await page.mouse.up()
                assert await page.locator('.annotation-layer polyline').count()==1
                await page.evaluate("window.command({action:'tool',tool:'select'})")
                await page.evaluate('''()=>{
                    const text=document.querySelector('.textLayer span').firstChild,range=document.createRange();
                    range.setStart(text,0);range.setEnd(text,11);getSelection().removeAllRanges();getSelection().addRange(range);
                }''')
                await page.evaluate("window.command({action:'tool',tool:'highlight'})")
                assert await page.locator('.annotation-layer polygon').count()>=1
                await page.keyboard.press('Control+s')
                await page.wait_for_function("window.saved.length===1 && window.states.at(-1).documentId==='copy' && !window.states.at(-1).saving && !window.states.at(-1).dirty")
                result=await page.evaluate('({items:window.saved[0].request.items,dirty:window.states.at(-1).dirty,error:window.error})')
                assert [item['kind'] for item in result['items']]==['ink','highlight']
                assert result['items'][0]['points'][0]==[150,600]
                assert result['dirty'] is False and result['error'] is None
                await page.keyboard.press('Meta+z')
                await page.wait_for_function('window.states.at(-1).dirty')
                assert await page.locator('.annotation-layer polygon').count()==0
                await page.keyboard.press('Control+Shift+z')
                await page.wait_for_function('!window.states.at(-1).dirty')
                await page.evaluate("window.command({action:'tool',tool:'eraser'})")
                await page.mouse.click(200,225)
                assert await page.locator('.annotation-layer polyline').count()==0
                await page.keyboard.press('Control+z')
                assert await page.locator('.annotation-layer polyline').count()==1
                await page.evaluate("window.command({action:'toggle'})")
                assert not await page.locator('.annotation-layer').evaluate("node=>node.classList.contains('drawing')")
                await page.evaluate("window.command({action:'tool',tool:'pen'})")
                await page.mouse.click(300,300)
                await page.evaluate('window.failSave=true')
                error=await page.evaluate("window.command({action:'save'}).catch(error=>error.message)")
                assert error=='Simulated save failure'
                await page.wait_for_function('window.states.at(-1).dirty && !window.states.at(-1).saving')
                assert await page.locator('.annotation-layer circle').count()==1
                assert await page.evaluate('window.saved.length')==1
                await page.evaluate("window.failSave=false;window.command({action:'save'})")
                await page.wait_for_function('window.saved.length===2 && !window.states.at(-1).dirty')
                assert await page.evaluate('window.saved[1].request.expected_revision')==1
            finally:
                await browser.close()
    asyncio.run(check())


@pytest.mark.parametrize('rotation',[0,90,180,270])
def test_real_pdf_viewport_keeps_marks_aligned_after_resize(rotation):
    static=Path(__file__).parents[1]/'formula_lab/static'
    writer=PdfWriter();sheet=writer.add_blank_page(width=600,height=800)
    sheet.cropbox=RectangleObject([100,100,500,700]);sheet.rotate(rotation)
    binary=io.BytesIO();writer.write(binary)
    html='''<!doctype html><style>
        *{box-sizing:border-box}body{margin:0;padding:12px}.pdf-page{margin:0 0 12px}.pdf-sheet{position:relative}
        canvas{position:absolute;width:100%;height:100%}.annotation-layer{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:4}
        .annotation-layer.drawing{pointer-events:auto;touch-action:none}
        </style><p id="status">Loading</p><div id="pages"></div><script type="module">
        const file={id:'original',sha256:'source',page_count:1};window.saved=[];
        window.MathPDFSession={ready:Promise.resolve({id:'viewer-owner'}),api:async(path,options)=>{
          if(options){window.saved.push(JSON.parse(options.body));return {document:{...file,id:'copy',original_document_id:'original'},
            base_document:file,copy_document:{id:'copy'},revision:1,annotations:window.saved.at(-1)};}
          if(path.endsWith('/annotations'))return {document:file,base_document:file,copy_document:null,revision:0,annotations:{schema_version:1,items:[]}};
          return file;
        }};
        await import('/static/pdf-viewer.js');
        </script>'''

    async def check():
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page(viewport={'width':700,'height':850})
                async def local(route):
                    path=route.request.url.split('localhost',1)[1].split('?',1)[0]
                    if path.startswith('/static/'):
                        file=(static/path.removeprefix('/static/')).resolve()
                        assert file.is_relative_to(static.resolve())
                        await route.fulfill(content_type=mimetypes.guess_type(file)[0] or 'application/octet-stream',body=file.read_bytes())
                    elif path=='/api/documents/original/file':
                        await route.fulfill(content_type='application/pdf',body=binary.getvalue())
                    else:await route.fulfill(content_type='text/html',body=html)
                await page.route('**/*',local)
                await page.goto('http://localhost/?document=original')
                await page.locator('.annotation-layer').wait_for()
                await page.evaluate("postMessage({type:'annotation-command',documentId:'original',action:'tool',tool:'pen'},location.origin)")
                await page.wait_for_function("document.querySelector('.annotation-layer').classList.contains('drawing')")
                # A fixed PDF-space point must map to the same source position at every rotation.
                start=await page.evaluate("(()=>{const p=new DOMPoint(200,300).matrixTransform(document.querySelector('.annotation-layer g').getScreenCTM());return {x:p.x,y:p.y};})()")
                await page.mouse.click(start['x'],start['y'])
                await page.keyboard.press('Control+s')
                await page.wait_for_function('window.saved.length===1')
                point=await page.evaluate('window.saved[0].items[0].points[0]')
                assert point==pytest.approx([200,300],abs=.01)
                await page.set_viewport_size({'width':480,'height':850})
                await page.wait_for_function('Math.abs(document.querySelector(".pdf-sheet").getBoundingClientRect().width-456)<1')
                actual=await page.locator('.annotation-layer circle').evaluate('''node=>{
                    const p=new DOMPoint(node.cx.baseVal.value,node.cy.baseVal.value).matrixTransform(node.getScreenCTM());
                    const target=new DOMPoint(200,300).matrixTransform(node.parentNode.getScreenCTM());
                    return Math.hypot(p.x-target.x,p.y-target.y);
                }''')
                assert actual<.01
            finally:await browser.close()
    asyncio.run(check())
