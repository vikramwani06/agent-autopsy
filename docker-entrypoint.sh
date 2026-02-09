#!/bin/bash

# =============================================================================
# Agent Autopsy Docker Entrypoint Script
# =============================================================================

set -e

# Create necessary directories
mkdir -p reports/passed reports/failed logs

# Wait for dependencies (if any)
# echo "Waiting for dependencies..."
# wait-for-it.sh ${DATABASE_URL}

# Health check function
health_check() {
    curl -f http://localhost:8000/health > /dev/null 2>&1
}

# Start the API server in background
echo "Starting Agent Autopsy API server on port ${API_PORT:-8000}..."
python -m uvicorn agent_autopsy.main:app \
    --host ${API_HOST:-0.0.0.0} \
    --port ${API_PORT:-8000} \
    --log-level ${LOG_LEVEL:-info} &

API_PID=$!

# Wait for API to be ready
echo "Waiting for API server to be ready..."
for i in {1..30}; do
    if health_check; then
        echo "API server is ready!"
        break
    fi
    echo "Waiting for API server... ($i/30)"
    sleep 2
done

if ! health_check; then
    echo "API server failed to start"
    exit 1
fi

# Start Streamlit UI
echo "Starting Streamlit UI on port ${STREAMLIT_PORT:-8501}..."
streamlit run client_app/app.py \
    --server.headless true \
    --server.port ${STREAMLIT_PORT:-8501} \
    --server.address ${STREAMLIT_HOST:-0.0.0.0} \
    --server.logLevel ${LOG_LEVEL:-info} &

UI_PID=$!

# Function to handle shutdown
shutdown() {
    echo "Shutting down..."
    kill $API_PID $UI_PID 2>/dev/null
    wait $API_PID $UI_PID 2>/dev/null
    echo "Shutdown complete"
    exit 0
}

# Trap signals
trap shutdown SIGTERM SIGINT

# Wait for processes
wait $API_PID $UI_PID
