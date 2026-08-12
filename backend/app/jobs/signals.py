import threading

# A tiny, dependency-free control channel between whatever creates work (the
# upload endpoint, a review action that unblocks a job, ...) and the worker loop -
# kept in its own module so callers don't have to import worker.py's much heavier
# AI/matcher dependency chain just to nudge it awake.
wake_event = threading.Event()
stop_event = threading.Event()


def wake_worker() -> None:
    """Interrupts the worker's poll wait so it picks up new work immediately
    instead of waiting out the rest of the poll interval.
    """
    wake_event.set()
