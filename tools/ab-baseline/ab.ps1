# Requires Python 3.10+, Git, Docker Desktop and Compose v2.
& python (Join-Path $PSScriptRoot 'baseline.py') @args
if ($LASTEXITCODE -ne 0) { throw 'Baseline operation failed; do not start the next evaluation.' }
