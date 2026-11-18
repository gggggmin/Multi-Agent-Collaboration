# Local artifacts

This directory keeps generated tests, logs, document renders, and build caches out of the repository root.

The heavy subdirectories are intentionally ignored by Git. Recreate generated test suites with:

```bash
python scripts/verify_project.py
```
