#!/usr/bin/env python3
"""Scaffold a knowledge note with valid frontmatter.

Deriving lifecycle/domain tags from the target module path removes the most common frontmatter
mistake (tags that do not match where the file actually lives), and starting at the lowest
evidence tier makes promotion a deliberate act rather than a default.

Run:  python3 tools/new_note.py --module domains/performance --slug snapmirror-initial-sync
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent

LIFECYCLE_BY_DIR = {
    "01-assess": "assess",
    "02-design": "design",
    "03-migrate": "migrate",
    "04-build": "build",
    "05-operate": "operate",
    "06-optimize": "optimize",
}
VALID_DOMAINS = {
    "data-protection",
    "data-utilization",
    "security-governance",
    "performance",
    "cost",
    "multiprotocol-identity",
}

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

TEMPLATE = """---
title: TODO - state the concern in one line, not a topic label
lifecycle: [{lifecycle}]
domains: [{domains}]
evidence: hypothesis
lang: {lang}
---

# TODO - same as title

> **Evidence**: `hypothesis` - 未検証の推論です。検証したら `evidence` を昇格し、
> `verified_on` と検証環境（ONTAP バージョン / リージョン / 構成）を追記してください。

## 結論

TODO - 読者が最初に知るべき判断を 1-3 行で。

## 背景 / 何が問題か

TODO

## 詳細

TODO

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | TODO |
| リージョン | TODO |
| 構成 | TODO |
| 検証日 | TODO |

> **注意**: 上記はこの環境での実測であり、一般的なサービス上限や本番環境での再現を
> 保証するものではありません。

## よくある誤解

| 誤解 | 実際 |
|---|---|
| TODO | TODO |

## 関連ドキュメント

- TODO
"""


def resolve_module(raw: str, lang: str) -> tuple[PurePosixPath, str, str] | None:
    """Accept either `domains/performance` or `docs/ja/domains/performance`.

    The short form is what CONTRIBUTING.md documents and what people type from memory; the long
    form is what shell completion produces now that the tree lives under docs/. Supporting both
    keeps the documented command working after the move instead of quietly breaking it.
    """
    parts = PurePosixPath(raw.strip("/")).parts
    if parts and parts[0] == "docs":
        if len(parts) != 4:
            print(
                "error: --module must be docs/<lang>/playbooks/<name> "
                "or docs/<lang>/domains/<name>",
                file=sys.stderr,
            )
            return None
        _, module_lang, group, name = parts
    elif len(parts) == 2:
        module_lang, group, name = lang, parts[0], parts[1]
    else:
        print(
            "error: --module must be playbooks/<name>, domains/<name>, "
            "or the same path under docs/<lang>/",
            file=sys.stderr,
        )
        return None

    if group not in ("playbooks", "domains"):
        print(
            f"error: unknown group {group!r} (expected playbooks or domains)",
            file=sys.stderr,
        )
        return None

    return PurePosixPath("docs", module_lang, group, name), group, name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module",
        required=True,
        help="module path, e.g. domains/performance or docs/ja/domains/performance",
    )
    parser.add_argument("--slug", required=True, help="kebab-case file slug (no .md)")
    parser.add_argument(
        "--lang", default="ja", help="frontmatter lang value (default: ja)"
    )
    args = parser.parse_args()

    if not SLUG.match(args.slug):
        print(f"error: slug must be kebab-case, got {args.slug!r}", file=sys.stderr)
        return 1

    resolved = resolve_module(args.module, args.lang)
    if resolved is None:
        return 1
    rel_module, group, name = resolved
    module = ROOT / rel_module
    if not module.is_dir():
        print(f"error: module not found: {rel_module}", file=sys.stderr)
        return 1
    if group == "playbooks":
        lifecycle = LIFECYCLE_BY_DIR.get(name)
        if lifecycle is None:
            print(f"error: no lifecycle tag maps to playbooks/{name}", file=sys.stderr)
            return 1
        domains = "TODO"
    else:
        if name not in VALID_DOMAINS:
            print(f"error: unknown domain {name!r}", file=sys.stderr)
            return 1
        lifecycle = "TODO"
        domains = name

    target = module / "notes" / f"{args.slug}.md"
    if target.exists():
        print(f"error: already exists: {target.relative_to(ROOT)}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        TEMPLATE.format(lifecycle=lifecycle, domains=domains, lang=args.lang),
        encoding="utf-8",
    )

    print(f"created {target.relative_to(ROOT)}")
    print("next steps:")
    print("  1. replace every TODO, including the lifecycle/domains tag left as TODO")
    print(
        "  2. keep evidence: hypothesis until you have actually verified the behaviour"
    )
    print(f"  3. link it from {rel_module}/README.md")
    today = dt.datetime.now(dt.UTC).date().isoformat()
    print(f"  4. run: make lint   (today is {today} UTC)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
