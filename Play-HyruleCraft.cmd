@echo off
setlocal
title HyruleCraft
cd /d "%~dp0"
echo HyruleCraft - experimental Creative integration
echo Enter: confirm   Arrows: choose   Backspace: back
echo WASD: move   Space: jump   E: inventory   Escape: pause
echo F5: camera   F7: release input   F8: nearby recovery   F11: fullscreen
echo Alt-Tab: switch apps   Double-tap Space: Creative flight
where py >nul 2>nul
if errorlevel 1 (
 python -u "%~dp0launch.py" %*
) else (
 py -3 -u "%~dp0launch.py" %*
)
if errorlevel 1 (
 echo Setup or runtime error. Run this shortcut with --doctor for setup checks.
 pause
)
