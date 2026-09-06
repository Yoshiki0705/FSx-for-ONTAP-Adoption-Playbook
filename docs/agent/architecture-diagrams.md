# Architecture diagram standards

> Extracted from `AGENTS.md` so it is not loaded on every turn. Read this when creating, editing, regenerating, or exporting a diagram.
>
> `AGENTS.md` remains authoritative on any disagreement.

Follow the same standard as sibling repositories:

- Official AWS Architecture Icons, current quarterly Asset Package only. Do **not** use draw.io's bundled `mxgraph.aws4` (2019 generation).
- Service icons 80×80 (`Arch_*_64.svg` native), resource icons 48×48 (`Res_*_48.svg`). No rescaling, no mixing.
- Labels use official service names with the `Amazon`/`AWS` prefix. No abbreviations (`ALB` → `Elastic Load Balancing`). Non-AWS elements (`NFS クライアント`, `Windows ファイルサーバー`) need no prefix.
- Arrows: single-color preset open arrow only (`endArrow=open;endFill=0;strokeColor=#232F3E`). No color-coding or dashed-line semantics.
- **Diagrams are generated from a spec, never hand-edited.** `tools/build_diagrams.py` holds the geometry and the `LABELS` table; `make diagrams` regenerates every language and theme and exports SVG + PNG, and `make diagrams-check` fails when a committed file no longer matches the spec. Both need the icon package, so neither is part of `make all`. Editing the XML directly is what `--check` exists to catch.
- Sources live in `docs/_assets/diagrams/`, exports in `docs/_assets/images/` and `docs/_assets/images/png/`. Diagrams are language-neutral; the underscore marks the directory as not-content, which is also why the validators skip it.
- Ship **both themes**: light is the default and what docs display; dark is generated from light with `Res_*_48_Dark` icon substitution and linked alongside.
- Never commit the icon asset package itself — only diagrams with icons already embedded.
- `ET.parse()` passing is not verification. **Render the PNG and look at it**, per language.
- `@2x` exports exceed the 2000px read limit; downscale to a preview before reading.

## Label size — the floor is what a reader sees, not the attribute

`make diagram-fonts` enforces this, and `tools/check_diagram_fonts.py` is where the numbers live.

A label is displayed at the size it has **after** the image is scaled down to fit the column it
sits in, so a wider canvas makes every label smaller. Every diagram in this repository was
authored at `fontSize=11` on a canvas near 1200px, which reaches a reader at about 8px — below
the point where the measured figures in a notes box can be read on a laptop. Nothing reported it,
because `fontSize=11` looks unremarkable in a style string and the exported PNG is inspected at
full size.

Two floors, both required:

| Floor | Value | What it stops |
|---|---|---|
| Effective size — `fontSize × min(1, 880 / rendered width)` | **≥ 14px** | A label that is legible in the editor and not on the page |
| Source `fontSize` | **≥ 16px** | Satisfying the first floor by shrinking the canvas rather than growing the text |

880px is the reader's column on GitHub, dev.to and hatenablog. The rendered width comes from the
exported SVG when one exists, not from `pageWidth`: draw.io crops to content and adds `--border`,
so the two differ.

| Canvas width | Required `fontSize` |
|---|---|
| ≤ 880px | 16 |
| 1200px | 20 |
| 1600px | 26 |
| 2000px | 32 |

**Widening the canvas raises the floor.** The cheapest diagram to keep compliant is one whose
canvas is close to 880px, where 16 suffices.

When a compliant label no longer fits, work down this list. Shrinking the font is not on it.

1. Fold the label to two lines (the two-line maximum above still applies; never break mid-word).
2. Move the notes box out of the figure and into body prose as a table. Figure annotations are the
   densest text in any diagram here and the least suited to being an image — prose is searchable,
   translatable and reachable by a screen reader.
3. Narrow the canvas toward 880px and stack elements vertically. Height does not compete for width,
   and top-to-bottom flow is the reading order a diagram should already have.
4. Split the figure.
5. Abstract — collapse individual resources into the role they play.

Standard shared with sibling repositories:
`~/.kiro/steering/global-document-readability.md`, derived from
[こんなアーキテクチャ図は嫌だ (JAWS SONIC 2026)](https://speakerdeck.com/naospon/15-of-anti-pattern-in-aws-architecture-diagrams).
