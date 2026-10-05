@echo off
rem Windows launcher: runs the Python script that sits next to this file.
setlocal
set "SCRIPT=%~dp0codex-claude-code-secret-cleaner"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 "%SCRIPT%" %*
) else (
    python "%SCRIPT%" %*
)
exit /b %ERRORLEVEL%
