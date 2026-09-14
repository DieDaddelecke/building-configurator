#!/bin/sh
# Nächtlicher Datenbank-Dump nach /backups (Unraid-Share). Aufruf mit "now" für eine sofortige Sicherung:
#   docker compose run --rm backup now
set -eu

HOUR="${BACKUP_HOUR:-3}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

dump() {
  stamp=$(date +%Y%m%d-%H%M%S)
  part="/backups/.emprise-$stamp.dump.part"
  # spatial_ref_sys gehört zu PostGIS und entsteht mit CREATE EXTENSION neu
  if pg_dump --format=custom --no-owner --exclude-table-data=public.spatial_ref_sys --file="$part"; then
    mv "$part" "/backups/emprise-$stamp.dump"
    date -Iseconds > /backups/last-success
    find /backups -maxdepth 1 -name 'emprise-*.dump' -mtime +"$KEEP_DAYS" -delete
    echo "backup ok: emprise-$stamp.dump"
  else
    rm -f "$part"
    date -Iseconds > /backups/last-failure
    echo "backup failed" >&2
    return 1
  fi
}

if [ "${1:-}" = "now" ]; then
  dump
  exit $?
fi

echo "backup scheduler: daily at ${HOUR}:00, keep ${KEEP_DAYS} days"
while true; do
  now=$(date +%s)
  target=$(date -d "today ${HOUR}:00" +%s)
  if [ "$target" -le "$now" ]; then
    target=$(date -d "tomorrow ${HOUR}:00" +%s)
  fi
  sleep $((target - now))
  dump || true
done
