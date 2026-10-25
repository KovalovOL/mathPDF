"""Isolated source-viewer runtime with a delayed PDF and corrupted derived image."""
import asyncio
import io
import mimetypes
from pathlib import Path

from playwright.async_api import async_playwright
from pypdf import PdfWriter

from formula_lab.pdf_export import chromium_executable


def test_initial_pdf_queue_starts_and_replaces_an_invalid_cached_page():
    static = Path(__file__).parents[1] / 'formula_lab/static'
    writer, data = PdfWriter(), io.BytesIO()
    writer.add_blank_page(width=600, height=800); writer.write(data)
    html = '''<!doctype html><style>
        body{margin:0}#pages{width:100%}.pdf-page{margin:12px}.pdf-sheet{position:relative}
        canvas,.cached-page{position:absolute;width:100%;height:100%}
        </style><p id="status">Loading</p><div id="pages"></div><script type="module">
        const file={id:'viewer-file',sha256:'original',page_count:1};
        window.MathPDFSession={ready:Promise.resolve({id:'viewer-owner'}),api:async()=>file};
        const {createVisualCache}=await import('/static/visual-cache.js');
        await createVisualCache('viewer-owner').put(file,'page',1,
          {blob:new Blob(['invalid persisted image'],{type:'image/png'}),ratio:4/3,baseWidth:600});
        await import('/static/pdf-viewer.js');
        </script>'''

    async def check():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, executable_path=chromium_executable())
            try:
                page = await browser.new_page(viewport={'width':700,'height':850})

                async def local(route):
                    path = route.request.url.split('viewer.local',1)[1].split('?',1)[0]
                    if path.startswith('/static/'):
                        file = (static/path.removeprefix('/static/')).resolve()
                        assert file.is_relative_to(static.resolve())
                        await route.fulfill(content_type=mimetypes.guess_type(file)[0] or 'application/octet-stream', body=file.read_bytes())
                    elif path == '/api/documents/viewer-file/file':
                        # Initial jump queues pages before the parser completes, without resize events.
                        await asyncio.sleep(.3)
                        await route.fulfill(content_type='application/pdf', body=data.getvalue())
                    else:
                        await route.fulfill(content_type='text/html', body=html)
                await page.route('**/*', local)
                await page.goto('http://viewer.local/?document=viewer-file')
                await page.locator('#pages canvas[role=img]').wait_for(timeout=10000)
                assert await page.locator('#pages img').count() == 0
                assert await page.locator('#status').is_hidden()
                await page.wait_for_function('''async()=>{
                    const {createVisualCache}=await import('/static/visual-cache.js');
                    const entry=await createVisualCache('viewer-owner').get({id:'viewer-file',sha256:'original'},'page',1);
                    return entry?.bytes?.byteLength>100;
                }''')
            finally:
                await browser.close()
    asyncio.run(check())
