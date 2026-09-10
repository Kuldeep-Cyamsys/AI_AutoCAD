$ErrorActionPreference = "Stop"
& "$PSScriptRoot\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --app-dir "$PSScriptRoot\backend" --host 127.0.0.1 --port 8010
