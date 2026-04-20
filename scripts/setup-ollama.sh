#!/usr/bin/env bash
# ============================================================================
# ATR-10: Install Ollama and pull Phi-3-mini model
# ============================================================================
# This script automates the Ollama setup for the AI-Ticket-Routing project.
#
# Prerequisites:
#   macOS:  brew or curl
#   Linux:  curl
#   Windows: Download from https://ollama.com/download
#
# Usage:
#   chmod +x scripts/setup-ollama.sh
#   ./scripts/setup-ollama.sh
# ============================================================================

set -euo pipefail

MODEL="phi3:mini"
OLLAMA_URL="http://localhost:11434"

# ---------- Helper ----------
info()  { printf "\033[1;34m[INFO]\033[0m  %s\n" "$1"; }
ok()    { printf "\033[1;32m[OK]\033[0m    %s\n" "$1"; }
fail()  { printf "\033[1;31m[FAIL]\033[0m  %s\n" "$1"; exit 1; }

# ---------- Step 1: Check / Install Ollama ----------
if command -v ollama &>/dev/null; then
    ok "Ollama is already installed: $(ollama --version)"
else
    info "Ollama not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &>/dev/null; then
            brew install ollama
        else
            curl -fsSL https://ollama.com/install.sh | sh
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -fsSL https://ollama.com/install.sh | sh
    else
        fail "Unsupported OS. Install Ollama manually from https://ollama.com/download"
    fi
    ok "Ollama installed: $(ollama --version)"
fi

# ---------- Step 2: Ensure Ollama is running ----------
if curl -sf "$OLLAMA_URL/api/version" &>/dev/null; then
    ok "Ollama server is running on $OLLAMA_URL"
else
    info "Starting Ollama server..."
    ollama serve &>/dev/null &
    sleep 3
    if curl -sf "$OLLAMA_URL/api/version" &>/dev/null; then
        ok "Ollama server started on $OLLAMA_URL"
    else
        fail "Could not start Ollama server. Run 'ollama serve' manually."
    fi
fi

# ---------- Step 3: Pull model ----------
info "Pulling model: $MODEL (~2.5 GB, may take a few minutes)..."
ollama pull "$MODEL"
ok "Model $MODEL pulled successfully"

# ---------- Step 4: Verify model is available ----------
if ollama list | grep -q "$MODEL"; then
    ok "ollama list shows $MODEL"
else
    fail "$MODEL not found in ollama list"
fi

# ---------- Step 5: Test OpenAI-compatible endpoint ----------
info "Testing OpenAI-compatible chat completions endpoint..."
RESPONSE=$(curl -sf "$OLLAMA_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{
        \"model\": \"$MODEL\",
        \"messages\": [{\"role\": \"user\", \"content\": \"Classify this ticket: Server is down. Reply with one word: infrastructure or application.\"}],
        \"temperature\": 0
    }")

if echo "$RESPONSE" | python3 -c "import sys,json; json.load(sys.stdin)" &>/dev/null; then
    ok "OpenAI-compatible endpoint returns valid JSON"
    echo "$RESPONSE" | python3 -m json.tool
else
    fail "Invalid response from chat completions endpoint"
fi

echo ""
ok "Ollama setup complete! Model '$MODEL' is ready on $OLLAMA_URL"
