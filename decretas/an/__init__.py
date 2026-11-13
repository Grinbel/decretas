"""Archives nationales index pipeline (series BB/34, decree inventories 1883-1948).

Reads the XML-EAD inventory exports stored under ``data/raw/an/`` (never the network),
turns them into decrees, person notices, spouses and children, classifies what
concerns Algeria and exports the "Algeria tier" to the static site.

Run it with ``python3 -m decretas.an --help`` from the repository root.
"""
