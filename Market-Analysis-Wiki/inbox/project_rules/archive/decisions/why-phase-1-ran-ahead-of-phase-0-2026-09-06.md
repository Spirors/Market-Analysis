# Why Phase 1 ran ahead of Phase 0 (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Why Phase 1 ran ahead of Phase 0 (2026-09-06)

The roadmap's own rule is "don't start a Phase N+1 item while a Phase N
item is open," but the Phase 1 docs split (commits `52e5b92`, `8583711`)
went in while Phase 0 still had open bugs. The reason: Phase 0's open
bugs (`stuck-process`, `tickerTable.js` cross-section state) need durable
root-cause records that survive context resets, and the session-start
read-order + `project_rules/DECISIONS.md` + `project_rules/HANDOFF.md` + `project_rules/SESSION_LOG.md`
are exactly that mechanism. Diagnosing Phase 0 bugs without those docs in
place would re-introduce the "rediscover the failed approach the hard
way" failure mode. The Phase 0 work itself is still untouched and remains
the top of the next-actions list.

---

---

