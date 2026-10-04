"""Script d'entrée pour le bundle PyInstaller."""
import multiprocessing
import sys

multiprocessing.freeze_support()

from nourriture.app import main  # noqa: E402

sys.exit(main())
