# The suites, N at a time, natively on Windows: tools/suite.py does the work.
#
#   powershell -ExecutionPolicy Bypass -File tools\run_suite.ps1 -Out D:\lava_suite -Jobs 8
#   powershell -ExecutionPolicy Bypass -File tools\run_suite.ps1 -Out D:\lava_suite -Only test_combat,test_death
#   powershell -ExecutionPolicy Bypass -File tools\run_suite.ps1 -Out D:\lava_suite -Affected
#   powershell -ExecutionPolicy Bypass -File tools\run_suite.ps1 -Out D:\lava_suite -RecordMap
#
# One output file per suite in -Out, summary.txt with a line per suite (exit
# code, seconds, name; a zero in front is a green suite) and report.html, the
# run as a table: mechanic, test, check, status, time. -Affected runs only the
# suites the change since origin/main touches, by the map -RecordMap writes
# (a full run that remembers which functions each suite runs).
#
# Needs the client's res folder: -Res, or LAVA_RES in the environment, or the
# default beside the repository (..\lava-online\res). The Python is the one
# on PATH; test_storage_pg is left out (it wants Postgres).
param(
  [string]$Out = (Join-Path $env:TEMP "lava_suite"),
  [int]$Jobs = 8,
  [string]$Res = "",
  [string[]]$Only = @(),
  [switch]$Affected,
  [switch]$RecordMap,
  [string]$Base = "origin/main"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$argv = @((Join-Path $repo "tools\suite.py"), "--out", $Out, "--jobs", $Jobs, "--base", $Base)
if ($Res) { $argv += @("--res", $Res) }
if ($Only.Count -gt 0) { $argv += @("--only", ($Only -join ",")) }
if ($Affected) { $argv += "--affected" }
if ($RecordMap) { $argv += "--record-map" }
& python @argv
exit $LASTEXITCODE
