"""Entry point of ``python3 -m decretas``: build, verify and serve the static site (see decretas/site.py)."""
import sys

from .site import main

if __name__ == "__main__":
    sys.exit(main())
