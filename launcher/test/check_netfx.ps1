# Does an exe built on Linux (launcher/build.sh, Mono's compiler) run on
# Windows' own .NET Framework? Without opening a window: every method of the
# assembly is compiled by this machine's JIT, which is where a call to a
# method .NET Framework does not have fails (MissingMethodException).
#
#   powershell -ExecutionPolicy Bypass -File launcher\test\check_netfx.ps1 LavaReborn.exe
#
# Built against Mono's own libraries, the engine failed in 8 methods here
# (String.TrimEnd(char) and the like); built against the .NET Framework
# reference assemblies, as build.sh does, in none. Exit status: the number of
# methods that failed. ASCII only (see build.ps1).
param([Parameter(Mandatory = $true)][string]$Exe)

$ErrorActionPreference = "Stop"
$a = [Reflection.Assembly]::LoadFile((Resolve-Path $Exe).Path)
Write-Host ("runtime " + $a.ImageRuntimeVersion)
foreach ($r in $a.GetReferencedAssemblies()) {
  $loaded = [Reflection.Assembly]::Load($r)
  Write-Host ("  " + $r.Name + " -> " + $loaded.Location)
}
$flags = [Reflection.BindingFlags]"Public,NonPublic,Instance,Static,DeclaredOnly"
$ok = 0
$bad = @()
foreach ($t in $a.GetTypes()) {
  if ($t.ContainsGenericParameters) { continue }
  foreach ($m in (@($t.GetMethods($flags)) + @($t.GetConstructors($flags)))) {
    if ($m.IsAbstract -or $m.ContainsGenericParameters) { continue }
    try {
      [System.Runtime.CompilerServices.RuntimeHelpers]::PrepareMethod($m.MethodHandle)
      $ok++
    } catch {
      $bad += ($t.FullName + "." + $m.Name + ": " + $_.Exception.GetBaseException().Message)
    }
  }
}
Write-Host ("resources: " + ($a.GetManifestResourceNames() -join ", "))
Write-Host ("compiled $ok methods, " + $bad.Count + " failed")
$bad | ForEach-Object { Write-Host ("  " + $_) }
exit $bad.Count
