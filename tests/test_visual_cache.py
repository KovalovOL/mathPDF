"""Exercise the IndexedDB module in an isolated browser runtime, without app UI."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from formula_lab.pdf_export import chromium_executable


def test_visual_cache_is_private_bounded_content_keyed_and_invalidated():
    source = (Path(__file__).parents[1] / 'formula_lab/static/visual-cache.js').read_text()

    async def check():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, executable_path=chromium_executable())
            try:
                page = await browser.new_page()

                async def local(route):
                    if route.request.url.endswith('/cache.js'):
                        await route.fulfill(content_type='text/javascript', body=source)
                    else:
                        await route.fulfill(content_type='text/html', body='<!doctype html><title>Storage unit test</title>')
                await page.route('**/*', local)
                await page.goto('http://cache.local/')
                result = await page.evaluate(r'''async()=>{
                    const {createVisualCache,clearVisualCache}=await import('/cache.js');
                    const file={id:'file-one',sha256:'original'}, cache=createVisualCache('owner-one');
                    for(let page=1;page<=10;page++) {
                        await cache.put(file,'page',page,{blob:new Blob(['page'+page]),ratio:1.4});
                        await new Promise(resolve=>setTimeout(resolve,2));
                    }
                    await cache.get(file,'page',1);
                    await new Promise(resolve=>setTimeout(resolve,3));
                    await cache.put(file,'page',11,{blob:new Blob(['page11']),ratio:1.4});
                    const count=(await cache.pages(file)).length;
                    const recent=!!await cache.get(file,'page',1), oldest=!!await cache.get(file,'page',2);
                    const other=await createVisualCache('owner-two').get(file,'page',1);
                    const changed=await cache.get({...file,sha256:'changed'},'page',1);
                    await cache.put(file,'preview',1,{text:'Cached excerpt'});
                    const preview=(await cache.get(file)).text;
                    await clearVisualCache('owner-one',file.id);
                    await cache.put(file,'preview',1,{text:'Late write must not restore a deleted file'});
                    const deleted=await cache.get(file);
                    const second={id:'file-two',sha256:'original'};
                    await cache.put(second,'preview',1,{text:'Second file'});
                    await clearVisualCache('owner-one');
                    await cache.put(second,'preview',1,{text:'Late write after sign-out'});
                    return {count,recent,oldest,other,changed,preview,deleted,
                            signedOut:await cache.get(second)};
                }''')
                assert result == {'count':10,'recent':True,'oldest':False,'other':None,'changed':None,
                                  'preview':'Cached excerpt','deleted':None,'signedOut':None}
                await page.close()
                unavailable = await browser.new_page()
                await unavailable.route('**/*', local)
                await unavailable.goto('http://cache.local/')
                result = await unavailable.evaluate(r'''async()=>{
                    Object.defineProperty(window,'indexedDB',{value:{open(){throw new Error('Storage disabled');}}});
                    const {createVisualCache}=await import('/cache.js'), cache=createVisualCache('owner');
                    const file={id:'file',sha256:'hash'};
                    await cache.put(file,'preview',1,{text:'No storage'});
                    return {entry:await cache.get(file),pages:await cache.pages(file)};
                }''')
                assert result == {'entry':None,'pages':[]}
            finally:
                await browser.close()
    asyncio.run(check())
