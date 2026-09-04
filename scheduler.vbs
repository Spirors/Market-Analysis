' scheduler.vbs - hidden launcher for scheduled tasks
'
' Used by the Windows scheduled tasks installed via app/scheduler.py.
' Mirrors the launch.vbs pattern used by the desktop shortcut: wscript.exe
' runs python.exe with WindowStyle=0 (SW_HIDE) so no console window
' flashes when the task fires at 09:00 / 17:00 / every-4-hours.
'
' Pass the run.py arguments as command-line args to this script:
'   wscript.exe //nologo scheduler.vbs --refresh --logfile-prefix "..."
'
' Why not pythonw.exe?  pythonw is a GUI-subsystem app that tries to
' detach from the parent console on startup.  When that detach leaves
' OS console-handle state inconsistent (see the warning in launch.bat),
' pythonw aborts silently before binding.  Using wscript.exe + python.exe
' with WindowStyle=0 avoids the detach entirely: python is a console-
' subsystem app and starts with a (hidden) console allocated cleanly.
'
' The script rebuilds the python command line from its own argv, quotes
' any arg containing a space (so paths like "C:\Users\...\data\logs\refresh"
' stay one token), and returns immediately (False = do not wait).

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Run from the repo root (this script's directory) so python resolves run.py.
shell.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)

cmd = "python"
For i = 0 To WScript.Arguments.Count - 1
    arg = WScript.Arguments(i)
    If InStr(arg, " ") > 0 Then
        cmd = cmd & " """ & arg & """"
    Else
        cmd = cmd & " " & arg
    End If
Next

' WindowStyle=0 (SW_HIDE) starts python with a hidden window.
' False means wscript.exe does not wait for python to exit.
shell.Run cmd, 0, False
