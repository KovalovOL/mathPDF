"""FIFO generation queue lifecycle with an in-memory fake generator."""
import asyncio
from types import SimpleNamespace
import pytest
from app.generation.jobs import GenerationBusy, GenerationJobs


def test_fifo_queue_cancellation_ownership_and_capacity():
    async def scenario():
        gates = {name: asyncio.Event() for name in "abd"}
        entered = []

        class Generator:
            async def execute(self, owner, selection, provider, progress):
                entered.append(owner)
                await gates[owner].wait()
                if owner == "b":
                    raise ValueError("Synthetic failure")
                return SimpleNamespace(items=[])

        class Incidents:
            async def execute(self, *args):
                return None

        lock = asyncio.Lock()
        jobs = GenerationJobs(Generator(), lock, Incidents())
        selection = SimpleNamespace(count=1, mode="flashcards")
        a = await jobs.start("a", selection, None)
        await asyncio.sleep(0)
        b = await jobs.start("b", selection, None)
        c = await jobs.start("c", selection, None)
        d = await jobs.start("d", selection, None)
        assert d.snapshot()["queue_position"] == 3
        with pytest.raises(KeyError):
            jobs.get(a.id, "other")
        with pytest.raises(GenerationBusy):
            await jobs.start("a", selection, None)
        await jobs.cancel(c.id, "c")
        assert lock.locked() and entered == ["a"]
        gates["a"].set()
        await a.task
        await asyncio.sleep(0)
        assert entered == ["a", "b"]
        gates["b"].set()
        await b.task
        await asyncio.sleep(0)
        assert entered == ["a", "b", "d"]
        gates["d"].set()
        await d.task
        assert not lock.locked() and d.status == "completed"
        await jobs.close()

    asyncio.run(scenario())


def test_generation_queue_rejects_over_capacity():
    async def scenario():
        lock = asyncio.Lock()
        await lock.acquire()
        jobs = GenerationJobs(SimpleNamespace(), lock, SimpleNamespace())
        jobs.max_pending = 1
        selection = SimpleNamespace(count=1, mode="flashcards")
        job = await jobs.start("first", selection, None)
        await asyncio.sleep(0)
        with pytest.raises(GenerationBusy):
            await jobs.start("second", selection, None)
        await jobs.cancel(job.id, "first")
        assert lock.locked()
        lock.release()

    asyncio.run(scenario())
