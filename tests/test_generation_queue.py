"""Synthetic queue lifecycle checks: no external provider or user data."""
import asyncio
from types import SimpleNamespace
import pytest
from formula_lab.generation_jobs import GenerationJobs, GenerationBusy


def test_fifo_cancellation_failure_and_ownership(monkeypatch):
    async def check():
        gates = {name: asyncio.Event() for name in ['a','b','c','d']}
        entered = []
        async def generate(workspace, owner, selection, provider, progress):
            entered.append(owner)
            await gates[owner].wait()
            if owner == 'b':
                raise ValueError('Synthetic failure')
            return SimpleNamespace(items=[])
        monkeypatch.setattr('formula_lab.generation_jobs.generate_study', generate)
        jobs = GenerationJobs(SimpleNamespace(), asyncio.Lock())
        selection = SimpleNamespace(count=1, mode='flashcards')
        a = await jobs.start('a', selection, None)
        await asyncio.sleep(0)
        b = await jobs.start('b', selection, None)
        c = await jobs.start('c', selection, None)
        d = await jobs.start('d', selection, None)
        assert jobs.get(d.id, 'd').snapshot()['queue_position'] == 3
        assert d.status == 'running' and d.phase == 'queued'
        with pytest.raises(KeyError): jobs.get(a.id, 'b')
        with pytest.raises(GenerationBusy): await jobs.start('a', selection, None)
        await jobs.cancel(c.id, 'c')  # Before task starts: must not release a's lock.
        await asyncio.sleep(0)
        assert jobs.lock.locked() and entered == ['a']
        assert jobs.get(d.id, 'd').queue_position == 2
        gates['a'].set()
        await a.task
        await asyncio.sleep(0)
        assert entered == ['a','b']
        gates['b'].set()
        await b.task
        await asyncio.sleep(0)
        assert entered == ['a','b','d'] and b.status == 'failed'
        gates['d'].set()
        await d.task
        assert not jobs.lock.locked() and d.status == 'completed'
        await jobs.close()
    asyncio.run(check())


def test_waiting_cancel_capacity_and_close(monkeypatch):
    async def check():
        lock = asyncio.Lock()
        await lock.acquire()  # Legacy synchronous generation holds the same lock.
        jobs = GenerationJobs(SimpleNamespace(), lock)
        jobs.max_pending = 2
        selection = SimpleNamespace(count=1, mode='flashcards')
        a = await jobs.start('a', selection, None)
        b = await jobs.start('b', selection, None)
        await asyncio.sleep(0)
        with pytest.raises(GenerationBusy): await jobs.start('c', selection, None)
        await jobs.cancel(a.id, 'a')
        assert lock.locked() and a.status == 'cancelled'
        await jobs.close()
        assert b.status == 'cancelled' and lock.locked()
        lock.release()
    asyncio.run(check())


def test_active_cancel_releases_next_job(monkeypatch):
    async def check():
        entered = []
        async def generate(workspace, owner, selection, provider, progress):
            entered.append(owner)
            await asyncio.Event().wait()
        monkeypatch.setattr('formula_lab.generation_jobs.generate_study', generate)
        jobs = GenerationJobs(SimpleNamespace(), asyncio.Lock())
        selection = SimpleNamespace(count=1, mode='flashcards')
        a = await jobs.start('a', selection, None)
        b = await jobs.start('b', selection, None)
        await asyncio.sleep(0)
        await jobs.cancel(a.id, 'a')
        await asyncio.sleep(0)
        assert entered == ['a','b'] and a.status == 'cancelled'
        await jobs.close()
        assert not jobs.lock.locked()
    asyncio.run(check())


def test_queue_ui_refreshes_waiting_deadline():
    from pathlib import Path
    from playwright.async_api import async_playwright
    from formula_lab.pdf_export import chromium_executable
    source = (Path(__file__).parents[1]/'formula_lab/static/app.js').read_text(encoding='utf-8')
    deadline = source[source.index('  let deadline;'):source.index('  let jobId, terminal')]
    progress = source[source.index('  function showProgress(job)'):source.index('  function pollDelay()')]
    async def check():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, executable_path=chromium_executable())
            try:
                page = await browser.new_page()
                await page.clock.install()
                await page.set_content('<div id="generation-progress-detail" role="status"></div>')
                await page.add_script_tag(content="const $=id=>document.getElementById(id); const config={generation_timeout_seconds:150}; const controller=new AbortController(); window.controller=controller;"+deadline+progress+'window.showProgress=showProgress;')
                await page.evaluate("showProgress({phase:'queued',queue_position:2})")
                assert 'Requests ahead: 2' in await page.locator('[role=status]').inner_text()
                await page.clock.fast_forward(170000)
                await page.evaluate("showProgress({phase:'queued',queue_position:1})")
                await page.clock.fast_forward(170000)
                assert not await page.evaluate('controller.signal.aborted')
                await page.evaluate("showProgress({phase:'generating'})")
                assert await page.locator('[role=status]').inner_text() == 'Generating your study set…'
                await page.clock.fast_forward(11000)
                assert await page.evaluate('controller.signal.aborted')
            finally:
                await browser.close()
    asyncio.run(check())
