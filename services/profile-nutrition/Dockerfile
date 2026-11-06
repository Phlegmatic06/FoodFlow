# Multi-stage production Dockerfile for FoodFlow Profile & Nutrition Service (Port 8001)
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final runtime stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Install curl for container health probes and CA certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Create non-root system user and group for security hardening
RUN groupadd -g 10001 foodflow && \
    useradd -u 10001 -g foodflow -s /bin/bash -m foodflow

# Copy application source code
COPY services /app/services

# Ensure non-root ownership
RUN chown -R foodflow:foodflow /app

USER foodflow

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PROFILE_SERVICE_HOST=0.0.0.0 \
    PROFILE_SERVICE_PORT=8001

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "services.profile_nutrition.main:app", "--host", "0.0.0.0", "--port", "8001"]

