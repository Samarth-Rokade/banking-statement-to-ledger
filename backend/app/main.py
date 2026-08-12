import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config.settings import get_settings
from app.database import engine
from app.export.router import router as export_router
from app.jobs import signals
from app.jobs.router import router as jobs_router
from app.jobs.worker import run_worker_loop
from app.ledger.router import router as ledger_router
from app.review.router import router as review_router
from app.upload.router import router as upload_router

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    worker_thread: threading.Thread | None = None
    if settings.run_worker_in_process and engine is not None:
        signals.stop_event.clear()
        worker_thread = threading.Thread(
            target=run_worker_loop,
            args=(settings.worker_poll_interval_seconds,),
            name="job-worker",
            daemon=True,
        )
        worker_thread.start()
        logger.info("Job worker started in-process")
    elif settings.run_worker_in_process:
        logger.warning("run_worker_in_process is enabled but DATABASE_URL is not set - skipping")

    yield

    if worker_thread is not None:
        signals.stop_event.set()
        signals.wake_worker()  # interrupt the poll wait so it notices stop_event promptly
        worker_thread.join(timeout=10)


app = FastAPI(title="AI Bank Statement to Tally Ledger Generator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(ledger_router, prefix="/api/v1")
app.include_router(review_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
