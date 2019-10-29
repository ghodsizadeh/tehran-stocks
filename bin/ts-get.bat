@echo off
set PYFILE=%~f0
set PYFILE=%PYFILE:~0,-4%
"python.exe" "%PYFILE%" %*