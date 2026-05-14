#!/bin/bash
# TriLink AI Engine Startup Script

echo "🚀 Starting TriLink AI Engine..."
echo ""
echo "Configuration:"
echo "  - Host: 0.0.0.0 (accessible from Docker)"
echo "  - Port: 8000"
echo "  - API Key: Configured"
echo ""

cd "$(dirname "$0")"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    exit 1
fi

# Check if Groq API key is set
if ! grep -q "^GROQ_API_KEY=" .env; then
    echo "⚠️  Warning: GROQ_API_KEY not found in .env"
fi

echo "✅ Starting uvicorn..."
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
