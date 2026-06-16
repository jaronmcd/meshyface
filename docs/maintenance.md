# Maintenance Commands

This page covers commands that inspect or repair local dashboard data and then
exit. They are meant for operators maintaining an existing Meshyface install,
not for normal dashboard startup.

## Rebuild Environment Rollups

The dashboard stores raw packet history in SQLite and also keeps one-minute
environment metric rollups in `environment_metrics_1m`. Those rollups make
history views faster and are normally updated while the dashboard is running.

Use the backfill command when an existing history database has packet history
but missing or stale environment rollups.

```bash
python mesh_dashboard.py \
  --history-db mesh_dashboard_history.sqlite3 \
  --backfill-environment-rollups
```

This is a one-shot command: it opens the selected history database, scans saved
packets, writes environment rollups, prints a summary, and exits. It does not
start the web dashboard and does not connect to a radio.

For a full rebuild, clear existing rollups first:

```bash
python mesh_dashboard.py \
  --history-db mesh_dashboard_history.sqlite3 \
  --backfill-environment-rollups \
  --backfill-environment-rollups-reset
```

Use `--backfill-environment-rollups-reset` when you want the rollup table to
match the saved packet history exactly. Without reset, the command merges into
existing one-minute buckets, which can increase counts if the same packets were
already included.

Backfill uses the exact `--history-db` path. If you need to backfill an older
per-radio database, pass that profiled `.radio-...` filename explicitly.

The completion summary reports:

- `scanned`: packet rows read from history
- `usable`: packet rows with usable JSON payloads
- `bad`: packet rows skipped because stored JSON could not be parsed
- `rows_before`: environment rollup rows present before the run
- `rows_after`: environment rollup rows present after the run
- `rows_delta`: new rollup rows added during the run

Stop the dashboard or work on a database copy before running maintenance
commands against an active install.
