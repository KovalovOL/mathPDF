"""Welcome persistence and native dialog behavior with synthetic accounts."""
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient
from formula_lab.app import create_app
from test_app import sign_in


def test_welcome_once_per_account_and_restart(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        assert client.post('/api/welcome/claim').status_code == 401
        sign_in(client, app)
        assert client.get('/api/me').json()['welcome_pending']
        assert client.post('/api/welcome/claim').json() == {'show': True}
        assert client.post('/api/welcome/claim').json() == {'show': False}
        sign_in(client, app)
        assert not client.get('/api/me').json()['welcome_pending']
        sign_in(client, app, 'other')
        assert client.get('/api/me').json()['welcome_pending']
        client.headers['Origin'] = 'https://other.invalid'
        assert client.post('/api/welcome/claim').status_code == 403
    restarted = create_app(tmp_path)
    with TestClient(restarted) as client:
        sign_in(client, restarted)
        assert client.post('/api/welcome/claim').json() == {'show': False}
        # Accounts predating the feature have no receipt and are not interrupted.
        with restarted.state.workspace.connection() as db:
            db.execute('DELETE FROM welcome_receipts')
        sign_in(client, restarted)
        assert client.post('/api/welcome/claim').json() == {'show': False}


def test_welcome_desktop_mobile_and_dismissal():
    from playwright.async_api import async_playwright
    from formula_lab.pdf_export import chromium_executable
    static = Path(__file__).parents[1]/'formula_lab/static'
    async def check():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, executable_path=chromium_executable())
            try:
                for width in [1280, 320]:
                    page = await browser.new_page(viewport={'width':width,'height':800})
                    await page.set_content('<button id="before">Upload PDF</button>')
                    await page.add_style_tag(content=(static/'style.css').read_text(encoding='utf-8'))
                    await page.add_script_tag(content=(static/'welcome.js').read_text(encoding='utf-8').replace('export async function','async function'))
                    await page.locator('#before').focus()
                    await page.evaluate('showWelcome({api:async()=>({show:true})})')
                    assert await page.get_by_role('dialog', name='Welcome to MathPDF!').is_visible()
                    assert await page.get_by_role('button', name='Start learning').evaluate('(e)=>e===document.activeElement')
                    assert await page.evaluate('document.querySelector("dialog").getBoundingClientRect().width<=innerWidth')
                    out = Path('output');out.mkdir(exist_ok=True)
                    await page.screenshot(path=str(out/f'welcome-{width}.png'))
                    await page.keyboard.press('Escape')
                    await page.locator('dialog').wait_for(state='detached')
                    assert await page.locator('dialog').count() == 0
                    assert await page.locator('#before').evaluate('(e)=>e===document.activeElement')
                    await page.evaluate('showWelcome({api:async()=>({show:false})})')
                    assert await page.locator('dialog').count() == 0
                    for button in ['Close welcome','Start learning']:
                        await page.evaluate('showWelcome({api:async()=>({show:true})})')
                        await page.get_by_role('button',name=button,exact=True).click()
                        await page.locator('dialog').wait_for(state='detached')
                        assert await page.locator('dialog').count() == 0
                    await page.close()
            finally: await browser.close()
    asyncio.run(check())
