# Build the one file a player gets: LavaOnline.exe.
#
#   powershell -ExecutionPolicy Bypass -File launcher\build.ps1 -ServerHost 159.194.247.90
#
# Uses csc.exe out of the Windows .NET Framework, which is already on every
# Windows that can run the game, so there is nothing to install. The projector
# and the generated string table go in as embedded resources; the game itself
# does not, and never will -- that stays the player's own res/ folder.
param(
  [string]$ServerHost = "159.194.247.90",
  [string]$Port = "9775",
  [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $here
if (-not $Out) { $Out = Join-Path $repo "dist\LavaOnline.exe" }

$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "csc.exe not found at $csc" }

$projector = Join-Path $repo "tools\flash\fp32_sa.exe"
if (-not (Test-Path $projector)) {
  throw "Flash projector not found at $projector -- download flashplayer_32_sa.exe and put it there"
}

# The string table has to hold every id this server can send, so it is
# regenerated here rather than taken from whatever dist/ happens to hold.
# Python lives in WSL on this machine (the Windows one is the Store stub),
# and export_texts.py writes dist/texts.xml by default.
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

# The address is compiled in, so the player has nothing to type or edit.
$src = Get-Content (Join-Path $here "LavaLauncher.cs") -Raw -Encoding UTF8
$src = $src.Replace("@HOST@", $ServerHost).Replace("@PORT@", $Port)
$gen = Join-Path $env:TEMP "LavaLauncher.generated.cs"
[System.IO.File]::WriteAllText($gen, $src, (New-Object System.Text.UTF8Encoding $true))

New-Item -ItemType Directory -Force (Split-Path -Parent $Out) | Out-Null
Write-Host "==> compile"
& $csc /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 `
  /reference:System.dll /reference:System.Windows.Forms.dll `
  "/resource:$projector,fp32_sa.exe" `
  "/resource:$texts,texts.xml" `
  "/out:$Out" $gen
if ($LASTEXITCODE -ne 0) { throw "csc failed" }

Remove-Item $gen -Force

# Short enough that someone will actually read it. Everything the old
# three-file package explained is now done by the exe itself.
$readme = @"
LAVA Online
===========

Положите LavaOnline.exe рядом с вашей папкой res (той, в которой лежит
main.swf) и запустите. Больше ничего делать не нужно.

Должно получиться так:

    LAVA\
      LavaOnline.exe
      res\
        main.swf
        ...

Игра в раздачу не входит: res — ваша собственная копия клиента. Всё
остальное программа делает сама при первом запуске — распаковывает
проигрыватель Flash, кладёт на место таблицу названий и разрешает игре
выход в сеть.

Сервер: $ServerHost`:$Port
Регистрация: http://$ServerHost`:8080/

Логин и пароль придумываете при регистрации, персонаж создаётся при первом
входе. Пароль на сервер не уходит: клиент считает от него хеш и посылает
только его.

Если игра пишет, что рядом нет папки res — значит exe лежит не там.
"@
[System.IO.File]::WriteAllText((Join-Path (Split-Path -Parent $Out) "README.txt"),
                               $readme, (New-Object System.Text.UTF8Encoding $true))

$mb = [math]::Round((Get-Item $Out).Length / 1MB, 1)
Write-Host "==> $Out  ($mb MB)  -> $ServerHost`:$Port"
Write-Host "==> README.txt"
