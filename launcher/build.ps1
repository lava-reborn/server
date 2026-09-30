# Build the one file a player gets: LavaReborn.exe.
#
#   powershell -ExecutionPolicy Bypass -File launcher\build.ps1
#   powershell -ExecutionPolicy Bypass -File launcher\build.ps1 -ServerHost 127.0.0.1 -Port 9775
#
# Uses csc.exe out of the Windows .NET Framework, which is already on every
# Windows that can run the game, so there is nothing to install. Three things
# go in as embedded resources -- the Flash projector, the generated string
# table and the window's photograph. The game itself does not, and never will:
# that stays the player's own res/ folder.
#
# ASCII only in this file. Windows PowerShell 5.1 reads a .ps1 saved as UTF-8
# without a mark as cp1251, and one Cyrillic letter or long dash here is a
# parse error somewhere else entirely.
param(
  [string]$ServerHost = "lava-reborn.ru",
  [string]$Port = "9775",
  [string]$Site = "https://lava-reborn.ru",
  [string]$RegisterUrl = "",
  [string]$LostPasswordUrl = "",
  [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $here
# No space in the file name: this is handed out as a link, and a link with a
# space in it breaks the moment someone pastes it into a chat. The name the
# player reads -- window, taskbar, Explorer details, SmartScreen -- is set by
# AssemblyTitle in Launcher.cs, and that one does say "Lava Reborn".
if (-not $Out) { $Out = Join-Path $repo "dist\LavaReborn.exe" }
if (-not $RegisterUrl) { $RegisterUrl = "$Site/register" }
if (-not $LostPasswordUrl) { $LostPasswordUrl = "$Site/" }

$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "csc.exe not found at $csc" }

$projector = Join-Path $repo "tools\flash\fp32_sa.exe"
if (-not (Test-Path $projector)) {
  throw "Flash projector not found at $projector -- download flashplayer_32_sa.exe and put it there"
}

$hero = Join-Path $here "assets\hero.jpg"
if (-not (Test-Path $hero)) { throw "Window artwork not found at $hero" }

# The film that scales the game: the projector is pointed at this rather than
# at main.swf, which fixes its stage at 950x650 and forbids scaling. Built by
# tools\make_wrapper.py, which also explains why it exists.
$wrapper = Join-Path $here "assets\wrapper.swf"
if (-not (Test-Path $wrapper)) { throw "Wrapper film not found at $wrapper -- build it with tools/make_wrapper.py" }
# Its unscaled twin, 950x650 like main.swf, opt-in with LAVA_PLAIN=1: the
# ClanInspector mend without the scaling, for working on why a game loaded
# into either film stops taking clicks. Same script builds both;
# tools/test_wrapper.py checks them.
$plain = Join-Path $here "assets\wrapper_plain.swf"
if (-not (Test-Path $plain)) { throw "Plain wrapper film not found at $plain -- build it with tools/make_wrapper.py" }

# Drawn from the brand mark by assets\make_icon.py; regenerate it with that
# script rather than by hand.
$icon = Join-Path $here "assets\lava.ico"
if (-not (Test-Path $icon)) { throw "Icon not found at $icon" }

# The string table has to hold every id this server can send, so it is
# regenerated here rather than taken from whatever dist/ happens to hold.
# Python lives in WSL on this machine (the Windows one is the Store stub).
# Into a build directory, not into dist/ itself: what lands beside the exe is
# what a player is handed, and a loose copy of a file the exe already carries
# is only there to be picked up by mistake.
$build = Join-Path $repo "dist\.build"
New-Item -ItemType Directory -Force $build | Out-Null
$texts = Join-Path $build "texts.xml"
$repoWsl = "/mnt/" + $repo.Substring(0,1).ToLower() + $repo.Substring(2).Replace('\','/')
Write-Host "==> string table"
& wsl.exe -e bash -lc "cd '$repoWsl' && python3 tools/export_texts.py -o dist/.build/texts.xml"
if ($LASTEXITCODE -ne 0) { throw "export_texts.py failed" }
if (-not (Test-Path $texts)) { throw "export_texts.py produced nothing at $texts" }

# The owner's edits to the names over the global map (data/map_labels.json),
# which LocalServer lays over the player's own res/database/locations.xml.
$labels = Join-Path $build "map_labels.txt"
Write-Host "==> map labels"
& wsl.exe -e bash -lc "cd '$repoWsl' && python3 tools/export_map_labels.py -o dist/.build/map_labels.txt"
if ($LASTEXITCODE -ne 0) { throw "export_map_labels.py failed" }
if (-not (Test-Path $labels)) { throw "export_map_labels.py produced nothing at $labels" }

# What the window shows in its corner. The commit is what a bug report needs;
# the date is what a player can actually read.
$stamp = Get-Date -Format "dd.MM.yyyy"
$sha = ""
try {
  Push-Location $repo
  $sha = (& git rev-parse --short HEAD 2>$null)
  Pop-Location
} catch { }
$version = if ($sha) { "$stamp $sha" } else { $stamp }
# Windows wants four numbers; the build date makes them, and they sort.
$now = Get-Date
$fileVersion = "{0}.{1}.{2}.0" -f $now.Year, $now.Month, $now.Day

# The address and the links are compiled in, so the player has nothing to type
# or edit anywhere.
$src = Get-Content (Join-Path $here "Launcher.cs") -Raw -Encoding UTF8
$src = $src.Replace("@HOST@", $ServerHost).Replace("@PORT@", $Port)
$src = $src.Replace("@VERSION@", $version).Replace("@FILEVERSION@", $fileVersion)
$src = $src.Replace("@REGISTER@", $RegisterUrl).Replace("@LOST@", $LostPasswordUrl)
# Where updates are published. Trailing slash trimmed here rather than in the
# launcher, so the compiled-in string is already the origin it will be pasted
# onto.
$src = $src.Replace("@SITE@", $Site.TrimEnd("/"))
$gen = Join-Path $build "Launcher.generated.cs"
[System.IO.File]::WriteAllText($gen, $src, (New-Object System.Text.UTF8Encoding $true))

$sources = @(
  (Join-Path $here "Theme.cs"),
  (Join-Path $here "Controls.cs"),
  (Join-Path $here "LoginForm.cs"),
  (Join-Path $here "Notice.cs"),
  (Join-Path $here "Creds.cs"),
  (Join-Path $here "GameProbe.cs"),
  (Join-Path $here "GameWindow.cs"),
  (Join-Path $here "LocalServer.cs"),
  (Join-Path $here "MapLabels.cs"),
  (Join-Path $here "Updater.cs"),
  $gen
)

New-Item -ItemType Directory -Force (Split-Path -Parent $Out) | Out-Null
Write-Host "==> compile"
& $csc /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 `
  /reference:System.dll /reference:System.Drawing.dll `
  /reference:System.Windows.Forms.dll /reference:System.Security.dll `
  "/win32icon:$icon" `
  "/resource:$projector,fp32_sa.exe" `
  "/resource:$texts,texts.xml" `
  "/resource:$labels,map_labels.txt" `
  "/resource:$hero,hero.jpg" `
  "/resource:$icon,icon.ico" `
  "/resource:$wrapper,wrapper.swf" `
  "/resource:$plain,wrapper_plain.swf" `
  "/out:$Out" $sources
if ($LASTEXITCODE -ne 0) { throw "csc failed" }

Remove-Item $gen -Force

# Short enough that someone will actually read it. It lives in its own file
# rather than in a here-string: PowerShell 5.1 reads this script as cp1251,
# and the Cyrillic that used to sit here shipped to every player as mojibake.
$readme = [System.IO.File]::ReadAllText((Join-Path $here "README.player.txt"),
                                        (New-Object System.Text.UTF8Encoding $false))
$readme = $readme.Replace("@HOST@", $ServerHost).Replace("@PORT@", $Port)
$readme = $readme.Replace("@REGISTER@", $RegisterUrl)
[System.IO.File]::WriteAllText((Join-Path (Split-Path -Parent $Out) "README.txt"),
                               $readme, (New-Object System.Text.UTF8Encoding $true))

$mb = [math]::Round((Get-Item $Out).Length / 1MB, 1)
Write-Host "==> $Out  ($mb MB)  -> $ServerHost`:$Port  [$version]"
Write-Host "==> README.txt"
