#!/bin/sh
# Ausliefern und Rückrollen auf Unraid (docs/BETRIEB.md Abschnitt 2).
#   ./deploy.sh                          Hauskonfigurator bauen und ausliefern
#   ./deploy.sh rollback REL             Hauskonfigurator auf eine frühere Release zurück (releases.log)
#   ./deploy.sh analyse                  „Emprise Analyse“ ausliefern (AN0; dieselben Images, eigener Stack)
#   ./deploy.sh analyse rollback REL     Analyse-Stack zurückrollen
#   ./deploy.sh shared                   gemeinsame Datenbank beider Produkte starten (PLAN_G2_VOLLSTAENDIGKEIT
#                                        3.9); vor dem ersten Ausliefern eines Produkts, legt das Netz an
# Beide Produkte kommen aus einem Repository (D16); getrennt sind Datenbank, Speicher, Hostname und
# das Bild-Kennzeichen (`current` gegenüber `current-analyse`), damit ein Rückrollen nur einen Stack trifft.
set -eu
cd "$(dirname "$0")"

if [ "${1:-}" = "shared" ]; then
  # Keine eigenen Images: Postgres und Sicherung; Migrationen fahren die Produkte (migrate)
  docker compose -f compose.shared.yaml --env-file .env.shared up -d
  echo "Gemeinsamer Stack bereit (Netz emprise-shared)"
  exit 0
fi

if ! docker network inspect emprise-shared >/dev/null 2>&1; then
  echo "Netz emprise-shared fehlt: zuerst ./deploy.sh shared (README, Gemeinsame Daten)" >&2
  exit 1
fi

stack=konfigurator
if [ "${1:-}" = "analyse" ]; then
  stack=analyse
  shift
fi

if [ "$stack" = "analyse" ]; then
  tag=current-analyse
  compose() {
    docker compose -f compose.yaml -f compose.analyse.yaml --env-file .env.analyse "$@"
  }
else
  tag=current
  compose() {
    docker compose "$@"
  }
fi

smoke_test() {
  i=0
  while [ $i -lt 60 ]; do
    if compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/ready')" 2>/dev/null; then
      return 0
    fi
    i=$((i + 1))
    sleep 3
  done
  return 1
}

activate() {
  docker tag "emprise-backend:$1" "emprise-backend:$tag"
  docker tag "emprise-web:$1" "emprise-web:$tag"
  compose up -d --remove-orphans --force-recreate migrate api worker web
  compose up -d
  if smoke_test; then
    echo "$(date -Iseconds) $stack $1" >> releases.log
    echo "Release $1 bereit ($stack)"
  else
    echo "Rauchtest fehlgeschlagen: docker compose logs api migrate" >&2
    exit 1
  fi
}

if [ "${1:-}" = "rollback" ]; then
  release="${2:?Release angeben, siehe releases.log}"
  # Migrationen bleiben stehen; sie sind abwärtskompatibel (Plan 6.5)
  activate "$release"
  exit 0
fi

release=$(git -C ../.. rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M)
if [ -n "$(git -C ../.. status --porcelain 2>/dev/null)" ]; then
  release="$release-dirty"
fi
echo "Baue Release $release ($stack)"
EMPRISE_RELEASE="$release" compose build migrate web
activate "$release"
