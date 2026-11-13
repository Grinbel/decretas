#!/usr/bin/env bash
# Download the XML-EAD export of each Archives nationales decree inventory, once.
#
# Usage:
#   scripts/telecharger-inventaires.sh                   # every inventory of scripts/inventaires-decrets.txt
#   scripts/telecharger-inventaires.sh FRAN_IR_057268    # only the ones given
#   scripts/telecharger-inventaires.sh --simulation      # print what would be fetched, send nothing
#   scripts/telecharger-inventaires.sh --delai 10        # wait 10 s between requests (default 5)
#   scripts/telecharger-inventaires.sh --rafraichir      # download again into a NEW dated directory
#   DRY_RUN=1 DELAY=10 scripts/telecharger-inventaires.sh  # same as --simulation --delai 10
#
# Rules (owner's decisions of 2026-10-16, revised 2026-11-11):
#   - honest, identifying User-Agent, never a browser disguise;
#   - slow: one request every DELAY seconds (5 by default), one connection, no parallelism;
#   - the site's robots.txt discourages robots: this script stays a rare, gentle, declared visitor
#     and NEVER works around an active block (no retry, no other address, no changed identity);
#   - a file already on disk is never requested again;
#   - it stops at the first refusal (403, 429, anti-bot page, any unexpected answer);
#   - 502, 503, 504 or no answer mean "the site is down": it stops, to be run again LATER by hand.
#
# --rafraichir: the indexing of the Archives nationales advances, so an inventory can change.
#   A refresh never overwrites the reference files: it writes a complete, separate set in
#   data/raw/an/rafraichi-AAAA-MM-JJ/ with its own manifest.jsonl, to be compared and built with
#   `python3 -m decretas.an construire --source data/raw/an/rafraichi-AAAA-MM-JJ`.
#
# Manifest (one JSON object per line): id, url, http, bytes, sha256, saved_as, at, ok
#   [+ reason when ok is false; + same_as_reference when refreshing].
#
# Exit codes: 0 done; 1 refusal; 2 bad usage; 3 site down or no answer; 4 truncated download.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REFERENCE="${DECRETAS_AN_DIR:-$ROOT/data/raw/an}"
LIST="$ROOT/scripts/inventaires-decrets.txt"
DELAY="${DELAY:-5}"
DRY_RUN="${DRY_RUN:-0}"
REFRESH=0
UA="decretas/0.2 (recherche genealogique non commerciale; projet libre et gratuit)"
BASE="https://www.siv.archives-nationales.culture.gouv.fr/siv/rechercheconsultation/consultation/ir/exportXML.action?irId="

usage() {
  cat <<'AIDE'
Télécharge une fois l'export XML-EAD de chaque inventaire de décrets des Archives nationales.

Utilisation :
  scripts/telecharger-inventaires.sh                   tous les inventaires de scripts/inventaires-decrets.txt
  scripts/telecharger-inventaires.sh FRAN_IR_057268    seulement ceux qui sont donnés
Options :
  --simulation     affiche ce qui serait demandé, n'envoie rien (ou DRY_RUN=1)
  --delai N        attente de N secondes entre deux requêtes (défaut 5, minimum 5 ; ou DELAY=N)
  --rafraichir     télécharge un jeu complet dans un NOUVEAU dossier daté data/raw/an/rafraichi-AAAA-MM-JJ/,
                   sans jamais écraser les fichiers de référence
  --aide           affiche cette aide
Codes de sortie : 0 terminé ; 1 refus ; 2 mauvais usage ; 3 site en panne ou sans réponse ; 4 fichier tronqué.
Un fichier déjà présent n'est jamais redemandé. Le script s'arrête au premier refus et ne le contourne pas.
AIDE
}

ids=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --rafraichir) REFRESH=1 ;;
    --simulation) DRY_RUN=1 ;;
    --delai)
      [ "$#" -ge 2 ] || { echo "--delai attend un nombre de secondes" >&2; exit 2; }
      DELAY="$2"; shift ;;
    --aide|-h|--help) usage; exit 0 ;;
    -*) echo "option inconnue : $1 (voir --aide)" >&2; exit 2 ;;
    *) ids+=("$1") ;;
  esac
  shift
done

[[ "$DELAY" =~ ^[0-9]+$ ]] || { echo "délai invalide : $DELAY (nombre entier de secondes)" >&2; exit 2; }
if [ "$DELAY" -lt 5 ]; then
  echo "délai de $DELAY s refusé : 5 s au minimum entre deux requêtes" >&2
  exit 2
fi

if [ "${#ids[@]}" -eq 0 ]; then
  # keep the identifier, drop comments and blank lines
  mapfile -t ids < <(sed -e 's/#.*//' -e 's/[[:space:]]//g' "$LIST" | grep -v '^$')
fi

if [ "$REFRESH" = "1" ]; then
  OUT="$REFERENCE/rafraichi-$(date +%F)"
else
  OUT="$REFERENCE"
fi
MANIFEST="$OUT/manifest.jsonl"

record() { # id url http bytes sha256 saved_as ok [extra JSON members]
  printf '{"id":"%s","url":"%s","http":"%s","bytes":%s,"sha256":"%s","saved_as":"%s","at":"%s","ok":%s%s}\n' \
    "$1" "$2" "$3" "$4" "$5" "$6" "$(date -Iseconds)" "$7" "${8:-}" >> "$MANIFEST"
}

summary() { echo "Bilan : $fetched téléchargé(s), $skipped déjà présent(s)." >&2; }

fetched=0 skipped=0
[ "$DRY_RUN" = "1" ] || mkdir -p "$OUT"

for id in "${ids[@]}"; do
  [[ "$id" =~ ^FRAN_IR_[0-9]{6}$ ]] || { echo "identifiant invalide : $id" >&2; exit 2; }
  target="$OUT/$id.xml"
  url="$BASE$id"

  if [ -s "$target" ]; then
    echo "déjà là     $id"
    skipped=$((skipped + 1))
    continue
  fi

  if [ "$DRY_RUN" = "1" ]; then
    echo "simulation  $id  <-  $url  ->  $target"
    continue
  fi

  tmp="$target.part"
  code=$(curl -sS --proto '=https' --max-time 300 -A "$UA" -o "$tmp" -w '%{http_code}' "$url") || code="000"
  size=$(stat -c %s "$tmp" 2>/dev/null || echo 0)

  case "$code" in
    200) ;;
    000|502|503|504)
      rm -f "$tmp"
      record "$id" "$url" "$code" "$size" "" "" false ',"reason":"site-down"'
      echo "SITE EN PANNE  $id : HTTP $code — arrêt. Réessayer plus tard, à la main ; ne pas relancer en boucle." >&2
      summary
      exit 3 ;;
    *)
      [ -f "$tmp" ] && mv "$tmp" "$OUT/$id.refus"
      record "$id" "$url" "$code" "$size" "" "$id.refus" false ',"reason":"refused"'
      echo "REFUS       $id : HTTP $code, $size octets — arrêt. Réponse gardée dans $OUT/$id.refus" >&2
      summary
      exit 1 ;;
  esac

  # An anti-bot challenge can come back as a small HTML page with a 200: check the content too.
  if ! head -c 1024 "$tmp" | grep -q -e '<?xml' -e '<ead'; then
    mv "$tmp" "$OUT/$id.refus"
    record "$id" "$url" "$code" "$size" "" "$id.refus" false ',"reason":"not-xml"'
    echo "REFUS       $id : HTTP 200 mais la réponse n'est pas un XML ($size octets) — arrêt. Réponse gardée dans $OUT/$id.refus" >&2
    summary
    exit 1
  fi
  # A complete export ends with </ead>.
  if ! tail -c 64 "$tmp" | grep -q '</ead>'; then
    mv "$tmp" "$OUT/$id.tronque"
    record "$id" "$url" "$code" "$size" "" "$id.tronque" false ',"reason":"truncated"'
    echo "TRONQUÉ     $id : le fichier ne se termine pas par </ead> ($size octets) — arrêt. Gardé dans $OUT/$id.tronque" >&2
    summary
    exit 4
  fi

  mv "$tmp" "$target"
  sha=$(sha256sum "$target" | cut -d' ' -f1)
  extra=""
  if [ "$REFRESH" = "1" ] && [ -s "$REFERENCE/$id.xml" ]; then
    if [ "$sha" = "$(sha256sum "$REFERENCE/$id.xml" | cut -d' ' -f1)" ]; then
      extra=',"same_as_reference":true'
      echo "téléchargé  $id  ($size octets) — identique au fichier de référence"
    else
      extra=',"same_as_reference":false'
      echo "téléchargé  $id  ($size octets) — DIFFÉRENT du fichier de référence"
    fi
  else
    echo "téléchargé  $id  ($size octets)"
  fi
  record "$id" "$url" "200" "$size" "$sha" "$id.xml" true "$extra"
  fetched=$((fetched + 1))
  sleep "$DELAY"
done

echo "Bilan : $fetched téléchargé(s), $skipped déjà présent(s)."
