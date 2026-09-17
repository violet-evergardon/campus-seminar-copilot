$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $root 'backend')
python -m compileall -q app
python -m pytest -q
Pop-Location
Push-Location (Join-Path $root 'frontend')
npm run build
Pop-Location
python (Join-Path $root 'scripts\evaluate.py')

