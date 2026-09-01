@echo off
rem Visible-cmd launcher. For the hidden-window variant used by the
rem desktop shortcut, see launch.vbs (the .lnk targets wscript.exe).
rem Use python (not pythonw). pythonw tries to detach from the parent
rem console on startup; when launched from cmd.exe via a .lnk
rem ShellExecute, that detach can leave OS console-handle state
rem inconsistent and pythonw aborts silently before uvicorn binds.
rem python inherits cmd's console cleanly.
cd /d "%~dp0"
python run.py --open-browser
