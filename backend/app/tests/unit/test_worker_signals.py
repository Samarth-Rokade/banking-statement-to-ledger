import threading
import time

from app.jobs import signals
from app.jobs.worker import run_worker_loop


def test_wake_worker_sets_the_wake_event():
    signals.wake_event.clear()
    signals.wake_worker()
    assert signals.wake_event.is_set()
    signals.wake_event.clear()


def test_run_worker_loop_stops_promptly_when_stop_event_is_set(monkeypatch):
    call_count = 0

    def fake_run_once() -> bool:
        nonlocal call_count
        call_count += 1
        return False  # nothing to do - loop should idle-wait, not spin

    monkeypatch.setattr("app.jobs.worker.run_once", fake_run_once)
    signals.stop_event.clear()
    signals.wake_event.clear()

    thread = threading.Thread(target=run_worker_loop, args=(30.0,), daemon=True)
    thread.start()
    time.sleep(0.1)  # let it enter the idle wait
    signals.stop_event.set()
    signals.wake_worker()  # interrupt the 30s wait - without this the join would hang
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert call_count >= 1
    signals.stop_event.clear()
    signals.wake_event.clear()


def test_run_worker_loop_wake_event_interrupts_the_wait_immediately(monkeypatch):
    call_count = 0

    def fake_run_once() -> bool:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            signals.stop_event.set()
        return False

    monkeypatch.setattr("app.jobs.worker.run_once", fake_run_once)
    signals.stop_event.clear()
    signals.wake_event.clear()

    thread = threading.Thread(target=run_worker_loop, args=(30.0,), daemon=True)
    started_at = time.monotonic()
    thread.start()
    time.sleep(0.05)
    signals.wake_worker()  # should make the loop re-check almost immediately, not wait 30s
    thread.join(timeout=2)
    elapsed = time.monotonic() - started_at

    assert not thread.is_alive()
    assert elapsed < 2
    assert call_count == 2
    signals.stop_event.clear()
    signals.wake_event.clear()
