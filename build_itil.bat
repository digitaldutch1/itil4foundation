@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem ====== Instellingen ==================================================
set "SCRIPT=itil.py"
set "APPNAME=ITIL 4 Foundation"
set "ICON=assets\afbeeldingen\itil_4_icon2.ico"
set "ASSETSDIR=assets"
set "DISTPATH=."
set "WORKPATH=build"
set "SPECPATH=."
set "LOG=build_last.log"

rem Default: NIET starten na build
set "AUTO_START=0"
rem Parameters: onedir / clean / start
for %%A in (%*) do (
  if /I "%%~A"=="start"  set "AUTO_START=1"
)
rem ======================================================================

> "%LOG%" echo ----------------------------------------------------------
>>"%LOG%" echo Build gestart: %DATE% %TIME%
>>"%LOG%" echo Werkmap: %CD%
>>"%LOG%" echo ----------------------------------------------------------

rem ---- Python & PyInstaller check ----
where py >nul 2>&1 && (set "PYCMD=py") || (set "PYCMD=python")
%PYCMD% --version >nul 2>&1 || (
  echo [FOUT] Python niet gevonden
  >>"%LOG%" echo [FOUT] Python niet gevonden
  start "" notepad "%LOG%"
  goto :END_FAIL
)

%PYCMD% -m PyInstaller --version >nul 2>&1 || (
  echo [INFO] PyInstaller niet gevonden. Installeren...
  >>"%LOG%" echo [INFO] PyInstaller niet gevonden. Installeren...
  %PYCMD% -m pip install -U pyinstaller >>"%LOG%" 2>&1 || goto :END_FAIL
)

rem ---- Buildmodus (onefile default) + schoonmaken ----
set "PYI_MODE=--onefile"
for %%A in (%*) do if /I "%%~A"=="onedir" set "PYI_MODE=-D"
set "CLEAN="
for %%A in (%*) do if /I "%%~A"=="clean" set "CLEAN=--clean"

rem ---- Basischecks ----
if not exist "%SCRIPT%" (
  echo [FOUT] Script niet gevonden: %SCRIPT%
  >>"%LOG%" echo [FOUT] Script niet gevonden: %SCRIPT%
  goto :END_FAIL
)
if not exist "%ASSETSDIR%" (
  echo [FOUT] Assets-map niet gevonden: %ASSETSDIR%
  >>"%LOG%" echo [FOUT] Assets-map niet gevonden: %ASSETSDIR%
  goto :END_FAIL
)

rem ---- Zorg dat de score-map bestaat (voor scores.json) ----
if not exist "%ASSETSDIR%\score" (
  mkdir "%ASSETSDIR%\score" 2>nul
)

rem ---- Als app nog draait: afsluiten zodat .exe overschreven kan worden ----
tasklist /FI "IMAGENAME eq %APPNAME%.exe" | find /I "%APPNAME%.exe" >nul 2>&1
if not errorlevel 1 (
  echo [INFO] %APPNAME%.exe draait nog; afsluiten...
  taskkill /IM "%APPNAME%.exe" /F >nul 2>&1
  timeout /t 1 >nul
)

rem ---- Icoon alleen als 'ie bestaat (correct gequote) ----
set "ICON_SWITCH="
if exist "%ICON%" (
  set ICON_SWITCH=--icon "%ICON%"
) else (
  echo [WAARSCHUWING] Icoon ontbreekt: %ICON%
  >>"%LOG%" echo [WAARSCHUWING] Icoon ontbreekt: %ICON%
)

echo [INFO] Bouwen... (%PYI_MODE%) >>"%LOG%"

rem ====== De build (geen backslash-escapes voor quotes) =================
%PYCMD% -m PyInstaller %CLEAN% -y ^
 --name "%APPNAME%" %PYI_MODE% --windowed ^
 %ICON_SWITCH% ^
 --add-data "%ASSETSDIR%;assets" ^
 --hidden-import PIL._tkinter_finder ^
 --distpath "%DISTPATH%" --workpath "%WORKPATH%" --specpath "%SPECPATH%" ^
 "%SCRIPT%" >>"%LOG%" 2>&1

if errorlevel 1 goto :END_FAIL
rem ======================================================================

echo.
if /I "%PYI_MODE%"=="--onefile" (
  echo [OK] Build gereed: "%DISTPATH%\%APPNAME%.exe"
  >>"%LOG%" echo [OK] Build gereed: %DISTPATH%\%APPNAME%.exe
) else (
  echo [OK] Build gereed: "%DISTPATH%\%APPNAME%\%APPNAME%.exe"
  >>"%LOG%" echo [OK] Build gereed: %DISTPATH%\%APPNAME%\%APPNAME%.exe
)

rem ---- Alleen starten als expliciet gevraagd met 'start' ----
if "%AUTO_START%"=="1" (
  if /I "%PYI_MODE%"=="--onefile" (
    start "" "%DISTPATH%\%APPNAME%.exe"
  ) else (
    start "" "%DISTPATH%\%APPNAME%\%APPNAME%.exe"
  )
)

echo.
echo [INFO] Klaar. Log: %LOG%
endlocal
exit /b 0

:END_FAIL
echo [FOUT] Build mislukt. Log wordt geopend...
start "" notepad "%LOG%"
echo.
pause
endlocal
exit /b 1
