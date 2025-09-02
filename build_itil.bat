
@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ==========================================================
rem  Wrapper: herstart in eigen venster dat NA afloop sluit
rem ==========================================================
if /I "%~1" NEQ "run" (
  start "ITIL4Foundation_Build" "%ComSpec%" /c "%~f0" run
  exit /b
)

cd /d "%~dp0"
title ITIL4Foundation_Build
color 0A

rem =================== Project-instellingen =================
set "SCRIPT=itil.py"
set "APPNAME=ITIL 4 Foundation"
set "ICON=assets\afbeeldingen\itil_4_icon2.ico"
set "ASSETSDIR=assets"
set "DISTPATH=."
set "WORKPATH=build"
set "SPECPATH=."
set "LOG=%~dp0build_last.log"

rem Opties via parameters
set "AUTO_START=0"
set "PYI_MODE=--onefile"
set "CLEAN="
for %%A in (%*) do (
  if /I "%%~A"=="start"  set "AUTO_START=1"
  if /I "%%~A"=="onedir" set "PYI_MODE=-D"
  if /I "%%~A"=="clean"  set "CLEAN=--clean"
)

rem Lokale Python-installer zoeken (assets\python\python*.exe)
set "PY_LOCAL_INSTALLER="
if exist "assets\python\" (
  for %%F in ("assets\python\python*.exe") do (
    set "PY_LOCAL_INSTALLER=%%~fF"
    goto :_foundPy
  )
)
:_foundPy

rem =================== Log-header ===========================
> "%LOG%" echo ----------------------------------------------------------
>>"%LOG%" echo Build gestart: %DATE% %TIME%
>>"%LOG%" echo Werkmap: %CD%
>>"%LOG%" echo ----------------------------------------------------------
echo [INFO] Log: "%LOG%"

rem =================== Python zoeken (robuust) ==============
set "PYCMD="
for %%P in (py pyw python python3) do (
  %%P -c "import sys" >nul 2>&1 && (
    set "PYCMD=%%P"
    goto :HAVE_PY
  )
)
goto :NO_PYTHON

:HAVE_PY
for /f "delims=" %%V in ('%PYCMD% -c "import sys;print(sys.version)" 2^>nul') do set "PYVER=%%V"
echo [INFO] Python gevonden: %PYCMD%
echo [INFO] Versie: %PYVER%
echo [INFO] Python gevonden: %PYCMD%  %PYVER%>>"%LOG%"

rem =================== PyInstaller check ====================
%PYCMD% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo [INFO] PyInstaller niet gevonden. Installeren...
  echo [INFO] PyInstaller niet gevonden. Installeren...>>"%LOG%"
  %PYCMD% -m pip install -U pyinstaller >>"%LOG%" 2>&1
  if errorlevel 1 goto :END_FAIL
)

rem =================== Pillow check =========================
%PYCMD% -c "import PIL" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Pillow [PIL] niet gevonden. Installeren...
  echo [INFO] Pillow [PIL] niet gevonden. Installeren...>>"%LOG%"
  %PYCMD% -m pip install -U pillow >>"%LOG%" 2>&1
  if errorlevel 1 (
    echo [FOUT] Installeren van Pillow is mislukt.
    echo [FOUT] Pillow install fail.>>"%LOG%"
    goto :END_FAIL
  )
)

rem =================== Basischecks =========================
if not exist "%SCRIPT%" (
  echo [FOUT] Script niet gevonden: %SCRIPT%
  echo [FOUT] Script niet gevonden: %SCRIPT%>>"%LOG%"
  goto :END_FAIL
)
if not exist "%ASSETSDIR%" (
  echo [FOUT] Assets-map niet gevonden: %ASSETSDIR%
  echo [FOUT] Assets-map niet gevonden: %ASSETSDIR%>>"%LOG%"
  goto :END_FAIL
)

rem Score-map garanderen
if not exist "%ASSETSDIR%\score" mkdir "%ASSETSDIR%\score" 2>nul

rem =================== App afsluiten indien actief ==========
tasklist /FI "IMAGENAME eq %APPNAME%.exe" | find /I "%APPNAME%.exe" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  echo [INFO] %APPNAME%.exe draait; afsluiten...
  taskkill /IM "%APPNAME%.exe" /F >nul 2>&1
  timeout /t 1 >nul
)

rem =================== Icoon switch =========================
set "ICON_SWITCH="
if exist "%ICON%" (
  set "ICON_SWITCH=--icon ""%ICON%"""
) else (
  echo [WAARSCHUWING] Icoon ontbreekt: %ICON%
  echo [WAARSCHUWING] Icoon ontbreekt: %ICON%>>"%LOG%"
)

echo [INFO] Bouwen... %PYI_MODE%
echo [INFO] Bouwen... %PYI_MODE%>>"%LOG%"

rem =================== BUILD ===============================
%PYCMD% -m PyInstaller %CLEAN% -y ^
 --name "%APPNAME%" %PYI_MODE% --windowed ^
 %ICON_SWITCH% ^
 --add-data "%ASSETSDIR%;assets" ^
 --hidden-import PIL._tkinter_finder ^
 --distpath "%DISTPATH%" --workpath "%WORKPATH%" --specpath "%SPECPATH%" ^
 "%SCRIPT%" >>"%LOG%" 2>&1

if errorlevel 1 goto :END_FAIL

echo [OK] Build gereed: "%DISTPATH%\%APPNAME%.exe"
echo [OK] Build gereed: %DISTPATH%\%APPNAME%.exe>>"%LOG%"

if "%AUTO_START%"=="1" (
  start "" "%DISTPATH%\%APPNAME%.exe"
)

goto :END_OK

rem =================== Geen Python gevonden =================
:NO_PYTHON
echo [FOUT] Python is niet gevonden op dit systeem.
echo.
if defined PY_LOCAL_INSTALLER (
  echo Lokale Python-installer gevonden:
  setlocal EnableDelayedExpansion
  echo(  !PY_LOCAL_INSTALLER!
  endlocal
  echo.
  call :ASK "Python nu vanaf lokale installer installeren? [j/n] " ANSW
  if /I "%ANSW%"=="j" (
    timeout /t 3 /nobreak >nul
    start "" /wait "%PY_LOCAL_INSTALLER%" /passive InstallAllUsers=1 PrependPath=1 Include_pip=1
    goto :END_OK
  ) else (
    goto :END_FAIL
  )
) else (
  echo Geen lokale installer gevonden in: assets\python
  call :ASK "Python via winget installeren? [j/n] " ANSW2
  if /I "%ANSW2%"=="j" (
    winget install -e --id Python.Python.3
    goto :END_OK
  ) else (
    goto :END_FAIL
  )
)

rem =================== Einde/Exit codes ====================
:END_OK
endlocal
exit /b 0

:END_FAIL
echo [FOUT] Er is iets misgegaan. Log wordt geopend...
start "" notepad "%LOG%"
rem Laat het foutvenster open zodat je het ziet:
pause
endlocal
exit /b 1

rem =================== Subroutine ASK ======================
:ASK
setlocal EnableExtensions EnableDelayedExpansion
set "ANS="
set /p "ANS=%~1"
endlocal & set "%~2=%ANS%"
goto :EOF

