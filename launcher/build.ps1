# Build the one file a player gets: LavaReborn.exe.
#
#   powershell -ExecutionPolicy Bypass -File launcher\build.ps1
#   powershell -ExecutionPolicy Bypass -File launcher\build.ps1 -SignKey C:\Users\me\.lava-keys\launcher.pem
#   powershell -ExecutionPolicy Bypass -File launcher\build.ps1 -Site http://127.0.0.1:8098 `
#       -ResourceKeys dev\resource.keys -LauncherKeys dev\launcher.keys      (a developer's stand)
#
# Uses csc.exe out of the Windows .NET Framework, which is already on every
# Windows that can run the game, so there is nothing to install. What goes in:
# the Flash projector, the window's photograph, the two wrapper films and the
# public keys a release and a launcher must be signed with. The game does not:
# the launcher installs it from the server (client/FORMAT.md), so building
# needs no copy of it.
#
# The launchers players get are not built here: the gate on the server builds
# one with launcher/build.sh whenever a deploy changes what the exe is made
# of, numbers it one past the published one and signs it (client/README.md).
# This script is for a developer's own copy, the stand, and the owner's
# emergency launcher signed with the owner's key. -Build is its number
# (default 1); a published launcher only replaces itself with a larger one, so
# for one that will be published pass one more than the published version
# (publish.py status prints it).
#
# With -SignKey, the statement the server publishes beside the exe
# (dist/<version>.txt) is signed here with the launcher key; client/README.md
# says how it goes on. Without it, dist/<version>.body is the unsigned text.
#
# ASCII only in this file. Windows PowerShell 5.1 reads a .ps1 saved as UTF-8
# without a mark as cp1251, and one Cyrillic letter or long dash here is a
# parse error somewhere else entirely.
param(
  [string]$ServerHost = "lava-reborn.ru",
  [string]$Port = "9775",
  [string]$Site = "https://lava-reborn.ru",
  [string]$RegisterUrl = "",
  [string]$WikiUrl = "",
  [string]$CabinetUrl = "",
  [string]$ForumUrl = "https://forum.lava-reborn.ru/",
  [string]$NewsUrl = "https://forum.lava-reborn.ru/forum/1-novosti",
  [string]$ResourceKeys = "",
  [string]$LauncherKeys = "",
  [string]$SignKey = "",
  [string]$Build = "1",
  [switch]$AcceptKeys,
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
# The links in the window follow the site's own map: /register, /wiki and
# /cabinet are its pages, the forum and the patch notes topic live on the
# forum. A forgotten password has no page: the window explains in place
# that the administrator issues a new one.
if (-not $RegisterUrl) { $RegisterUrl = "$Site/register" }
if (-not $WikiUrl) { $WikiUrl = "$Site/wiki" }
if (-not $CabinetUrl) { $CabinetUrl = "$Site/cabinet" }
if (-not $ResourceKeys) { $ResourceKeys = Join-Path $repo "client\keys\resource.keys" }
if (-not $LauncherKeys) { $LauncherKeys = Join-Path $repo "client\keys\launcher.keys" }

$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "csc.exe not found at $csc" }

$projector = Join-Path $repo "tools\flash\fp32_sa.exe"
if (-not (Test-Path $projector)) {
  throw "Flash projector not found at $projector -- download flashplayer_32_sa.exe and put it there"
}

$hero = Join-Path $here "assets\hero.jpg"
if (-not (Test-Path $hero)) { throw "Window artwork not found at $hero" }
# The wordmark, drawn at 338x121 on the artwork and 94x34 on the title bar;
# the file is three times the larger of those, for high-dpi screens.
$logo = Join-Path $here "assets\logo.png"
if (-not (Test-Path $logo)) { throw "Logo not found at $logo" }

# The film that scales the game, opt-in with LAVA_SCALE=1, and its unscaled
# twin, opt-in with LAVA_PLAIN=1; both carry the ClanInspector mend. Built by
# tools\make_wrapper.py, which also explains why they exist.
$wrapper = Join-Path $here "assets\wrapper.swf"
if (-not (Test-Path $wrapper)) { throw "Wrapper film not found at $wrapper -- build it with tools/make_wrapper.py" }
$plain = Join-Path $here "assets\wrapper_plain.swf"
if (-not (Test-Path $plain)) { throw "Plain wrapper film not found at $plain -- build it with tools/make_wrapper.py" }

# Drawn from the brand mark by assets\make_icon.py; regenerate it with that
# script rather than by hand.
$icon = Join-Path $here "assets\lava.ico"
if (-not (Test-Path $icon)) { throw "Icon not found at $icon" }

# The build number, one integer.
$buildNo = $Build.Trim()
if ($buildNo -notmatch '^[1-9][0-9]{0,8}$') { throw "-Build must be one positive integer" }

# The public keys, as C# string literals. A launcher without them could not
# check a single update, so a missing or empty file stops the build.
function Key-Literals([string]$path, [string]$what) {
  if (-not (Test-Path $path)) { throw "no $what keys at $path (client\README.md, Keys)" }
  $lines = @()
  foreach ($l in [System.IO.File]::ReadAllLines($path)) {
    $t = $l.Trim()
    if ($t -eq "" -or $t.StartsWith("#")) { continue }
    if ($t -notmatch '^[0-9a-f]{16} [0-9]+ [0-9a-f]+$') { throw "bad line in $path" }
    $lines += '"' + $t + '"'
  }
  if ($lines.Count -eq 0) { throw "no $what keys in $path" }
  return ($lines -join ", ")
}
$resLits = Key-Literals $ResourceKeys "resource"
$lnLits = Key-Literals $LauncherKeys "launcher"

# The keys come from the checkout, and anyone who can merge could add a line
# to them; the next official build would then trust that person's signature.
# So the owner pins the key ids he trusts in pinned.txt beside his own keys
# (one "resource <id>" or "launcher <id>" per line), and a build whose keys
# differ stops. -AcceptKeys overrides, for a deliberate change of keys; a
# developer's stand (-ResourceKeys/-LauncherKeys given) is not checked.
function Key-Ids([string]$lits) {
  return @([regex]::Matches($lits, '"([0-9a-f]{16}) ') | ForEach-Object { $_.Groups[1].Value } | Sort-Object)
}
$pinned = Join-Path $env:USERPROFILE ".lava-keys\pinned.txt"
$official = -not $PSBoundParameters.ContainsKey("ResourceKeys") -and -not $PSBoundParameters.ContainsKey("LauncherKeys")
Write-Host ("==> keys: resource " + ((Key-Ids $resLits) -join ",") + "; launcher " + ((Key-Ids $lnLits) -join ","))
if ($official) {
  if (Test-Path $pinned) {
    $pin = @{ resource = @(); launcher = @() }
    foreach ($l in [System.IO.File]::ReadAllLines($pinned)) {
      $t = $l.Trim()
      if ($t -match '^(resource|launcher) ([0-9a-f]{16})$') { $pin[$Matches[1]] += $Matches[2] }
    }
    $okRes = ((@($pin.resource | Sort-Object) -join ",") -eq ((Key-Ids $resLits) -join ","))
    $okLn = ((@($pin.launcher | Sort-Object) -join ",") -eq ((Key-Ids $lnLits) -join ","))
    if (-not ($okRes -and $okLn)) {
      if ($AcceptKeys) { Write-Host "==> keys differ from $pinned -- accepted by -AcceptKeys" }
      else { throw "the keys in client\keys differ from the ones pinned in $pinned; check who changed them, then rebuild with -AcceptKeys and update the pin" }
    } else { Write-Host "==> keys match $pinned" }
  } else {
    Write-Host "==> WARNING: no $pinned -- the keys above are trusted as the repository has them"
  }
}

$build = Join-Path $repo "dist\.build"
New-Item -ItemType Directory -Force $build | Out-Null

# What the window shows in its corner. The commit is what a bug report needs;
# the date is what a player can actually read.
$stamp = Get-Date -Format "dd.MM.yyyy"
$sha = ""
try {
  Push-Location $repo
  $sha = (& git rev-parse --short HEAD 2>$null)
  Pop-Location
} catch { }
$version = if ($sha) { "v$buildNo $stamp $sha" } else { "v$buildNo $stamp" }
# Windows wants four numbers; the build number leads, so they sort.
$now = Get-Date
$fileVersion = "{0}.{1}.{2}.{3}" -f $buildNo, $now.Year, ($now.Month * 100 + $now.Day), 0

# The address, the links and the keys are compiled in, so the player has
# nothing to type or edit anywhere.
$src = Get-Content (Join-Path $here "Launcher.cs") -Raw -Encoding UTF8
$src = $src.Replace("@HOST@", $ServerHost).Replace("@PORT@", $Port)
$src = $src.Replace("@VERSION@", $version).Replace("@FILEVERSION@", $fileVersion)
$src = $src.Replace("@REGISTER@", $RegisterUrl).Replace("@WIKI@", $WikiUrl)
$src = $src.Replace("@CABINET@", $CabinetUrl).Replace("@FORUM@", $ForumUrl).Replace("@NEWS@", $NewsUrl)
$src = $src.Replace("@BUILD@", $buildNo)
$src = $src.Replace("@RESOURCE_KEYS@", $resLits).Replace("@LAUNCHER_KEYS@", $lnLits)
# Where releases are published. Trailing slash trimmed here rather than in the
# launcher, so the compiled-in string is already the origin it will be pasted
# onto.
$src = $src.Replace("@SITE@", $Site.TrimEnd("/"))
$gen = Join-Path $build "Launcher.generated.cs"
[System.IO.File]::WriteAllText($gen, $src, (New-Object System.Text.UTF8Encoding $true))

$sources = @(
  (Join-Path $here "Theme.cs"),
  (Join-Path $here "Controls.cs"),
  (Join-Path $here "Icons.cs"),
  (Join-Path $here "Panels.cs"),
  (Join-Path $here "MainForm.cs"),
  (Join-Path $here "Dialogs.cs"),
  (Join-Path $here "Prefs.cs"),
  (Join-Path $here "Notice.cs"),
  (Join-Path $here "Creds.cs"),
  (Join-Path $here "GameProbe.cs"),
  (Join-Path $here "GameWindow.cs"),
  (Join-Path $here "LocalServer.cs"),
  (Join-Path $here "Release.cs"),
  (Join-Path $here "Sync.cs"),
  (Join-Path $here "TextsCheck.cs"),
  $gen
)

New-Item -ItemType Directory -Force (Split-Path -Parent $Out) | Out-Null
Write-Host "==> compile"
& $csc /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 `
  /reference:System.dll /reference:System.Core.dll /reference:System.Numerics.dll `
  /reference:System.Drawing.dll /reference:System.Windows.Forms.dll /reference:System.Security.dll `
  "/win32icon:$icon" `
  "/resource:$projector,fp32_sa.exe" `
  "/resource:$hero,hero.jpg" `
  "/resource:$logo,logo.png" `
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

# The statement the server publishes beside the exe (client/FORMAT.md).
$exeSha = (Get-FileHash $Out -Algorithm SHA256).Hash.ToLower()
$exeSize = (Get-Item $Out).Length
$created = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$body = "lava-launcher 1`nversion $buildNo`nsha256 $exeSha`nsize $exeSize`ncreated $created`n"
$dist = Split-Path -Parent $Out
$bodyPath = Join-Path $dist "$buildNo.body"
[System.IO.File]::WriteAllText($bodyPath, $body, (New-Object System.Text.UTF8Encoding $false))
$stPath = Join-Path $dist "$buildNo.txt"
if (Test-Path $stPath) { Remove-Item $stPath -Force }

if ($SignKey) {
  if (-not (Test-Path $SignKey)) { throw "no key at $SignKey" }
  # Python: the Windows one if "python" is a real interpreter, else WSL's.
  $winPython = $false
  try { $null = & python -c "import sys; sys.exit(0)" 2>$null; $winPython = ($LASTEXITCODE -eq 0) } catch { $winPython = $false }
  $sig = Join-Path $repo "client\lavasig.py"
  if ($winPython) {
    & python $sig sign $SignKey $bodyPath -o $stPath
  } else {
    function ToWsl([string]$p) { $f = [System.IO.Path]::GetFullPath($p); return "/mnt/" + $f.Substring(0,1).ToLower() + $f.Substring(2).Replace('\','/') }
    & wsl.exe -e python3 (ToWsl $sig) sign (ToWsl $SignKey) (ToWsl $bodyPath) -o (ToWsl $stPath)
  }
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $stPath)) { throw "signing failed" }
  Remove-Item $bodyPath -Force
  Write-Host "==> $stPath (signed)"
} else {
  Write-Host "==> $bodyPath (unsigned: pass -SignKey to sign it)"
}

$mb = [math]::Round($exeSize / 1MB, 1)
Write-Host "==> $Out  ($mb MB)  build $buildNo -> $ServerHost`:$Port, updates from $Site/download/client/"
Write-Host "==> README.txt"
