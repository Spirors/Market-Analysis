---
type: source
title: "Test isolation — autouse conftest.py redirects every user-data path"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/test-isolation-autouse-conftest-py-redirects-every-user-data-path-2026-09-08.md"
original_sha256: "daf6497cd4619ea16e8b66c4ea1d22bab70b1d151cd8e3bfb73820f2b28406f1"
stored_path: ".raw/captured/daf6497cd4619ea16e8b66c4ea1d22bab70b1d151cd8e3bfb73820f2b28406f1.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Test isolation — autouse conftest.py redirects every user-data path

An autouse fixture in tests/conftest.py redirects every user-data path (PORTFOLIOS_PATH, DATA_DIR, CACHE_DIR, EVENTS_PATH, etc.) to tmp_path so no test can accidentally write to the user's real data. Module-level path constants are patched on the importing module, not just on config.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/test-isolation-autouse-conftest-py-redirects-every-user-data-path-2026-09-08.md`
  - SHA-256: `daf6497cd4619ea16e8b66c4ea1d22bab70b1d151cd8e3bfb73820f2b28406f1`
- **Captured:** `.raw/captured/daf6497cd4619ea16e8b66c4ea1d22bab70b1d151cd8e3bfb73820f2b28406f1.md`

## Key claims

- Every user-data path is redirected by the autouse fixture; module-level constants are patched on the importing module since they bind at import time.
- New user-data paths must be added to _isolate_data_files in the same commit they are introduced.

## Concepts

- `test-isolation`
- `autouse-fixture`
- `user-data-safety`

## Entities

- `tests/conftest.py`
- `_isolate_data_files`
- `PORTFOLIOS_PATH`
