# Ollama Setup Guide

Local LLM inference for DeskMind using Ollama with Qwen 2.5:3B.

## Automated setup

```bash
chmod +x scripts/setup-ollama.sh
./scripts/setup-ollama.sh
```

The script installs Ollama, pulls the model, and verifies the endpoints.

## Manual setup

### 1. Install Ollama

| Platform | Command |
|----------|---------|
| macOS (Homebrew) | `brew install ollama` |
| macOS / Linux | `curl -fsSL https://ollama.com/install.sh \| sh` |
| Windows | Download from [ollama.com/download](https://ollama.com/download) |

### 2. Start the server

```bash
ollama serve
```

Runs on `http://localhost:11434` by default.

### 3. Pull Qwen 2.5:3B

```bash
ollama pull qwen2.5:3b
```

Download size is ~2 GB.

### 4. Verify installation

```bash
# Check model is listed
ollama list
# Should show: qwen2.5:3b

# Test the OpenAI-compatible endpoint
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:3b",
    "messages": [{"role": "user", "content": "Say hello"}],
    "temperature": 0
  }'
```

You should get a valid JSON response with the model's reply.

### 5. Test classification

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:3b",
    "messages": [{"role": "user", "content": "Classify this IT ticket: PostgreSQL not accepting connections on prod-db-01"}],
    "temperature": 0.1
  }'
```

## Migrating from old setup

If you previously installed `phi3:mini`, remove it and pull the correct model:

```bash
# Remove old model
ollama rm phi3:mini

# Pull the correct model
ollama pull qwen2.5:3b

# Verify
ollama list
# Should show ONLY: qwen2.5:3b
```

Make sure your `.env` has `OLLAMA_MODEL=qwen2.5:3b`. Then restart the backend:

```bash
docker compose restart backend
```

## Environment variables

Ensure your `.env` has:

```ini
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
```

## Docker setup

Ollama runs on the **host machine** (not inside Docker). The backend container reaches it via:

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

This is already configured in `docker-compose.yml`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `connection refused` on :11434 | Run `ollama serve` first |
| Model not found | Run `ollama pull qwen2.5:3b` |
| Slow responses | Qwen 2.5:3B needs ~4 GB RAM; close other heavy apps |
| GPU not used | Ollama auto-detects GPU. Check `ollama ps` for GPU info |
| Backend can't reach Ollama | Check `OLLAMA_BASE_URL` in `.env`. Inside Docker use `host.docker.internal` |
