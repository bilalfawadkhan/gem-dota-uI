"""PyInstaller entry point: the frozen app starts here.

``multiprocessing.freeze_support()`` must run first. The parse job starts worker processes with
the "spawn" method, and in a frozen Windows build each of them is this same executable;
``freeze_support()`` is what makes such a child run its job instead of opening another window.
"""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from gemstudio.__main__ import main

    sys.exit(main())
