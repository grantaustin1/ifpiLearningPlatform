#!/usr/bin/env bash
# Restores the database to the pre-UAT snapshot taken on 2026-07-30.
# Wipes EVERYTHING done after the snapshot (UAT org, courses, enrolments...).
set -euo pipefail

SNAPSHOT=/app/backend/snapshots/pre_uat_ifpi_lms.db
DB=/app/backend/ifpi_lms.db

if [ ! -f "$SNAPSHOT" ]; then
  echo "ERROR: snapshot not found at $SNAPSHOT" >&2
  exit 1
fi

echo "Restoring $DB from snapshot ($(du -h "$SNAPSHOT" | cut -f1))..."
sudo supervisorctl stop backend
cp "$SNAPSHOT" "$DB"
sudo supervisorctl start backend
sleep 5
curl -sf http://localhost:8001/api/health && echo " — backend healthy, reset complete."
