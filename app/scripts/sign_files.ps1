<#
.SYNOPSIS
  Authenticode-sign the program files of a build (optional step of build_app.ps1).

.DESCRIPTION
  Signs every .exe, .dll and .pyd under -Path (or the single file -Path) that is not already
  validly signed (Microsoft's and other vendors' files are left alone), with a timestamp, using
  signtool from the Windows SDK.

  Why: Windows 11's Smart App Control blocks unsigned programs and libraries it has no reputation
  for, with no "run anyway" choice for the user, and SmartScreen warns about unsigned installers.
  Only a signature from a trusted certificate authority avoids both. A self-signed certificate
  proves the mechanics but is NOT trusted by Windows.

.PARAMETER Path
  A folder (signed recursively) or one file.
.PARAMETER PfxPath
  The code-signing certificate (.pfx).
.PARAMETER PfxPassword
  Its password. Prefer the GEMSTUDIO_PFX_PASSWORD environment variable to a command-line value.
.PARAMETER TimestampUrl
  An RFC 3161 timestamp server (a timestamp keeps signatures valid after the certificate expires).
#>
param(
  [Parameter(Mandatory = $true)][string]$Path,
  [Parameter(Mandatory = $true)][string]$PfxPath,
  [string]$PfxPassword = $env:GEMSTUDIO_PFX_PASSWORD,
  [string]$TimestampUrl = "http://timestamp.digicert.com"
)
$ErrorActionPreference = "Stop"

$signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -match "\\x64\\" } | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $signtool) { throw "signtool.exe not found: install the Windows SDK (signing tools)." }
if (-not (Test-Path $PfxPath)) { throw "certificate not found: $PfxPath" }

$item = Get-Item $Path
$files = if ($item.PSIsContainer) {
  Get-ChildItem $Path -Recurse -File -Include *.exe, *.dll, *.pyd
} else { @($item) }

# Leave files that already carry a valid signature (Microsoft runtime DLLs, for example).
$todo = @($files | Where-Object { (Get-AuthenticodeSignature $_.FullName).Status -ne "Valid" })
Write-Host "signing $($todo.Count) of $($files.Count) files"

$base = @("sign", "/fd", "SHA256", "/f", $PfxPath, "/tr", $TimestampUrl, "/td", "SHA256")
if ($PfxPassword) { $base += @("/p", $PfxPassword) }
$batch = 40
for ($i = 0; $i -lt $todo.Count; $i += $batch) {
  $chunk = $todo[$i..([math]::Min($i + $batch, $todo.Count) - 1)] | ForEach-Object { $_.FullName }
  & $signtool.FullName @base @chunk | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "signtool failed on a batch starting at file $i" }
}
$unsigned = @($todo | Where-Object { (Get-AuthenticodeSignature $_.FullName).SignerCertificate -eq $null })
if ($unsigned.Count) { throw "$($unsigned.Count) files are still unsigned, e.g. $($unsigned[0].FullName)" }
Write-Host "signed $($todo.Count) files"
