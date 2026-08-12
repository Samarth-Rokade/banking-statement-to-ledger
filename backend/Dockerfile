FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

# Runs as a non-root user - Cloud Run doesn't require this, but a compromised
# dependency shouldn't get root inside the container either way.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/storage/uploads \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Cloud Run's convention; entrypoint.sh reads $PORT at runtime regardless.
EXPOSE 8080

# This same image is deployed as two separate Cloud Run services (see
# DEPLOY.md): the API (RUN_WORKER_IN_PROCESS=false, scales on traffic) and the
# worker (RUN_WORKER_IN_PROCESS=true, min-instances=1, --no-cpu-throttling) -
# both just run this entrypoint; which one they become is entirely env-driven.
ENTRYPOINT ["./entrypoint.sh"]
