from __future__ import annotations

import runpy
import sys
import urllib.request
from pathlib import Path


def main() -> None:
    opener = urllib.request.build_opener()
    opener.addheaders = [
        (
            "User-Agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
    ]
    urllib.request.install_opener(opener)

    project_root = Path(__file__).resolve().parents[3]
    script_path = project_root / "scripts" / "beta_top_indexes.py"

    if not script_path.exists():
        raise FileNotFoundError(f"Missing script: {script_path}")

    sys.argv = [str(script_path), "--index", "sp500", *sys.argv[1:]]
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
