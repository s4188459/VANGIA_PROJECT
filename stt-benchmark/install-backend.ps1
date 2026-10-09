param(
  [Parameter(Mandatory=$true)]
  [ValidateSet('faster-whisper','transformers-whisper','transformers-ctc','qwen-asr','nemo','sensevoice','vosk','elevenlabs','google-chirp')]
  [string]$Backend
)
$ErrorActionPreference = 'Stop'
$packages = @{
  'faster-whisper' = @('faster-whisper==1.2.1')
  'transformers-whisper' = @('torch','transformers','soundfile')
  'transformers-ctc' = @('torch','transformers','soundfile')
  'qwen-asr' = @('qwen-asr')
  'nemo' = @('nemo_toolkit[asr]','huggingface_hub')
  'sensevoice' = @('funasr','torch','torchaudio','huggingface_hub')
  'vosk' = @('vosk')
  'elevenlabs' = @('requests')
  'google-chirp' = @('google-cloud-speech')
}
$envDirectory = Join-Path $PSScriptRoot ".backends\$Backend"
$backendPython = Join-Path $envDirectory 'Scripts\python.exe'
$existingPython = Join-Path (Split-Path $PSScriptRoot -Parent) 'facial-cue-prototype\.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $backendPython)) {
  if (Test-Path -LiteralPath $existingPython) { & $existingPython -m venv $envDirectory }
  else { python -m venv $envDirectory }
  if ($LASTEXITCODE -ne 0) { throw 'Cannot create backend environment.' }
}
& $backendPython -m pip install @($packages[$Backend])
if ($LASTEXITCODE -ne 0) { throw 'Backend installation failed. NeMo may require Linux/WSL; see README.' }
Write-Host "Backend Python: $backendPython"
Write-Host 'Refresh the tool, select a catalog model, then save its configuration. Weights download separately when enabled.'
