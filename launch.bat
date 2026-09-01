@echo off
rem Use python (not pythonw). pythonw is built for GUI apps and tries to
rem detach from the parent console on startup; when invoked from cmd.exe via
rem a .lnk ShellExecute, that detach can leave the OS console-handle state
rem inconsistent and pythonw aborts silently before uvicorn binds. python
rem inherits cmd's console cleanly. Trade-off: this cmd window stays open
rem with uvicorn's logs visible (Ctrl+C stops the server).
cd /d "%~dp0"
python run.py --open-browser
