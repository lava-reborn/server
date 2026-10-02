# Every suite, N at a time, longest first, natively on Windows.
#
#   powershell -ExecutionPolicy Bypass -File tools\run_suite.ps1 -Out D:\lava_suite -Jobs 8
#   powershell -ExecutionPolicy Bypass -File tools\run_suite.ps1 -Out D:\lava_suite -Only test_combat,test_death
#
# One output file per suite in -Out, and summary.txt with a line per suite:
# exit code, seconds, name. A zero in front is a green suite. The suites that
# wait on game time share the clock, so a suite that depends on it can fail
# under load: run it alone before taking the failure for real.
#
# Needs the client's res folder: -Res, or LAVA_RES in the environment, or the
# default beside the repository (..\lava-online\res). The Python is the one
# on PATH; test_storage_pg is left out (it wants Postgres).
param(
  [string]$Out = (Join-Path $env:TEMP "lava_suite"),
  [int]$Jobs = 8,
  [string]$Res = "",
  [string[]]$Only = @()
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $Res) { $Res = $env:LAVA_RES }
if (-not $Res) { $Res = Join-Path (Split-Path -Parent $repo) "lava-online\res" }
if (-not (Test-Path (Join-Path $Res "main.swf"))) { throw "no client at $Res (main.swf missing); pass -Res" }
New-Item -ItemType Directory -Force $Out | Out-Null

$list = @()
$list += Get-ChildItem (Join-Path $repo "server\test_halfa_training.py")
$list += Get-ChildItem (Join-Path $repo "server\test_*.py") |
  Where-Object { $_.Name -notin @("test_halfa_training.py", "test_storage_pg.py") } |
  Sort-Object Length -Descending
$list += Get-ChildItem (Join-Path $repo "data\test_*.py")
$list += Get-ChildItem (Join-Path $repo "tools\test_*.py")
if ($Only.Count -gt 0) { $list = $list | Where-Object { $_.BaseName -in $Only } }

$summary = Join-Path $Out "summary.txt"
Set-Content -Path $summary -Value "" -Encoding utf8
$orig = Join-Path $Res "xml\texts.xml"

$running = @{}
$queue = [System.Collections.Queue]::new($list)
while ($queue.Count -gt 0 -or $running.Count -gt 0) {
  while ($queue.Count -gt 0 -and $running.Count -lt $Jobs) {
    $t = $queue.Dequeue()
    $name = $t.BaseName
    $env:LAVA_RES = $Res
    $env:LAVA_DB = Join-Path $env:TEMP ("lava_" + $name + ".db")
    $env:LAVA_ORIG_TEXTS = $orig
    $env:PYTHONUTF8 = "1"
    $log = Join-Path $Out ($name + ".out")
    $p = Start-Process -FilePath "python" -ArgumentList $t.Name -WorkingDirectory $t.DirectoryName `
      -RedirectStandardOutput $log -RedirectStandardError (Join-Path $Out ($name + ".err")) `
      -PassThru -NoNewWindow
    # Touch the handle now, or ExitCode reads back empty once it has exited.
    $null = $p.Handle
    $running[$p.Id] = @{ p = $p; name = $name; start = Get-Date }
    # A server takes some five seconds to read the world on Windows, and
    # eight of them at once take longer than the ten the suites wait for the
    # port; one launch at a time, a few seconds apart, keeps every start
    # inside that.
    Start-Sleep -Seconds 4
  }
  Start-Sleep -Seconds 2
  foreach ($id in @($running.Keys)) {
    $r = $running[$id]
    if ($r.p.HasExited) {
      $secs = [int]((Get-Date) - $r.start).TotalSeconds
      Add-Content -Path $summary -Value ("{0} {1}s {2}" -f $r.p.ExitCode, $secs, $r.name) -Encoding utf8
      $running.Remove($id)
    }
  }
}
Add-Content -Path $summary -Value "DONE" -Encoding utf8
$failed = Get-Content $summary | Where-Object { $_ -match '^\d' -and $_ -notmatch '^0 ' }
"{0} suites, {1} failed" -f $list.Count, @($failed).Count
$failed
