"""Touch gestures and compact card layout use isolated synthetic content."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from formula_lab.pdf_export import chromium_executable


def test_workspace_entrypoint_parses_as_the_classic_script_served_by_index():
    """The workspace deliberately uses dynamic imports from its classic entrypoint."""
    static=Path(__file__).parents[1]/'formula_lab/static'
    assert '<script src="/static/app.js" defer>' in (static/'index.html').read_text()
    async def check():
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page()
                await page.evaluate('(source)=>{new Function(source);}',(static/'app.js').read_text())
            finally:await browser.close()
    asyncio.run(check())


def test_touch_card_does_not_select_text_or_flip_during_scroll_and_fits_width():
    static=Path(__file__).parents[1]/'formula_lab/static'
    html='''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/style.css">
    <main class="practice-content" style="height:calc(100dvh - 16px);width:calc(100vw - 16px);margin:8px;padding:10px">
    <div class="deck"><section class="flashcard" tabindex="0"><div class="card-inner"><div class="card-face card-front"><div class="card-body"><p id="text" class="text-block">Question with a very long unbroken word: LONGWORD</p><a href="#source">Source page 1</a></div></div><div class="card-face card-back"><div class="card-body">Answer</div></div></div></section>
    <div class="deck-footer"><button class="icon-button" aria-label="Previous card">‹</button><div class="deck-footer-center"><div class="review-controls"><div class="review-actions"><button class="review-incorrect">✕ Incorrect</button><button class="review-correct">✓ Correct</button></div></div></div><button class="icon-button" aria-label="Next card">›</button></div></div></main>
    <script type="module">import {wireFlashcard} from '/static/card-interaction.js';window.flips=0;window.moves=0;const card=document.querySelector('.flashcard');wireFlashcard(card,{flip:()=>window.flips++,previous:()=>window.moves--,next:()=>window.moves++});window.ready=true;</script>'''.replace('LONGWORD','variable'*100)
    async def check():
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page(viewport={'width':320,'height':740},has_touch=True)
                async def local(route):
                    name=route.request.url.rsplit('/',1)[-1]
                    await route.fulfill(body=(static/name).read_text() if name in ['style.css','card-interaction.js'] else html,content_type='text/css' if name=='style.css' else 'text/javascript' if name.endswith('.js') else 'text/html')
                await page.route('**/*',local);await page.goto('http://cards.local/');await page.wait_for_function('window.ready')
                assert await page.locator('#text').evaluate('(e)=>getComputedStyle(e).userSelect')=='none'
                await page.locator('#text').tap();assert await page.evaluate('window.flips')==1
                assert await page.evaluate('getSelection().toString()')==''
                await page.locator('.flashcard').dispatch_event('pointerdown',{'pointerType':'touch','isPrimary':True,'clientX':50,'clientY':50})
                await page.locator('.flashcard').dispatch_event('pointermove',{'pointerType':'touch','clientX':50,'clientY':95})
                await page.locator('.flashcard').dispatch_event('click')
                assert await page.evaluate('window.flips')==1
                await page.get_by_role('link',name='Source page 1').tap();assert await page.evaluate('window.flips')==1
                await page.locator('.flashcard').focus();await page.keyboard.press('Space');assert await page.evaluate('window.flips')==2
                await page.keyboard.press('ArrowRight');assert await page.evaluate('window.moves')==1
                assert await page.get_by_role('button',name='Flip card',exact=True).count()==0
                assert await page.get_by_role('progressbar').count()==0
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                rect=await page.locator('.deck-footer').bounding_box();assert rect['x']>=0 and rect['x']+rect['width']<=320
                assert rect['y']+rect['height']<=740
            finally:await browser.close()
    asyncio.run(check())
