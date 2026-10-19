<#
.SYNOPSIS
  Build the Gem Studio installer: figures -> PyInstaller bundle -> self-test -> Inno Setup.

.DESCRIPTION
  Run from anywhere:  powershell -File app\scripts\build_app.ps1
  Needs: app\.venv (with the app's packages and PyInstaller), Node 22+, Inno Setup 6
  (winget install JRSoftware.InnoSetup). It stops at the first failing step; the build is not
  offered as an installer unless the frozen app passed its self-test.

.PARAMETER SkipWeb
  Reuse app\web\dist instead of rebuilding the figures.
.PARAMETER SkipInstaller
  Stop after the bundle and its self-test.
.PARAMETER PfxPath
  A code-signing certificate (.pfx). When given, every program file in the bundle and the installer are
  signed (see sign_files.ps1). Unsigned builds can be blocked outright by Windows 11 Smart App Control.
.PARAMETER PfxPassword
  The certificate's password (or set GEMSTUDIO_PFX_PASSWORD).
.PARAMETER Replay
  A replay for the self-test. Default: the small truncated test replay (fast). Pass a full replay
  (about 4 minutes cold) to also exercise fight playbacks and the map crops in the frozen build.
#>
param(
  [switch]$SkipWeb,
  [switch]$SkipInstaller,
  [string]$Replay = "",
  [string]$PfxPath = "",
  [string]$PfxPassword = $env:GEMSTUDIO_PFX_PASSWORD
)
$ErrorActionPreference = "Stop"

$app = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repo = (Resolve-Path (Join-Path $app "..")).Path
$py = Join-Path $app ".venv\Scripts\python.exe"
$build = Join-Path $app "build"

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "FAILED: $text" -ForegroundColor Red; exit 1 }

Step "Checking tools"
if (-not (Test-Path $py)) { Fail "app\.venv not found. See app\README.md (Setting it up from scratch)." }
& $py -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller is not installed in app\.venv (pip install pyinstaller)." }
if (-not $SkipWeb -and -not (Get-Command node -ErrorAction SilentlyContinue)) { Fail "Node 22+ is needed to build the figures." }
$version = (& $py -c "import sys; sys.path.insert(0, r'$app'); import gemstudio; print(gemstudio.__version__)").Trim()
if (-not $version) { Fail "could not read the app version" }
Write-Host "Gem Studio $version"

Step "Hero and item icons"
if (-not (Test-Path (Join-Path $app "web\icons\heroes\axe.png"))) {
  & $py (Join-Path $repo "scripts\fetch_hero_icons.py")
  & $py (Join-Path $repo "scripts\fetch_item_icons.py")
  & $py (Join-Path $app "scripts\collect_icons.py")
  if ($LASTEXITCODE -ne 0) { Fail "collecting icons" }
} else { Write-Host "already collected" }

if (-not $SkipWeb) {
  Step "Figures (Vite)"
  Push-Location (Join-Path $app "web")
  try {
    if (-not (Test-Path "node_modules")) { npm install; if ($LASTEXITCODE -ne 0) { Fail "npm install" } }
    $env:VITE_CONFIG_NATIVE_IGNORE_WARNING = "true"
    npm run build
    if ($LASTEXITCODE -ne 0) { Fail "the figures did not build" }
  } finally { Pop-Location }
}
if (-not (Test-Path (Join-Path $app "web\dist\fights.html"))) { Fail "app\web\dist is missing: build the figures." }

Step "Icon and licence notices"
if (-not (Test-Path (Join-Path $app "packaging\gemstudio.ico"))) { & $py (Join-Path $app "packaging\make_icon.py") }
& $py (Join-Path $app "packaging\collect_licenses.py")
if ($LASTEXITCODE -ne 0) { Fail "collecting licences" }

Step "PyInstaller bundle"
Push-Location $app
$env:PYTHONPATH = Join-Path $repo "src"   # the engine; the build must not depend on a .pth file
try {
  & $py -m PyInstaller packaging\gemstudio.spec --noconfirm --distpath build\dist --workpath build\work
  if ($LASTEXITCODE -ne 0) { Fail "PyInstaller" }
} finally { Pop-Location; Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue }
$exe = Join-Path $build "dist\GemStudio\GemStudio.exe"
if (-not (Test-Path $exe)) { Fail "the bundle has no GemStudio.exe" }
$mb = [math]::Round(((Get-ChildItem (Join-Path $build "dist\GemStudio") -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB)
Write-Host "bundle: $mb MB"

if ($PfxPath) {
  Step "Signing the bundle"
  & powershell -NoProfile -File (Join-Path $PSScriptRoot "sign_files.ps1") -Path (Join-Path $build "dist\GemStudio") -PfxPath $PfxPath -PfxPassword $PfxPassword
  if ($LASTEXITCODE -ne 0) { Fail "signing the bundle" }
} else {
  Write-Host "`nNOTE: this build is unsigned. Windows 11 Smart App Control and SmartScreen can block or warn about unsigned programs (pass -PfxPath to sign)." -ForegroundColor Yellow
}

Step "Self-test of the frozen app (no Python on PATH, cold data folder)"
if (-not $Replay) { $Replay = Join-Path $repo "tests\fixtures\ti14_finals_g3_xg_vs_falcons_truncated.dem" }
$report = Join-Path $build "selftest-report.json"
$cold = Join-Path $build "selftest-data"
Remove-Item $report -ErrorAction SilentlyContinue
Remove-Item $cold -Recurse -Force -ErrorAction SilentlyContinue
$saved = @{ PATH = $env:PATH; PYTHONPATH = $env:PYTHONPATH; PYTHONHOME = $env:PYTHONHOME; VIRTUAL_ENV = $env:VIRTUAL_ENV }
try {
  # What a user's machine looks like: no Python, nothing from the developer's environment.
  $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
  Remove-Item Env:PYTHONPATH, Env:PYTHONHOME, Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
  $env:GEMSTUDIO_DATA_DIR = $cold
  $cwd = New-Item -ItemType Directory -Force (Join-Path $env:TEMP "gemstudio_selftest_cwd")
  $p = Start-Process -FilePath $exe -ArgumentList "--self-test", "`"$Replay`"", "--report", "`"$report`"", "--timeout", "900" `
        -WorkingDirectory $cwd.FullName -PassThru
  if (-not $p.WaitForExit(1000000)) { $p.Kill(); Fail "the self-test did not finish" }
  $code = $p.ExitCode
} finally {
  $env:PATH = $saved.PATH
  foreach ($n in "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV") { if ($saved[$n]) { Set-Item "Env:$n" $saved[$n] } }
  Remove-Item Env:GEMSTUDIO_DATA_DIR -ErrorAction SilentlyContinue
}
if (-not (Test-Path $report)) { Fail "the self-test wrote no report (see $cold\logs)" }
$result = Get-Content $report -Raw | ConvertFrom-Json
foreach ($c in $result.checks) {
  $mark = if ($c.ok) { "PASS" } else { "FAIL" }
  Write-Host ("  {0}  {1}  {2}" -f $mark, $c.name, $c.detail)
}
if ($code -ne 0 -or -not $result.ok) {
  if (($result.checks | Where-Object { $_.detail -match "Application Control policy" })) {
    Write-Host "  Windows Smart App Control / Application Control blocked a file of this unsigned build." -ForegroundColor Yellow
    Write-Host "  Run the build again (blocks can be one-off while Windows checks a file's reputation), or sign it (-PfxPath)." -ForegroundColor Yellow
  }
  Fail "the frozen app failed its self-test; no installer built"
}
Write-Host "self-test passed in $($result.seconds) s" -ForegroundColor Green

if ($SkipInstaller) { Write-Host "`nBundle: $build\dist\GemStudio"; exit 0 }

Step "Installer (Inno Setup)"
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
  Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Fail "Inno Setup 6 not found (winget install JRSoftware.InnoSetup)." }
Push-Location $app
try {
  & $iscc "/DAppVersion=$version" "packaging\gemstudio.iss"
  if ($LASTEXITCODE -ne 0) { Fail "Inno Setup" }
} finally { Pop-Location }
$setup = Join-Path $build "installer\GemStudio-Setup-$version.exe"
if (-not (Test-Path $setup)) { Fail "the installer was not written" }
if ($PfxPath) {
  & powershell -NoProfile -File (Join-Path $PSScriptRoot "sign_files.ps1") -Path $setup -PfxPath $PfxPath -PfxPassword $PfxPassword
  if ($LASTEXITCODE -ne 0) { Fail "signing the installer" }
}
$size = [math]::Round((Get-Item $setup).Length / 1MB)
Write-Host "`nInstaller: $setup ($size MB)" -ForegroundColor Green
