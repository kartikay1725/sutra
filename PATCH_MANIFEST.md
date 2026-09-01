# SUTRA Priority 5 — Real Insights

## Replace

- `backend/app/api/insights.py`

## Add

- `backend/tests/test_insights_api.py`

## What this changes

The repository Insights endpoint is now calculated from real repository records instead of hardcoded demo metrics.

It uses:

- successful `Deployment` records for deployment frequency
- terminal `CIJob` records for CI pass rate
- merged `PullRequest` + `Change` records for lead time
- `Actor.type` for agent vs human change split
- recent CI/deployment failures for the actionable signal

The endpoint remains repository-owner scoped.

## No migration required

This patch uses existing tables and columns.

## Validate

From `D:\sutra\backend`:

```powershell
python -m compileall app/api/insights.py
pytest tests/test_insights_api.py -q
```
