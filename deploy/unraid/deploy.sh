#!/bin/sh
# Ausliefern und Rückrollen auf Unraid (deploy/unraid/README.md Abschnitt 5).
#   ./deploy.sh                          Anwendung (Konfigurator, Büro, Analyse) bauen und ausliefern
#   ./deploy.sh rollback REL             auf eine frühere Release zurück (releases.log)
set -eu
cd "$(dirname "$0")"

smoke_test() {
  i=0
  while [ $i -lt 60 ]; do
    if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/ready')" 2>/dev/null \
      && docker compose exec -T engine node -e "fetch('http://127.0.0.1:8090/health').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))" 2>/dev/null; then
      return 0
    fi
    i=$((i + 1))
    sleep 3
  done
  return 1
}

activate() {
  docker tag "emprise-backend:$1" emprise-backend:current
  docker tag "emprise-web:$1" emprise-web:current
  # Releases vor dem Rechendienst (HM0) haben kein engine-Image; dann bleibt das aktuelle stehen
  if docker image inspect "emprise-engine:$1" >/dev/null 2>&1; then
    docker tag "emprise-engine:$1" emprise-engine:current
  fi
  docker compose up -d --remove-orphans --force-recreate migrate api worker worker-long web engine
  docker compose up -d
  if smoke_test; then
    echo "$(date -Iseconds) $1" >> releases.log
    echo "Release $1 bereit"
  else
    echo "Rauchtest fehlgeschlagen: docker compose logs api migrate engine" >&2
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
echo "Baue Release $release"
EMPRISE_RELEASE="$release" docker compose build migrate web engine
activate "$release"
