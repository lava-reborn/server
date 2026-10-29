# Full local pre-push check. Does not commit, push or deploy.
param(
    [ValidateSet('All', 'Native', 'CI', 'Regression')]
    [string]$Mode = 'All',
    [string]$Res = 'D:\lava-reborn\res',
    [string]$Player = "$env:USERPROFILE\Downloads\flashplayer_32_sa.exe",
    [string]$ClientMain = '',
    [ValidateRange(1, 8)][int]$Jobs = 1,
    [ValidateRange(60, 86400)][int]$TimeoutSeconds = 21600,
    [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$checkArgs = @('-B', (Join-Path $repo 'tools\local_checks.py'),
    '--mode', $Mode.ToLowerInvariant(), '--res', $Res, '--player', $Player,
    '--jobs', $Jobs, '--timeout', $TimeoutSeconds)
if ($ClientMain) { $checkArgs += @('--client-main', $ClientMain) }
if ($Out) { $checkArgs += @('--out', $Out) }
# Prefer the dedicated checker environment when it has been prepared.
$checkPython = Join-Path $repo '.venv-local-checks\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $checkPython)) { $checkPython = 'python' }
& $checkPython @checkArgs
exit $LASTEXITCODE
