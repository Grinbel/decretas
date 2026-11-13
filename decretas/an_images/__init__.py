"""Tools for the decrees that exist only as page images on the Archives nationales site.

Sub-commands of ``python3 -m decretas.an_images`` (messages are in French, like the rest of
the project's tooling):

- ``disponibilite``  one polite request that says whether the reading-room site answers;
- ``reprise``        the ordered probe plan to run when it does (exemplars of each case);
- ``metadonnees``    what an image file, its name and its URL encode (no third-party tool);
- ``lire``           transcription harness: page images -> name occurrences to be verified;
- ``plan-collecte``  size of a future collection of the image-only decrees.

Vocabulary: see CONTEXT.md. A name read from an image by a machine is an *indice*, never a
*citation*: every occurrence produced here carries a "to be verified on the image" flag and
is written under data/build/, never under site/data/.
"""

RACINE_DEPOT_PARENTS = 2  # decretas/an_images/__init__.py -> repository root is parents[2]
