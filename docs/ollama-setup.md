# Ollama Setup Guide (ATR-9 / ATR-10)

Local LLM inference for AI-Ticket-Routing using Ollama with Phi-3-mini.

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

### 3. Pull Phi-3-mini

```bash
ollama pull phi3:mini
```

Download size is ~2.5 GB.

### 4. Verify installation

```bash
# Check model is listed
ollama list
# Should show: phi3:mini

# Test the OpenAI-compatible endpoint
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "phi3:mini",
    "messages": [{"role": "user", "content": "Say hello"}],
    "temperature": 0
  }'
```

You should get a valid JSON response with the model's reply.

### 5. Test logprobs support

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "phi3:mini",
    "messages": [{"role": "user", "content": "Classify: infrastructure or application?"}],
    "logprobs": true,
    "top_logprobs": 5
  }'
```

## Environment variables

Ensure your `.env` has:

```ini
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi3:mini
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `connection refused` on :11434 | Run `ollama serve` first |
| Model not found | Run `ollama pull phi3:mini` |
| Slow responses | Phi-3-mini needs ~4 GB RAM; close other heavy apps |
| GPU not used | Ollama auto-detects GPU. Check `ollama ps` for GPU info |
