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


def test_image_bytes_legacy_blob_migration_and_decode_recovery():
    static = Path(__file__).parents[1] / 'formula_lab/static'
    source = (static / 'visual-cache.js').read_text()

    async def check():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, executable_path=chromium_executable())
            try:
                page = await browser.new_page()

                async def local(route):
                    await route.fulfill(content_type='text/javascript' if route.request.url.endswith('.js') else 'text/html',
                                        body=(static/'file-previews.js').read_text() if route.request.url.endswith('file-previews.js')
                                        else source if route.request.url.endswith('.js') else '<title>Cache recovery component</title>')
                await page.route('**/*', local)
                await page.goto('http://cache.local/')
                result = await page.evaluate(r'''async()=>{
                    const {createVisualCache,cachedImage,canvasBlob}=await import('/cache.js');
                    const cache=createVisualCache('image-owner'), file={id:'image-file',sha256:'original'};
                    const canvas=document.createElement('canvas'); canvas.width=20; canvas.height=30;
                    canvas.getContext('2d').fillRect(0,0,20,30);
                    const blob=await canvasBlob(canvas);
                    await cache.put(file,'preview',1,{blob});
                    const db=await new Promise(resolve=>{const request=indexedDB.open('mathpdf-visual-cache',1);request.onsuccess=()=>resolve(request.result);});
                    async function raw(operation){return new Promise(resolve=>{
                        const tx=db.transaction('entries','readwrite'), store=tx.objectStore('entries'); let value;
                        const request=operation(store);request.onsuccess=()=>{value=request.result;};
                        tx.oncomplete=()=>resolve(value);
                    });}
                    const stored=(await raw(store=>store.getAll()))[0];
                    const byteStorage=stored.bytes instanceof ArrayBuffer && !stored.blob;
                    // Seed the exact previous storage shape: no byte buffer or write marker.
                    const legacy={...stored,blob:new Blob([stored.bytes],{type:stored.mediaType})};
                    delete legacy.bytes; delete legacy.written;
                    await raw(store=>store.put(legacy));
                    const restored=await cache.get(file), image=await cachedImage(restored,'Legacy preview');
                    const migrated=await raw(store=>store.get(stored.key));
                    const legacyReadable=image?.image.naturalWidth===20 && image.image.naturalHeight===30 && !migrated.blob && migrated.bytes instanceof ArrayBuffer;
                    if(image)URL.revokeObjectURL(image.url);
                    // Simulate WebKit's unreadable persisted Blob while retaining its metadata.
                    await raw(store=>store.put({...legacy,blob:new Blob(['unreadable-image'])}));
                    const original=Blob.prototype.arrayBuffer;
                    Blob.prototype.arrayBuffer=function(){return this.size===16?Promise.reject(new Error('Unavailable persisted Blob')):original.call(this);};
                    const unreadable=await cache.get(file);
                    Blob.prototype.arrayBuffer=original;
                    const badRemoved=!await raw(store=>store.get(stored.key));
                    await cache.put(file,'preview',1,{blob:new Blob(['not an image'],{type:'image/png'})});
                    const invalid=await cache.get(file), invalidImage=await cachedImage(invalid,'Invalid');
                    await cache.remove(file,'preview',1,invalid);
                    const decodeRemoved=!await cache.get(file);
                    await cache.put(file,'preview',1,{blob});
                    await cache.remove(file,'preview',1,invalid); // Do not delete a newer replacement.
                    const replacement=await cachedImage(await cache.get(file),'Replacement');
                    const replacementReadable=!!replacement;
                    if(replacement)URL.revokeObjectURL(replacement.url);
                    // The actual library consumer must recover from a bad image automatically.
                    const fallbackFile={id:'fallback',sha256:'hash',media_type:'image/png',filename:'example.png'};
                    await cache.put(fallbackFile,'preview',1,{blob:new Blob(['broken'],{type:'image/png'})});
                    const {createFilePreviews}=await import('/static/file-previews.js');
                    const container=document.createElement('div');document.body.append(container);
                    let downloads=0;
                    const renderer=createFilePreviews({userId:'image-owner',request:async()=>{downloads++;return new Response(blob);},onAuthFailure:()=>{}});
                    const ready=new Promise((resolve,reject)=>{
                        const timer=setTimeout(()=>{observer.disconnect();reject(new Error('Preview fallback did not complete'));},5000);
                        const observer=new MutationObserver(()=>{if(container.querySelector('canvas')){
                            clearTimeout(timer);observer.disconnect();resolve();
                        }});observer.observe(container,{childList:true});
                    });
                    renderer.observe(container,fallbackFile);await ready;
                    const fallbackWorks=downloads===1 && !container.querySelector('img') && !!container.querySelector('canvas');
                    renderer.destroy();
                    db.close();
                    return {byteStorage,legacyReadable,unreadable,badRemoved,invalidImage,decodeRemoved,replacementReadable,fallbackWorks};
                }''')
                assert result == {'byteStorage':True,'legacyReadable':True,'unreadable':None,'badRemoved':True,
                                  'invalidImage':None,'decodeRemoved':True,'replacementReadable':True,'fallbackWorks':True}
            finally:
                await browser.close()
    asyncio.run(check())
