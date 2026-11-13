"""Printed-source pipeline: the Bulletin officiel du Gouvernement général de l'Algérie
(BOGGA), 1861-1888, as readable on the Internet Archive.

Modules: `catalogue` (volumes and link templates), `moisson` (harvest), `volume` (loading
the OCR text page by page), `dates`, `texte`, `segmentation` (decrees and person entries),
`controle` (quality control against each volume's own tables), `export` (site data files).
Run `python3 -m decretas.bogga --help` from the repository root.
"""
