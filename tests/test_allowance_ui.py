"""Quota UI uses synthetic payloads only, including expiry and recovery states."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright
from formula_lab.pdf_export import chromium_executable


def test_daily_meter_limit_dialog_and_reset_refresh():
    static=Path(__file__).parents[1]/'formula_lab/static'
    html='''<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/static/style.css">
    <header class="app-header">MathPDF</header><button id="limit">Generate fixture</button><input aria-label="Items" value="10"><textarea aria-label="Comment">Keep my comment.</textarea>
    <script type="module">
    import {createAllowanceUI,createGenerationLimitDialog} from '/static/allowance-ui.js';
    window.fixture={calls:0,adjusted:false,reason:'insufficient',state:{limited:true,daily_tokens:200000,remaining_tokens:20000,remaining_percent:10,reserved_tokens:0,resets_at:new Date(Date.now()+7200000).toISOString()}};
    window.meter=createAllowanceUI({api:async()=>{window.fixture.calls++;return structuredClone(window.fixture.state);}});await window.meter.refresh();
    const dialog=createGenerationLimitDialog({onAdjust:()=>{window.fixture.adjusted=true;document.querySelector('input').focus();}});
    document.querySelector('#limit').onclick=()=>dialog.show({code:'generation_limit',reason:window.fixture.reason,allowance:window.fixture.state,required_percent:20});
    </script>'''
    async def check():
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page(viewport={'width':390,'height':844})
                async def local(route):
                    name=route.request.url.rsplit('/',1)[-1]
                    await route.fulfill(body=(static/name).read_text() if name in ['style.css','allowance-ui.js'] else html,content_type='text/css' if name=='style.css' else 'text/javascript' if name.endswith('.js') else 'text/html')
                await page.clock.install()
                await page.route('**/*',local);await page.goto('http://allowance.local/')
                await page.get_by_text('10% left',exact=True).wait_for()
                meter=page.get_by_role('progressbar',name='Daily generation allowance remaining',exact=True)
                assert await meter.get_attribute('aria-valuenow')=='10'
                assert '10% remaining, 90% used'==await meter.get_attribute('aria-valuetext')
                assert 'Resets in 2h 00m · 00:00 UTC' in await page.locator('.allowance-header').get_attribute('title')
                await page.get_by_role('button',name='Generate fixture').click()
                await page.get_by_role('heading',name='This request needs more allowance').wait_for()
                assert 'Estimated request: 20%' in await page.locator('.allowance-dialog').inner_text()
                await page.get_by_role('button',name='Adjust request',exact=True).click()
                assert not await page.locator('dialog').is_visible()
                assert await page.get_by_label('Items').input_value()=='10'
                assert await page.get_by_label('Comment').input_value()=='Keep my comment.'
                await page.evaluate("window.fixture.reason='exhausted';window.fixture.state.remaining_percent=0;window.fixture.state.remaining_tokens=0")
                await page.get_by_role('button',name='Generate fixture').click()
                await page.get_by_role('heading',name="You've used today's allowance").wait_for()
                await page.evaluate("window.fixture.state.remaining_percent=100;window.fixture.state.remaining_tokens=200000;dispatchEvent(new CustomEvent('mathpdf-allowance-updated',{detail:window.fixture.state}))")
                await page.get_by_role('heading',name='Your allowance is ready').wait_for()
                await page.get_by_role('button',name='Continue',exact=True).click()
                await page.evaluate("window.fixture.reason='disabled';window.fixture.state.daily_tokens=0;window.fixture.state.remaining_percent=0")
                await page.get_by_role('button',name='Generate fixture').click()
                await page.get_by_role('heading',name='Generation is paused for your plan').wait_for()
                assert not await page.get_by_role('button',name='Adjust request',exact=True).is_visible()
                await page.evaluate("window.fixture.state.limited=false;dispatchEvent(new CustomEvent('mathpdf-allowance-updated',{detail:window.fixture.state}))")
                await page.get_by_role('heading',name='Your allowance is ready').wait_for()
                await page.get_by_role('button',name='Close',exact=True).click()
                # Move the local clock beyond reset: the timer refreshes the server state.
                await page.evaluate("window.fixture.state.limited=true;window.fixture.state.daily_tokens=200000;window.fixture.state.remaining_percent=100;window.fixture.state.resets_at=new Date(Date.now()+30000).toISOString()")
                await page.evaluate('window.meter.refresh()');calls=await page.evaluate('window.fixture.calls')
                await page.clock.fast_forward(61000)
                await page.wait_for_function('(old)=>window.fixture.calls>old',arg=calls)
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert '200000' not in await page.locator('.allowance-header').inner_text()
            finally:await browser.close()
    asyncio.run(check())
