# Hidden launchers: `wscript.exe` + VBS, not `pythonw.exe` (undated)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Hidden launchers: `wscript.exe` + VBS, not `pythonw.exe`

`pythonw.exe` (the GUI-subsystem Python launcher) tries to detach from the
parent console on startup; when that detach leaves OS console-handle state
inconsistent, `pythonw` silently aborts before binding. The working pattern
is `wscript.exe <vbs-script> python args...` with the VBS setting
`shell.Run "python args", 0, False` (`WindowStyle=0` = `SW_HIDE`, `False` =
don't wait). Used by both `launch.vbs` (desktop shortcut) and
`scheduler.vbs` (Windows Task Scheduler tasks). If a third hidden launcher
is ever needed, copy this pattern — do not reintroduce `pythonw.exe`.

