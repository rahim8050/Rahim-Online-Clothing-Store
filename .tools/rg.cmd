@echo off
REM rg shim: safe defaults + 60s timeout
setlocal
for %%I in (rg.exe) do set RG=%%~$PATH:I
if "%RG%"=="" (exit /b 0)
start /b "" "%RG%" -n -S --hidden --no-config --max-filesize 1M %* > rg.out
timeout /t 60 >nul
tasklist /FI "IMAGENAME eq rg.exe" | find /I "rg.exe" >nul && taskkill /F /IM rg.exe >nul
type rg.out 2>nul
del rg.out 2>nul
endlocal
