#!/usr/bin/env python3
"""List the decrees of the Archives nationales inventories that concern Algeria.

Thin compatibility wrapper around ``python3 -m decretas.an decrets``: the parsing, the decree
taxonomy, the Algeria classes (A1, A2, A3, R), the reconciled dates and the cote checks all
live in the package ``decretas.an`` (see docs/format-donnees-an.md). No network access: the
links are copied from the XML, never followed.

Usage:
  scripts/lister-decrets-algeriens.py                      # -> data/derived/decrets-algeriens.csv
  scripts/lister-decrets-algeriens.py -o /tmp/liste.csv    # another output file
  scripts/lister-decrets-algeriens.py --tous               # every decree, not only Algeria
  scripts/lister-decrets-algeriens.py a.xml b.xml          # only these exports

What changed from the first version of this script: the cote is read from both <unitid> types
(it was empty on half of the rows); a decree is recognised by its structure, not by the first
word of its title; "Algeria" is a class (the admissions "aux droits de citoyen" without
territory are included) instead of the test 'alger' in the title; dates are reconciled with
the title; the unverified column lien_consultation is gone.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from decretas.an import ead, listing  # noqa: E402  (the repository root must be on the path first)

RAW = ROOT / "data" / "raw" / "an"
DEFAULT_OUT = ROOT / "data" / "derived" / "decrets-algeriens.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Liste en CSV des décrets des inventaires des Archives nationales.")
    parser.add_argument("-o", "--sortie", type=Path, default=DEFAULT_OUT, help="fichier CSV à écrire")
    parser.add_argument("--tous", action="store_true",
                        help="garder tous les décrets, pas seulement ceux des classes Algérie (A1, A2, A3, R)")
    parser.add_argument("fichiers", nargs="*", type=Path, help="XML à lire (défaut : data/raw/an/FRAN_IR_*.xml)")
    args = parser.parse_args()

    files = args.fichiers or ead.inventory_files(RAW)
    if not files:
        print(f"aucun XML dans {RAW}", file=sys.stderr)
        return 1
    try:
        records = listing.decree_records(files)
    except (ead.EadError, OSError) as error:
        print(f"échec : {error}", file=sys.stderr)
        return 1
    total = len(records)
    if not args.tous:
        records = listing.only_algeria(records)
    listing.write_csv(records, args.sortie)

    print(f"{len(records)} décrets écrits dans {args.sortie} (sur {total} lus)")
    by_class: dict[str, int] = {}
    for record in records:
        key = f"{record['classe_algerie']} / {record['etat']}"
        by_class[key] = by_class.get(key, 0) + 1
    for key, count in sorted(by_class.items()):
        print(f"  {count:>6}  classe {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
