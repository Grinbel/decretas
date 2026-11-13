"""Entry point of ``python3 -m decretas.an``."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
