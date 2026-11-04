"""Eventbus: toestandswissels, abonnees en het during()-blok."""

import asyncio

import pytest

from hud.events import EventBus, HudState


@pytest.fixture
def bus():
    return EventBus()


def test_begint_in_rust(bus):
    assert bus.state is HudState.IDLE


def test_toestandswissel_bereikt_abonnee(bus):
    async def scenario():
        with bus.subscribe() as queue:
            await bus.set_state(HudState.THINKING)
            return await asyncio.wait_for(queue.get(), 1)

    msg = asyncio.run(scenario())
    assert msg == {"type": "state", "value": "thinking"}


def test_zelfde_toestand_stuurt_niets(bus):
    async def scenario():
        with bus.subscribe() as queue:
            await bus.set_state(HudState.IDLE)   # al de huidige toestand
            return queue.empty()

    assert asyncio.run(scenario()) is True


def test_during_valt_terug_op_rust(bus):
    async def scenario():
        gezien = []
        with bus.subscribe() as queue:
            async with bus.during(HudState.SPEAKING):
                gezien.append(bus.state)
            while not queue.empty():
                gezien.append(queue.get_nowait()["value"])
        return gezien

    gezien = asyncio.run(scenario())
    assert gezien[0] is HudState.SPEAKING
    assert gezien[-1] == "idle"


def test_abonnee_verdwijnt_na_het_blok(bus):
    async def scenario():
        with bus.subscribe():
            tijdens = bus.listener_count
        return tijdens, bus.listener_count

    tijdens, erna = asyncio.run(scenario())
    assert (tijdens, erna) == (1, 0)


def test_trage_abonnee_blokkeert_de_bus_niet(bus):
    async def scenario():
        with bus.subscribe() as queue:
            for i in range(EventBus.MAX_QUEUE + 25):
                await bus.publish("token", {"text": str(i)})
            return queue.qsize()

    # De wachtrij loopt vol en laat frames vallen in plaats van te blokkeren.
    assert asyncio.run(scenario()) == EventBus.MAX_QUEUE


# --- thread-veilige kant (de spraaklus draait in een eigen thread) ----------

def test_publiceren_vanuit_thread_bereikt_de_browser(bus):
    import threading

    async def scenario():
        bus.bind_loop(asyncio.get_running_loop())
        with bus.subscribe() as queue:
            t = threading.Thread(
                target=lambda: bus.publish_from_thread("level", {"value": 0.7}))
            t.start(); t.join()
            return await asyncio.wait_for(queue.get(), 2)

    assert asyncio.run(scenario()) == {"type": "level", "value": 0.7}


def test_toestand_vanuit_thread(bus):
    import threading

    async def scenario():
        bus.bind_loop(asyncio.get_running_loop())
        with bus.subscribe() as queue:
            t = threading.Thread(
                target=lambda: bus.set_state_from_thread(HudState.LISTENING))
            t.start(); t.join()
            return await asyncio.wait_for(queue.get(), 2)

    assert asyncio.run(scenario()) == {"type": "state", "value": "listening"}


def test_zonder_gekoppelde_lus_valt_er_niets_om(bus):
    # Publiceren voordat de server draait mag geen uitzondering geven.
    bus.publish_from_thread("level", {"value": 0.5})
    bus.set_state_from_thread(HudState.SPEAKING)
    assert bus.state is HudState.SPEAKING
