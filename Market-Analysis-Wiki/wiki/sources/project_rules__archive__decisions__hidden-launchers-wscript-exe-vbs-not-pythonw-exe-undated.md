---
type: source
title: "Hidden launchers — wscript.exe + VBS, not pythonw.exe"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/hidden-launchers-wscript-exe-vbs-not-pythonw-exe-undated.md"
original_sha256: "5820bc520c16a9508547a1ea42e101d608803507c8315bc50550d3fafeb1f942"
stored_path: ".raw/captured/5820bc520c16a9508547a1ea42e101d608803507c8315bc50550d3fafeb1f942.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Hidden launchers — wscript.exe + VBS, not pythonw.exe

pythonw.exe silently aborts before binding due to inconsistent console-handle state after parent detach. The working pattern is wscript.exe launching a VBS script that calls shell.Run 'python args', 0, False (hidden + non-blocking). Never reintroduce pythonw.exe.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/hidden-launchers-wscript-exe-vbs-not-pythonw-exe-undated.md`
  - SHA-256: `5820bc520c16a9508547a1ea42e101d608803507c8315bc50550d3fafeb1f942`
- **Captured:** `.raw/captured/5820bc520c16a9508547a1ea42e101d608803507c8315bc50550d3fafeb1f942.md`

## Key claims

- pythonw.exe must not be used for hidden launchers; use wscript.exe + VBS with shell.Run WindowStyle=0 instead.

## Concepts

- `hidden-launchers`
- `vbs-wrapper`
- `process-lifecycle`

## Entities

- `wscript.exe`
- `pythonw.exe`
- `launch.vbs`
