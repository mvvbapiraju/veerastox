from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Clean generated workspace artifacts (raw data, processed data, reports)"
    )
    p.add_argument("--raw", action="store_true", help="Clean only data/raw")
    p.add_argument("--processed", action="store_true", help="Clean only data/processed")
    p.add_argument("--reports", action="store_true", help="Clean only reports")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting anything",
    )
    return p.parse_args()


def _clean_dir(path: Path, dry_run: bool) -> int:
    removed = 0
    if not path.exists():
        return removed

    for child in path.iterdir():
        removed += 1
        if dry_run:
            print(f"would remove: {child}")
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        print(f"removed: {child}")
    return removed


def main() -> None:
    args = parse_args()

    explicit = args.raw or args.processed or args.reports
    targets: list[Path] = []
    if not explicit or args.raw:
        targets.append(Path("data/raw"))
    if not explicit or args.processed:
        targets.append(Path("data/processed"))
    if not explicit or args.reports:
        targets.append(Path("reports"))

    total_removed = 0
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        total_removed += _clean_dir(target, dry_run=args.dry_run)

    if args.dry_run:
        print(f"dry run complete: {total_removed} path(s) would be removed")
    else:
        print(f"cleanup complete: removed {total_removed} path(s)")


if __name__ == "__main__":
    main()
