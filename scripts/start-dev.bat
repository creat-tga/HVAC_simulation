@echo off
setlocal

set ROOT_DIR=%~dp0..

REM Start backend in new window
echo Starting backend (in new window)
start "Backend" cmd /k "cd /d %ROOT_DIR%backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000"

REM Start frontend in new window
echo Starting frontend (in new window)
start "Frontend" cmd /k "cd /d %ROOT_DIR%frontend && pnpm run dev"

endlocal
