param([int]$Port = 8766, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$localPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$existingPython = Join-Path (Split-Path $PSScriptRoot -Parent) 'facial-cue-prototype\.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $localPython) { $benchmarkPython = $localPython }
elseif (Test-Path -LiteralPath $existingPython) { $benchmarkPython = $existingPython }
else { $benchmarkPython = (Get-Command python -ErrorAction Stop).Source }
$arguments = @((Join-Path $PSScriptRoot 'server.py'), '--port', $Port)
if ($NoBrowser) { $arguments += '--no-browser' }
& $benchmarkPython @arguments

