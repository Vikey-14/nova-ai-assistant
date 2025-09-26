# build.ps1 — auto-generate version_info files from Git tag or VERSION.txt, then build

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

function Get-VersionString {
  $ver = $null
  try {
    $tag = (git describe --tags --abbrev=0 2>$null)
    if ($tag) { $ver = $tag.TrimStart('v','V') }
  } catch {}
  if (-not $ver -and (Test-Path "$repo/VERSION.txt")) {
    $ver = (Get-Content -Raw "$repo/VERSION.txt").Trim()
  }
  if (-not $ver) { $ver = "1.0.0" }
  return $ver
}

$ver = Get-VersionString
if ($ver -notmatch '^(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$') {
  throw "Version must look like 1.2.3 or 1.2.3.4 (got '$ver')."
}
$maj=[int]$Matches[1]; $min=[int]$Matches[2]; $pat=[int]$Matches[3]
$bld=[int]([string]::IsNullOrEmpty($Matches[4])?0:$Matches[4])

function New-VersionInfo($p,$prod,$desc,$orig){
$code=@"
VSVersionInfo(ffi=FixedFileInfo(filevers=($maj,$min,$pat,$bld), prodvers=($maj,$min,$pat,$bld),
 mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)),
 kids=[StringFileInfo([StringTable('040904B0',[
  StringStruct('CompanyName','Nova'),
  StringStruct('FileDescription','$desc'),
  StringStruct('ProductName','$prod'),
  StringStruct('ProductVersion','$ver'),
  StringStruct('FileVersion','$ver'),
  StringStruct('InternalName','$prod'),
  StringStruct('OriginalFilename','$orig')
])]), VarFileInfo([VarStruct('Translation',[1033,1200])])])
"@
Set-Content $p $code -Encoding UTF8
}

New-VersionInfo "$repo/version_info_main.txt" "Nova" "Nova" "Nova.exe"
New-VersionInfo "$repo/version_info_tray.txt" "Nova Tray" "Nova Tray" "Nova Tray.exe"

Write-Host "✔ Version files generated for $ver  ->  ($maj,$min,$pat,$bld)"

$venv = Join-Path $repo ".venv\Scripts\Activate.ps1"; if (Test-Path $venv) { & $venv }
Remove-Item -Recurse -Force build, dist 2>$null

# >>> BUILD_ID: make every build unique so first launch does full onboarding
$buildId = (Get-Date -Format "yyyyMMdd-HHmmss")
$gitShort = (git rev-parse --short HEAD 2>$null)
if ($LASTEXITCODE -eq 0 -and $gitShort) { $buildId = "$buildId-$gitShort" }
New-Item -ItemType Directory -Force -Path .\data | Out-Null
Set-Content -Encoding UTF8 .\data\build_id.txt $buildId
Write-Host "✔ BUILD_ID: $buildId"

pyinstaller .\NOVA.spec
Write-Host "✔ Build complete. Version: $ver"
