# Simple runner for Windows PowerShell
if (-not (Test-Path .\.venv)) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
