@echo off
set PYTHONPATH=src
echo API docs: http://127.0.0.1:8000/docs
uvicorn recon_agent.api:app --reload
