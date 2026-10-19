GEM STUDIO: REBUILD AND RUN COMMANDS
=====================================================================
All commands are for Windows PowerShell. Replace D:\Repo\gem-dota-uI with
your project folder if it is somewhere else.

Where things are
  Project root ............ D:\Repo\gem-dota-uI
  The app ................. D:\Repo\gem-dota-uI\app
  The figures (web) ....... D:\Repo\gem-dota-uI\app\web        (built to app\web\dist)
  Python environment ...... D:\Repo\gem-dota-uI\app\.venv
  Built app (runnable) .... app\build\dist\GemStudio\GemStudio.exe   (keep the _internal folder beside it)
  Built installer ......... app\build\installer\GemStudio-Setup-<version>.exe
  Saved replay results .... %LOCALAPPDATA%\GemStudio\cache     (logs: %LOCALAPPDATA%\GemStudio\logs)
  Test replay ............. D:\Repo\gem-dota-uI\9045456575_334166624.dem


1. FULL REBUILD (exe + installer)   <- the one you usually want
---------------------------------------------------------------------
  cd D:\Repo\gem-dota-uI
  powershell -NoProfile -ExecutionPolicy Bypass -File app\scripts\build_app.ps1

Takes about 8 to 9 minutes. It does, in order:
  1. checks the tools (the venv, PyInstaller, Node)
  2. fetches hero/item icons if they are missing
  3. builds the figures (Vite)  -> app\web\dist
  4. writes the licence notices and the icon
  5. bundles the app with PyInstaller -> app\build\dist\GemStudio  (about 583 MB)
  6. SELF-TESTS the bundled app (no Python on PATH, empty data folder)
  7. only if the self-test passed: builds the installer with Inno Setup
Output:
  app\build\dist\GemStudio\GemStudio.exe
  app\build\installer\GemStudio-Setup-0.1.0.exe   (about 167 MB)
If a step fails the script stops and prints "FAILED: ...".

Variants (add to the command above):
  -SkipWeb                  reuse app\web\dist instead of rebuilding the figures
  -SkipInstaller            stop after the bundle and its self-test (about 4 minutes)
  -Replay "C:\path\full.dem"  self-test with a full replay (about 3 extra minutes);
                            also exercises fight replays and the map crops
  -PfxPath "C:\cert.pfx" -PfxPassword "..."   sign the bundle and installer (see section 9)
Example (quick check of the bundle only):
  powershell -NoProfile -ExecutionPolicy Bypass -File app\scripts\build_app.ps1 -SkipWeb -SkipInstaller


2. REBUILD ONLY THE FIGURES (after changing app\web or site\)
---------------------------------------------------------------------
  cd D:\Repo\gem-dota-uI\app\web
  $env:VITE_CONFIG_NATIVE_IGNORE_WARNING = "true"     # optional: hides a harmless Vite notice
  npm run build
  npx tsc --noEmit -p tsconfig.json                   # optional: type check
  npx vitest run                                       # optional: the figure-build tests
Python changes in app\gemstudio need NO rebuild to run from source (section 3).


3. RUN THE APP FROM SOURCE (no exe needed, fastest way to test)
---------------------------------------------------------------------
  cd D:\Repo\gem-dota-uI\app
  .\.venv\Scripts\python -m gemstudio                                    # empty window, use "Open replay..."
  .\.venv\Scripts\python -m gemstudio ..\9045456575_334166624.dem        # open a replay directly
  .\.venv\Scripts\python -m gemstudio --version
First open of a replay takes about 3 minutes (progress is shown); later opens take seconds.
Rebuild the figures first (section 2) if you changed app\web.


4. RUN / CHECK THE BUILT EXE
---------------------------------------------------------------------
Run it:
  D:\Repo\gem-dota-uI\app\build\dist\GemStudio\GemStudio.exe
  D:\Repo\gem-dota-uI\app\build\dist\GemStudio\GemStudio.exe "D:\Repo\gem-dota-uI\9045456575_334166624.dem"

Self-test it by hand (what the build does). The cold data folder forces a real first-time read:
  $env:GEMSTUDIO_DATA_DIR = "D:\Repo\gem-dota-uI\app\build\selftest-data"
  Remove-Item $env:GEMSTUDIO_DATA_DIR -Recurse -Force -ErrorAction SilentlyContinue
  $p = Start-Process -FilePath "D:\Repo\gem-dota-uI\app\build\dist\GemStudio\GemStudio.exe" `
       -ArgumentList "--self-test","`"D:\Repo\gem-dota-uI\9045456575_334166624.dem`"","--report","`"$env:TEMP\selftest.json`"" -PassThru
  $p.WaitForExit(); "exit code: $($p.ExitCode)"            # 0 = every check passed
  Get-Content "$env:TEMP\selftest.json" | ConvertFrom-Json | Select-Object -ExpandProperty checks
  Remove-Item Env:GEMSTUDIO_DATA_DIR


5. TEST THE INSTALLER (install, run, uninstall in a scratch folder)
---------------------------------------------------------------------
  $setup = "D:\Repo\gem-dota-uI\app\build\installer\GemStudio-Setup-0.1.0.exe"
  $dir   = "D:\Repo\gem-dota-uI\app\build\install_test"
  Start-Process -FilePath $setup -Wait -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/DIR=`"$dir`"","/TASKS=`"openwith`""
  & "$dir\GemStudio.exe"                                    # try it
  Start-Process -FilePath "$dir\unins000.exe" -Wait -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART"
The installer needs no administrator rights. To install normally just double-click it.
Uninstalling never deletes your saved replay results.


6. TESTS AND CHECKS
---------------------------------------------------------------------
  cd D:\Repo\gem-dota-uI\app
  .\.venv\Scripts\python -m pytest                          # the fast tests, about 2.5 minutes
  .\.venv\Scripts\python -m pytest -m slow tests\test_export.py   # real-replay check; needs the .dem in the project root; minutes when cold
  .\.venv\Scripts\ruff check gemstudio tests                # lint
  .\.venv\Scripts\ruff format gemstudio tests               # auto-format
  .\.venv\Scripts\mypy gemstudio                            # type check
(The app tests need the figures built first: section 2.)


7. ONE-TIME SETUP ON A NEW MACHINE
---------------------------------------------------------------------
Needs: Python 3.12, Node 22 or newer, Inno Setup 6 (only to build the installer):
  winget install JRSoftware.InnoSetup --scope user

  cd D:\Repo\gem-dota-uI\app
  python -m venv .venv
  .\.venv\Scripts\python -m pip install --upgrade pip
  .\.venv\Scripts\python -m pip install -r requirements-build.txt pytest ruff mypy
  # let the venv find the parser source in this repository:
  Set-Content -Path .venv\Lib\site-packages\gem_fork.pth -Value "D:\Repo\gem-dota-uI\src" -Encoding ascii
  # hero and item icons (downloaded, not committed), then copy them for the app:
  .\.venv\Scripts\python ..\scripts\fetch_hero_icons.py
  .\.venv\Scripts\python ..\scripts\fetch_item_icons.py
  .\.venv\Scripts\python scripts\collect_icons.py
  # the figures:
  cd web
  npm install
  npm run build


8. VERSION NUMBER
---------------------------------------------------------------------
Edit __version__ in  app\gemstudio\__init__.py  (for example "0.1.1"), then rebuild (section 1).
The installer file name uses it, and so does the saved-results cache (a new version never reuses old results).


9. SIGNING (optional; needs a code-signing certificate)
---------------------------------------------------------------------
Unsigned builds can be blocked by Windows 11 Smart App Control and flagged by SmartScreen.
With a certificate file:
  powershell -NoProfile -ExecutionPolicy Bypass -File app\scripts\build_app.ps1 -PfxPath "C:\path\cert.pfx" -PfxPassword "the-password"
  (or set the password in the GEMSTUDIO_PFX_PASSWORD environment variable instead of typing it)
Signing only the bundle folder or the installer by hand:
  powershell -NoProfile -File app\scripts\sign_files.ps1 -Path app\build\dist\GemStudio -PfxPath "C:\path\cert.pfx"
Certificates from cloud signing services need a change to the scripts first (not done yet).


10. BUILD ON GITHUB AND PUBLISH A DOWNLOAD
---------------------------------------------------------------------
The workflow is .github\workflows\gem-studio-installer.yml. It runs only when started by hand or when
a tag named studio-v* is pushed. It has NOT been run on GitHub yet.
  cd D:\Repo\gem-dota-uI
  git add -A
  git commit -m "Gem Studio app"
  git push origin main
Then on GitHub: Actions -> "Gem Studio installer" -> Run workflow, and download the "GemStudio-installer" artifact.
To publish a release the README link points to (use the version from section 8):
  git tag studio-v0.1.0
  git push origin studio-v0.1.0


11. HOUSEKEEPING AND PROBLEMS
---------------------------------------------------------------------
Clear the saved replay results (the next open re-reads the replay, about 3 minutes):
  Remove-Item "$env:LOCALAPPDATA\GemStudio\cache" -Recurse -Force
Read an error log:
  Get-Content "$env:LOCALAPPDATA\GemStudio\logs\*.log"
Close a stuck app before rebuilding:
  Get-Process GemStudio -ErrorAction SilentlyContinue | Stop-Process -Force

"This file / policy has been blocked" or "Application Control policy" errors:
  Windows 11 Smart App Control can block unsigned files in a build, sometimes only on some runs.
  Run the build or the app again. Only signing (section 9) fixes it for good. You can check Windows' record:
  Get-WinEvent -LogName "Microsoft-Windows-CodeIntegrity/Operational" -MaxEvents 50 | Where-Object { $_.Id -in 3077,3033 }
"running scripts is disabled": run the build with  -ExecutionPolicy Bypass  as shown in section 1.
Build says Inno Setup not found: winget install JRSoftware.InnoSetup --scope user
Build says app\.venv not found: do section 7.
