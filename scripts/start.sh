#!/usr/bin/env bash
# Linux/macOS Startup Script for DocuMind Platform
echo "=================================================="
echo "Starting DocuMind Enterprise RAG Platform"
echo "=================================================="

# 1. Start FastAPI Backend in background
echo "[1/2] Starting FastAPI Backend on http://127.0.0.1:8000..."
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

trap "kill $BACKEND_PID" EXIT

sleep 3

# 2. Start Vite Frontend
echo "[2/2] Starting Vite Frontend on http://localhost:5173..."
cd frontend && npm run dev
