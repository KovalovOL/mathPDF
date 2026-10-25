"""Isolated layout component checks; no account or application UI is loaded."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from formula_lab.pdf_export import chromium_executable


def test_source_collapse_and_mobile_pull_preserve_the_viewer():
    static = Path(__file__).parents[1] / 'formula_lab/static'
    html = '''<!doctype html><link rel="stylesheet" href="/style.css">
        <header class="app-header">Layout component</header>
        <main id="workspace" class="workspace">
          <section id="document-pane" class="pane"><button id="hide-source">Hide viewer</button>
            <iframe title="Retained document" src="about:blank"></iframe></section>
          <div id="splitter" tabindex="0"></div>
          <section id="practice-pane" class="pane"><button id="show-source">Show viewer</button>
            <div class="practice-content"><div id="answer" style="height:1600px;flex-shrink:0">Long answer</div></div>
          </section>
        </main><script type="module">
        import {createWorkspaceLayout} from '/workspace-layout.js';
        const values = new Map();
        window.layout = createWorkspaceLayout({preference:(key,value)=>{
          if(value!==undefined)values.set(key,String(value)); return values.get(key);
        },onViewport:()=>{}});
        window.initialFrame = document.querySelector('iframe');
        window.ready = true;
        </script>'''

    async def check():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, executable_path=chromium_executable())
            try:
                page = await browser.new_page(viewport={'width':390,'height':844}, has_touch=True)

                async def local(route):
                    name = route.request.url.rsplit('/',1)[-1]
                    if name in {'workspace-layout.js','style.css'}:
                        await route.fulfill(content_type='text/javascript' if name.endswith('.js') else 'text/css',
                                            body=(static/name).read_text())
                    else:
                        await route.fulfill(content_type='text/html', body=html)
                await page.route('**/*', local)
                await page.goto('http://layout.local/')
                await page.wait_for_function('window.ready')
                await page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
                await page.wait_for_function("document.querySelector('#workspace').classList.contains('source-collapsed')")

                async def pull(target='#answer', horizontal=0):
                    return await page.evaluate('''({target,horizontal})=>{
                        const element=document.querySelector(target);
                        function send(type,x,y){
                            const touch=new Touch({identifier:1,target:element,clientX:x,clientY:y});
                            return element.dispatchEvent(new TouchEvent(type,{bubbles:true,cancelable:true,touches:[touch]}));
                        }
                        send('touchstart',100,140); send('touchmove',100+horizontal,230);
                        element.dispatchEvent(new TouchEvent('touchend',{bubbles:true,touches:[]}));
                        return document.querySelector('#workspace').classList.contains('source-collapsed');
                    }''', {'target':target,'horizontal':horizontal})

                # A horizontal gesture or interaction with the restore button must not steal a scroll.
                assert await pull(horizontal=70)
                assert await pull('#show-source')
                # A long answer first scrolls to its own top before a pull may restore the PDF.
                await page.evaluate("document.querySelector('.practice-content').scrollTop=100")
                assert await pull()
                await page.evaluate("document.querySelector('.practice-content').scrollTop=0")
                assert not await pull()
                assert await page.evaluate("document.querySelector('iframe')===window.initialFrame")
                await page.locator('#hide-source').click()
                await page.locator('#show-source').click()
                assert await page.locator('#document-pane').get_attribute('aria-hidden') == 'false'
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')

                await page.set_viewport_size({'width':1280,'height':720})
                await page.locator('#splitter').press('Home')
                assert await page.locator('#document-pane').get_attribute('aria-hidden') == 'true'
                await page.locator('#show-source').click()
                assert await page.locator('#document-pane').get_attribute('aria-hidden') == 'false'
                assert await page.evaluate("document.querySelector('iframe')===window.initialFrame")
            finally:
                await browser.close()
    asyncio.run(check())
