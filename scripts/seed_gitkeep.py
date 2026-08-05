#!/usr/bin/env python3
"""Place .gitkeep in module notes/ and checklists/ directories that are still empty.

Git does not track empty directories, so a module scaffolded locally would lose its notes/ and
checklists/ on clone - and every link to them would 404. This keeps the scaffold intact until
real content arrives, and removes the marker once it does.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = (
    "# Placeholder so git tracks this directory until the first file lands.\n"
    "# Remove this file once real content is added.\n"
)


def main() -> int:
    added = removed = 0
    for group in ("playbooks", "domains"):
        base = ROOT / group
        if not base.is_dir():
            continue
        for module in sorted(base.iterdir()):
            if not module.is_dir():
                continue
            for sub in ("notes", "checklists"):
                directory = module / sub
                directory.mkdir(parents=True, exist_ok=True)
                keep = directory / ".gitkeep"
                has_content = any(
                    child.is_file() and child.name not in (".gitkeep", ".DS_Store")
                    for child in directory.iterdir()
                )
                if has_content:
                    if keep.exists():
                        keep.unlink()
                        removed += 1
                        print(f"removed {keep.relative_to(ROOT)}")
                elif not keep.exists():
                    keep.write_text(CONTENT, encoding="utf-8")
                    added += 1
                    print(f"added   {keep.relative_to(ROOT)}")

    print(f"\n{added} added, {removed} removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
