# ---------- development stage ----------
FROM python:3.12-slim AS dev

WORKDIR /app

# Install system deps needed by some Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------- production stage ----------
FROM python:3.12-slim AS production

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm && \
    apt-get purge -y gcc g++ && apt-get autoremove -y

COPY . .

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
