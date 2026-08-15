# Architecture diagram standards

> Extracted from `AGENTS.md` so it is not loaded on every turn. Read this when creating, editing, regenerating, or exporting a diagram.
>
> `AGENTS.md` remains authoritative on any disagreement.

Follow the same standard as sibling repositories:

- Official AWS Architecture Icons, current quarterly Asset Package only. Do **not** use draw.io's bundled `mxgraph.aws4` (2019 generation).
- Service icons 80×80 (`Arch_*_64.svg` native), resource icons 48×48 (`Res_*_48.svg`). No rescaling, no mixing.
- Labels use official service names with the `Amazon`/`AWS` prefix. No abbreviations (`ALB` → `Elastic Load Balancing`). Non-AWS elements (`NFS クライアント`, `Windows ファイルサーバー`) need no prefix.
- Arrows: single-color preset open arrow only (`endArrow=open;endFill=0;strokeColor=#232F3E`). No color-coding or dashed-line semantics.
- Sources live in `docs/_assets/diagrams/`, exports in `docs/_assets/images/` and `docs/_assets/images/png/`. Diagrams are language-neutral; the underscore marks the directory as not-content, which is also why the validators skip it.
- Ship **both themes**: light is the default and what docs display; dark is generated from light with `Res_*_48_Dark` icon substitution and linked alongside.
- Never commit the icon asset package itself — only diagrams with icons already embedded.
- `ET.parse()` passing is not verification. **Render the PNG and look at it**, per language.
- `@2x` exports exceed the 2000px read limit; downscale to a preview before reading.
