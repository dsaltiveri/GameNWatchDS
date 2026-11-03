[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $projectRoot 'build\gnw-builder'
$venvRoot = Join-Path $buildRoot 'venv'
$python = Join-Path $venvRoot 'Scripts\python.exe'
$icon = Join-Path $buildRoot 'GNWBuilder.ico'
$work = Join-Path $buildRoot 'pyinstaller-work'
$dist = Join-Path $buildRoot 'dist'
$versionFile = Join-Path $buildRoot 'version-info.txt'
$target = Join-Path $projectRoot 'GNWBuilder.exe'

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
if (-not (Test-Path -LiteralPath $python)) {
    py -3 -m venv $venvRoot
}
& $python -m pip install --disable-pip-version-check `
    'numpy==2.5.3' 'Pillow==12.3.0' 'PyInstaller==6.22.3'

& $python -c "from PIL import Image; im=Image.open(r'$($projectRoot)\icon.gif').convert('RGBA'); im.save(r'$icon', sizes=[(16,16),(32,32),(48,48),(256,256)])"

@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=(1,0,0,0), prodvers=(1,0,0,0), mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'GameNWatchDS'),
    StringStruct('FileDescription', 'GameNWatchDS package builder'),
    StringStruct('FileVersion', '1.0.0'),
    StringStruct('InternalName', 'GNWBuilder'),
    StringStruct('OriginalFilename', 'GNWBuilder.exe'),
    StringStruct('ProductName', 'GNWBuilder'),
    StringStruct('ProductVersion', '1.0.0')])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"@ | Set-Content -LiteralPath $versionFile -Encoding UTF8

& $python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name GNWBuilder `
    --icon $icon `
    --version-file $versionFile `
    --paths $PSScriptRoot `
    --add-data "$projectRoot\arm9\source\games;arm9\source\games" `
    --add-data "$projectRoot\icon.gif;." `
    --workpath $work `
    --distpath $dist `
    --specpath $buildRoot `
    (Join-Path $PSScriptRoot 'gnw_builder.py')

Copy-Item -LiteralPath (Join-Path $dist 'GNWBuilder.exe') -Destination $target -Force
$hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "Built $target"
Write-Host "SHA-256: $hash"
