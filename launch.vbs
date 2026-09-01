' Hidden launcher for python run.py --open-browser.
'
' Used by the desktop shortcut. No console window is shown.
' See launch.bat for the visible-cmd variant (shows uvicorn's
' logs, Ctrl+C to stop).
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
shell.Run "python run.py --open-browser", 0, False
