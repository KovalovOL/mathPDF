"""Isolated leave dialog waits for saves and retains failed/canceled work."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from formula_lab.pdf_export import chromium_executable


def test_leave_confirmation_saves_all_and_preserves_failures():
    static=Path(__file__).parents[1]/'formula_lab/static'
    html='''<!doctype html><button id="leave">Home</button><script type="module">
        import {createLeaveGuard} from '/static/leave-guard.js';
        window.items=['Lecture.pdf · Unsaved notes','Practice · Unsaved study set'];window.saved=0;
        const guard=createLeaveGuard({pending:()=>window.items,save:async()=>{
          window.saved++;await new Promise(resolve=>window.finishSave=resolve);
          if(window.fail)throw new Error('Save failed; local notes retained.');window.items=[];
        }});
        document.querySelector('#leave').onclick=()=>{window.result=undefined;guard.confirm().then(value=>window.result=value);};
        window.unloadBlocked=()=>{const event=new Event('beforeunload',{cancelable:true});dispatchEvent(event);return event.defaultPrevented;};
        window.ready=true;
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
                await page.route('**/*',local);await page.goto('http://localhost/')
                await page.wait_for_function('window.ready')
                assert await page.evaluate('window.unloadBlocked()')
                await page.get_by_role('button',name='Home',exact=True).click()
                assert await page.locator('#leave-dialog li').count()==2
                await page.get_by_role('button',name='Cancel',exact=True).click()
                await page.wait_for_function('window.result===false')
                assert await page.evaluate('window.items.length')==2
                await page.get_by_role('button',name='Home',exact=True).click()
                await page.evaluate('window.fail=true')
                await page.get_by_role('button',name='Save and leave',exact=True).click()
                assert await page.get_by_role('button',name='Leave without saving',exact=True).is_disabled()
                assert await page.evaluate('window.result===undefined')
                await page.keyboard.press('Escape')
                assert await page.locator('#leave-dialog').is_visible()
                await page.evaluate('window.finishSave()')
                await page.get_by_role('alert').wait_for()
                assert await page.evaluate('window.result===undefined && window.items.length===2')
                assert await page.locator('#leave-dialog').is_visible()
                await page.evaluate('window.fail=false')
                await page.get_by_role('button',name='Save and leave',exact=True).click()
                await page.evaluate('window.finishSave()')
                await page.wait_for_function('window.result===true')
                assert await page.evaluate('window.saved')==2
                assert not await page.evaluate('window.unloadBlocked()')
                # A later canceled departure can never silently discard pending work.
                await page.evaluate("dispatchEvent(new Event('pageshow'));window.items=['Another PDF'];")
                await page.get_by_role('button',name='Home',exact=True).click()
                await page.get_by_role('button',name='Leave without saving',exact=True).click()
                await page.wait_for_function('window.result===true')
                assert await page.evaluate('window.items.length')==1
            finally:await browser.close()
    asyncio.run(check())
