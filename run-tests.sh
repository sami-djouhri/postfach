#!/usr/bin/env bash
# Testlauf des Briefkastens.
#
# Gelaufen wird in einem Wegwerf-Container aus dem GEBAUTEN Image, nicht gegen
# den Quellbaum. Das ist Absicht und folgt der Lehre aus dem Saganta-Lauf vom
# 30.08.2026: ein Test gegen den Quellbaum beweist, dass die Datei stimmt, nicht
# dass der laufende Dienst sie hat. Genau diese Luecke liess dort einen Filter in
# sieben von acht Diensten wirkungslos, waehrend alles gruen aussah.
#
# Warum nicht `docker exec` in den laufenden Container: dessen Rootfs ist
# read_only, die Testdateien kommen dort nicht hinein. Der Wegwerf-Container
# haengt sie stattdessen ein und ist danach weg.
#
# Erwartung: "Ran 9 tests ... OK". Laeuft eine kleinere Zahl durch, wurde ein
# Modul still uebersprungen. Das ist nicht als gruen zu verbuchen.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${IMAGE:-postfach-briefkasten}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image '$IMAGE' fehlt. Erst bauen:"
  echo "  docker compose build"
  exit 1
fi

# --user 0:0 nur fuer den Lauf: die Testdateien tragen im Quellbaum 660, der
# Dienst-Nutzer koennte sie sonst nicht lesen. Der Container ist ein
# Wegwerfstueck, die Rechte im Baum bleiben unangetastet.
# DATABASE_URL zeigt ins Nirgendwo: diese Tests fassen keine Datenbank an, und
# ein Tippfehler soll nicht aus Versehen die echte oeffnen.
exec docker run --rm --user 0:0 \
  --network none \
  -v "$PWD/tests:/pruefung:ro" \
  -e DATABASE_URL=sqlite:////tmp/nicht-benutzt.db \
  -w /app \
  "$IMAGE" \
  python -m unittest discover -s /pruefung -t /pruefung -v
