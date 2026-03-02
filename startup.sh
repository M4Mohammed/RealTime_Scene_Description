#!/bin/bash
# Startup script for Azure App Service
python -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8000
