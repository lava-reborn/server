# The launcher's update path, end to end and without a window.
#
#   powershell -ExecutionPolicy Bypass -File launcher\test\run.ps1
#
# 1. make_fixture.py signs a few releases with client/publish.py's own code
#    (Python: the Windows one if "python" is a real interpreter, else WSL's);
# 2. csc compiles TestSync.cs with Release.cs, Sync.cs, TextsCheck.cs and
#    LocalServer.cs -- the files the launcher is built from, as they are;
# 3. TestSync.exe serves those releases on 127.0.0.1 and runs the launcher's
#    update against them: install, update, tampering, refusals, self-update.
#
# Exit status 0 when every check passed. ASCII only (see build.ps1).
param([string]$Work = "")

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Split-Path -Parent $here
$repo = Split-Path -Parent $launcher
if (-not $Work) { $Work = Join-Path $repo "dist\launcher-test" }
New-Item -ItemType Directory -Force $Work | Out-Null
$Work = (Resolve-Path $Work).Path

function ToWsl([string]$p) {
  $f = [System.IO.Path]::GetFullPath($p)
  return "/mnt/" + $f.Substring(0,1).ToLower() + $f.Substring(2).Replace('\','/')
}

Write-Host "==> fixture"
$fixture = Join-Path $here "make_fixture.py"
$winPython = $false
try { $null = & python -c "import sys; sys.exit(0)" 2>$null; $winPython = ($LASTEXITCODE -eq 0) } catch { $winPython = $false }
$data = Join-Path $Work "data"
if ($winPython) { & python $fixture $data } else { & wsl.exe -e python3 (ToWsl $fixture) (ToWsl $data) }
if ($LASTEXITCODE -ne 0) { throw "make_fixture.py failed" }

Write-Host "==> compile"
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$exe = Join-Path $Work "TestSync.exe"
& $csc /nologo /target:exe /platform:anycpu /codepage:65001 `
  /reference:System.dll /reference:System.Core.dll /reference:System.Numerics.dll `
  "/out:$exe" `
  (Join-Path $here "TestSync.cs") `
  (Join-Path $launcher "Release.cs") `
  (Join-Path $launcher "Sync.cs") `
  (Join-Path $launcher "TextsCheck.cs") `
  (Join-Path $launcher "LocalServer.cs")
if ($LASTEXITCODE -ne 0) { throw "csc failed" }

Write-Host "==> run"
& $exe $data
exit $LASTEXITCODE
