"""Entry point for the bundled afterwit package (no install step needed).

`scripts/afterwit.sh` runs this file with whichever interpreter works; where
sh isn't available (e.g. PowerShell), run it directly:

    python <plugin>/scripts/afterwit_cli.py stats
"""

import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from afterwit.cli import main  # noqa: E402

main()
