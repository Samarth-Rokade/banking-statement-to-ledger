from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config.settings import get_settings
from app.jobs.router import router as jobs_router
from app.ledger.router import router as ledger_router
from app.review.router import router as review_router
from app.upload.router import router as upload_router

settings = get_settings()

app = FastAPI(title="AI Bank Statement to Tally Ledger Generator")

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
