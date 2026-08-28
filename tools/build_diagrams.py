#!/usr/bin/env python3
"""Generate the architecture diagrams from a spec, one file per language and theme.

Provenance: the machinery here — direct `.drawio` XML generation, icons embedded as
`data:image/svg+xml,<base64>` data URIs, `--check` against the committed files, and
`stabilize_svg()` — is copied from `tools/build_diagrams.py` in the sibling repository
`S3-Burst-on-ONTAP-Files`. Divergences, all deliberate:

* one diagram rather than three, so `DIAGRAMS` is short and the spec functions are inline;
* a **theme** axis was added. This repository's diagram standard ships light and dark together,
  and dark substitutes the `Res_*_48_Dark` variant of every general resource icon. The sibling
  ships light only, so its renderer has no theme parameter;
* no `LOCAL_ICONS`: this diagram uses AWS assets only, so the third-party badge handling and its
  per-vendor rules are not carried over.

Why the XML is written directly rather than through the draw.io MCP tools or the built-in
`mxgraph.aws4.*` shapes — each was tried in a sibling project and the findings recorded there:

* `insert_image_vertex` embeds icons in a form the draw.io CLI drops on export, so the picture is
  right on screen and empty in the exported file;
* `mxgraph.aws4.*` carries the 2019 icon generation, not the current quarterly asset package;
* the data URI must be `data:image/svg+xml,<base64>`. Written as the MIME specification would
  suggest, `data:image/svg+xml;base64,`, draw.io renders nothing and the export still succeeds.

The `mxgraph.aws4.group` *container* shapes are a different thing from the aws4 icon set and are
used: they draw a boundary, not a service mark.

Icons are read from the AWS Architecture Icons package rather than copied in. The package is a
quarterly release from https://aws.amazon.com/architecture/icons/ and is never committed, so this
is an authoring step and not a gate — the generated `.drawio` and the exported images are the
committed artefacts, and `make all` does not run it.

Run:
  python3 tools/build_diagrams.py --check           # committed files still match the spec
  python3 tools/build_diagrams.py --write           # regenerate every .drawio
  python3 tools/build_diagrams.py --write --export  # and run the draw.io CLI for SVG + PNG
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parent.parent
DIAGRAM_DIR = ROOT / "docs" / "_assets" / "diagrams"
IMAGE_DIR = ROOT / "docs" / "_assets" / "images"
PNG_DIR = IMAGE_DIR / "png"

LANGS = ("ja", "en")
THEMES = ("light", "dark")

# Fixed so regeneration is byte-stable. A changing timestamp puts every diagram in every diff and
# hides the edit that mattered.
MODIFIED = "2026-08-28T00:00:00.000Z"
DRAWIO_CLI = Path("/Applications/draw.io.app/Contents/MacOS/draw.io")

# --- icons ---------------------------------------------------------------------------------------

# Relative to the package root, with `{d}` standing for the release date and `{v}` for the
# light/dark variant of the general resource icons. The date appears in every top-level directory
# inside the package and changes quarterly, so it is read off the directory name rather than
# written here — one home for one fact, and a wrong guess shows up as a missing icon.
#
# The `_Light` suffix on the general resource icons is easy to miss: `Res_Disk_48.svg` does not
# exist, `Res_Disk_48_Light.svg` does.
ICONS = {
    "fsx_ontap": (
        "Architecture-Service-Icons_{d}/Arch_Storage/64/"
        "Arch_Amazon-FSx-for-NetApp-ONTAP_64.svg"
    ),
    "aws_backup": (
        "Architecture-Service-Icons_{d}/Arch_Storage/64/Arch_AWS-Backup_64.svg"
    ),
    "disk": "Resource-Icons_{d}/Res_General-Icons/Res_48_{v}/Res_Disk_48_{v}.svg",
}

# Native sizes. Rescaling is what the AWS icon guidelines forbid, so the size follows the asset:
# 80 for an architecture (service) icon, 48 for a resource icon.
ICON_SIZE = {
    "fsx_ontap": 80,
    "aws_backup": 80,
    "disk": 48,
}

# --- styles --------------------------------------------------------------------------------------

GROUP_POINTS = (
    "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],"
    "[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]]"
)


@dataclass(frozen=True)
class Palette:
    """Everything the theme changes. Icon variant included, so one lookup covers the whole switch."""

    variant: str
    background: str
    ink: str
    cloud_stroke: str
    region_stroke: str
    box_stroke: str
    frame_stroke: str
    note_fill: str
    note_ink: str


PALETTES = {
    "light": Palette(
        variant="Light",
        background="#FFFFFF",
        ink="#232F3E",
        cloud_stroke="#232F3E",
        region_stroke="#00A4A6",
        box_stroke="#232F3E",
        frame_stroke="#666666",
        note_fill="#F5F5F5",
        note_ink="#333333",
    ),
    "dark": Palette(
        variant="Dark",
        background="#232F3E",
        ink="#FFFFFF",
        cloud_stroke="#FFFFFF",
        region_stroke="#4DD2D4",
        box_stroke="#FFFFFF",
        frame_stroke="#B0B8C1",
        note_fill="#2E3B4E",
        note_ink="#D5DBDB",
    ),
}


def group_style(gr_icon: str, stroke: str, ink: str, dashed: bool) -> str:
    return (
        f"{GROUP_POINTS};outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;"
        f"fontStyle=1;fontColor={ink};shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.{gr_icon};"
        f"strokeColor={stroke};fillColor=none;verticalAlign=top;align=left;spacingLeft=30;"
        f"spacingTop=4;dashed={1 if dashed else 0};"
    )


def icon_style(data_uri: str, ink: str) -> str:
    return (
        "sketch=0;html=1;shape=image;verticalLabelPosition=bottom;verticalAlign=top;"
        "labelPosition=center;align=center;imageAspect=1;aspect=fixed;fontSize=11;"
        f"fontColor={ink};image={data_uri};"
    )


def box_style(stroke: str, ink: str) -> str:
    """A named resource with no official icon.

    Backups and recovery points have no icon in the AWS asset package that is not an AWS Backup
    mark, and this figure's main path is the FSx for ONTAP native copy. Borrowing the AWS Backup
    resource icon for it would attribute the native path to AWS Backup, which is the confusion the
    article exists to remove. A named box states the resource without claiming a service.
    """
    return (
        f"rounded=1;whiteSpace=wrap;html=1;strokeColor={stroke};fillColor=none;"
        f"fontColor={ink};fontSize=11;verticalAlign=middle;align=center;"
    )


def frame_style(stroke: str, ink: str) -> str:
    """A dashed grouping, used where an edge must arrive at a set of resources rather than at one.

    The restore creates a file system, an SVM and a volume. An edge landing on the file system icon
    alone would say the backup restores into an existing file system, which is the misreading the
    article corrects.
    """
    return (
        f"rounded=1;whiteSpace=wrap;html=1;dashed=1;dashPattern=8 4;strokeColor={stroke};"
        f"fillColor=none;fontColor={ink};fontSize=11;verticalAlign=top;align=center;spacingTop=6;"
    )


def edge_style(ink: str, background: str) -> str:
    """An edge and its label.

    `labelBackgroundColor` is set explicitly because draw.io's default is an opaque white plate
    behind every edge label. On the dark canvas that plate stays white while the text turns white
    with it, so each label renders as a blank rectangle — visible only in the exported PNG, which is
    why the standard says to look at the picture rather than trust a parse.
    """
    return (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=open;endFill=0;"
        f"strokeColor={ink};strokeWidth=1;fontSize=11;fontColor={ink};"
        f"labelBackgroundColor={background};"
    )


def note_style(fill: str, stroke: str, ink: str) -> str:
    return (
        f"rounded=1;whiteSpace=wrap;html=1;dashed=1;dashPattern=8 4;strokeColor={stroke};"
        f"fillColor={fill};fontColor={ink};fontSize=11;align=left;verticalAlign=top;"
        "spacingLeft=10;spacingTop=6;"
    )


# --- labels --------------------------------------------------------------------------------------

# Product names and API action names stay English in both languages: they are identifiers, and the
# naming rule requires the official service name with its Amazon / AWS prefix. Prose — panel
# titles, resource descriptions, the footnote — is localized.
LABELS: dict[str, dict[str, str]] = {
    "aws_cloud": {"ja": "AWS Cloud", "en": "AWS Cloud"},
    "region_source": {
        "ja": "ap-northeast-1（東京）",
        "en": "ap-northeast-1 (Tokyo)",
    },
    "region_dest": {
        "ja": "ap-northeast-3（大阪）",
        "en": "ap-northeast-3 (Osaka)",
    },
    "fsx_source": {
        "ja": "Amazon FSx for NetApp ONTAP",
        "en": "Amazon FSx for NetApp ONTAP",
    },
    "fsx_dest": {
        "ja": "Amazon FSx for NetApp ONTAP",
        "en": "Amazon FSx for NetApp ONTAP",
    },
    "aws_backup": {"ja": "AWS Backup", "en": "AWS Backup"},
    "volume_rw": {"ja": "RW ボリューム", "en": "RW volume"},
    "volume_restored": {"ja": "新規ボリューム", "en": "New volume"},
    "backup": {"ja": "ボリュームバックアップ", "en": "Volume backup"},
    "backup_copy": {
        "ja": "バックアップのコピー",
        "en": "Backup copy",
    },
    "vault": {
        "ja": "バックアップボールト",
        "en": "Backup vault",
    },
    # The point of the whole figure: this area holds nothing until a recovery starts.
    "recovery_frame": {
        "ja": "復旧するときに作る（平常時は存在しない）",
        "en": "Created when recovering (absent day to day)",
    },
    "create_backup": {"ja": "CreateBackup", "en": "CreateBackup"},
    "copy_backup": {"ja": "CopyBackup", "en": "CopyBackup"},
    "backup_plan": {
        "ja": "バックアッププラン",
        "en": "Backup plan",
    },
    "copy_rule": {"ja": "コピールール", "en": "Copy rule"},
    "restore": {
        "ja": "CreateVolumeFromBackup",
        "en": "CreateVolumeFromBackup",
    },
    "note": {
        "ja": (
            "<b>補足</b><br>"
            "※1 <b>復元先はバックアップが保存されているリージョンに限られる</b><br>"
            "大阪で復元するには大阪にファイルシステムと SVM が必要で、その作成時間が RTO に乗る"
            "（実測 20 分、ap-northeast-3、SINGLE_AZ_1、128 MBps）<br>"
            "※2 <b>ネイティブの CopyBackup は同一アカウント内のみ・手動</b><br>"
            "定期実行と別アカウントは AWS Backup 経由（別アカウントは AWS Organizations が前提）<br>"
            "※3 <b>この図は SnapMirror の代わりではない</b><br>"
            "分単位の RPO と切り戻しが要件なら宛先にファイルシステムを常時持つ構成になる"
        ),
        "en": (
            "<b>Notes</b><br>"
            "*1 <b>A backup restores only into the Region it is stored in</b><br>"
            "Restoring in Osaka needs a file system and an SVM there, and creating them lands on "
            "the RTO (20 minutes measured; ap-northeast-3, SINGLE_AZ_1, 128 MBps)<br>"
            "*2 <b>The native CopyBackup is manual and same-account only</b><br>"
            "Scheduling and cross-account copies go through AWS Backup, which requires AWS "
            "Organizations for the cross-account case<br>"
            "*3 <b>This is not a replacement for SnapMirror</b><br>"
            "A minutes-level RPO and a failback procedure still mean holding a file system at the "
            "destination continuously"
        ),
    },
}

CJK = re.compile(r"[\u3000-\u30ff\u4e00-\u9fff]")


def label(key: str, lang: str) -> str:
    """Look up a label, refusing to emit Japanese into an English diagram.

    A missing English string is otherwise invisible: the file exports, and the Japanese text simply
    sits in the English figure.
    """
    if key not in LABELS:
        raise SystemExit(f"build_diagrams: no label {key!r}")
    text = LABELS[key][lang]
    if lang != "ja" and CJK.search(text):
        raise SystemExit(
            f"build_diagrams: label {key!r} for {lang!r} contains Japanese"
        )
    return text


# --- spec ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    cid: str
    icon: str
    label: str
    x: int
    y: int


@dataclass(frozen=True)
class Group:
    cid: str
    label: str
    x: int
    y: int
    width: int
    height: int
    gr_icon: str = "group_aws_cloud"
    kind: str = "cloud"
    dashed: bool = False


@dataclass(frozen=True)
class Box:
    cid: str
    label: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Frame:
    cid: str
    label: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Edge:
    cid: str
    source: str
    target: str
    label: str = ""
    exit_at: tuple[float, float] | None = None
    entry_at: tuple[float, float] | None = None

    def style(self, ink: str, background: str) -> str:
        style = edge_style(ink, background)
        if self.exit_at:
            style += (
                f"exitX={self.exit_at[0]};exitY={self.exit_at[1]};exitDx=0;exitDy=0;"
            )
        if self.entry_at:
            style += f"entryX={self.entry_at[0]};entryY={self.entry_at[1]};entryDx=0;entryDy=0;"
        return style


@dataclass(frozen=True)
class Note:
    cid: str
    label: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Diagram:
    name: str
    diagram_id: str
    width: int
    height: int
    groups: tuple[Group, ...] = ()
    frames: tuple[Frame, ...] = ()
    boxes: tuple[Box, ...] = ()
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    notes: tuple[Note, ...] = ()

    def filename(self, lang: str, theme: str) -> str:
        parts = [self.name]
        if lang != "ja":
            parts.append(lang)
        if theme != "light":
            parts.append(theme)
        return "-".join(parts) + ".drawio"


def _backup_copy() -> Diagram:
    """Where a backup can live, and what the destination Region holds while nothing is wrong.

    Two paths are drawn because the article's correction is that they are not the same one. The FSx
    for ONTAP native `CopyBackup` reaches another Region inside one account with no scheduler; AWS
    Backup reaches another Region and another account on a plan. Drawing only the native path is
    what left readers thinking cross-account copies came with it.
    """
    return Diagram(
        name="backup-copy-cross-region",
        diagram_id="backup-copy-cross-region",
        width=1220,
        height=720,
        groups=(
            Group("aws_cloud", "aws_cloud", 40, 40, 1140, 490),
            Group(
                "region_src",
                "region_source",
                75,
                85,
                560,
                400,
                gr_icon="group_region",
                kind="region",
                dashed=True,
            ),
            Group(
                "region_dst",
                "region_dest",
                700,
                85,
                450,
                400,
                gr_icon="group_region",
                kind="region",
                dashed=True,
            ),
        ),
        frames=(Frame("recovery", "recovery_frame", 725, 210, 410, 170),),
        boxes=(
            Box("backup", "backup", 380, 160, 210, 50),
            Box("copy", "backup_copy", 830, 130, 200, 50),
            Box("vault", "vault", 730, 410, 200, 50),
        ),
        nodes=(
            Node("fsx_src", "fsx_ontap", "fsx_source", 120, 130),
            Node("vol_src", "disk", "volume_rw", 250, 146),
            Node("backup_svc", "aws_backup", "aws_backup", 120, 370),
            Node("fsx_dst", "fsx_ontap", "fsx_dest", 770, 250),
            Node("vol_dst", "disk", "volume_restored", 1000, 266),
        ),
        edges=(
            Edge("e1", "fsx_src", "vol_src"),
            Edge("e2", "vol_src", "backup", "create_backup"),
            Edge("e3", "backup", "copy", "copy_backup"),
            Edge("e4", "fsx_src", "backup_svc", "backup_plan"),
            Edge("e5", "backup_svc", "vault", "copy_rule"),
            Edge(
                "e6",
                "copy",
                "recovery",
                "restore",
                exit_at=(0.5, 1.0),
                entry_at=(0.5, 0.0),
            ),
            Edge("e7", "fsx_dst", "vol_dst"),
        ),
        notes=(Note("note", "note", 40, 560, 1140, 140),),
    )


DIAGRAMS = (_backup_copy(),)


# --- rendering -----------------------------------------------------------------------------------


def icon_package(explicit: str | None) -> Path:
    """Locate the AWS Architecture Icons package."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_dir():
            raise SystemExit(f"build_diagrams: --icons {path} is not a directory")
        return path
    env = os.environ.get("AWS_ICON_PACKAGE")
    if env:
        return icon_package(env)
    for candidate in sorted(Path.home().glob("Downloads/Icon-package_*"), reverse=True):
        if candidate.is_dir():
            return candidate
    raise SystemExit(
        "build_diagrams: the AWS Architecture Icons package was not found.\n"
        "  Download the current quarterly release from "
        "https://aws.amazon.com/architecture/icons/ and either leave it in ~/Downloads or pass\n"
        "  --icons <path> / set AWS_ICON_PACKAGE. The package is never committed here, which is\n"
        "  why the generated .drawio files are."
    )


def package_date(package: Path) -> str:
    """The release date in the package directory name, e.g. Icon-package_07312026.<hash>."""
    match = re.search(r"Icon-package_(\d{8})", package.name)
    if not match:
        raise SystemExit(
            f"build_diagrams: cannot read a release date from {package.name!r}.\n"
            "  Expected a directory named like Icon-package_07312026.<hash> from "
            "https://aws.amazon.com/architecture/icons/"
        )
    return match.group(1)


def data_uris(package: Path) -> dict[tuple[str, str], str]:
    """Read every icon, per theme, and build its draw.io data URI.

    Keyed by (icon, theme) because the general resource icons ship a Light and a Dark file and the
    dark diagram has to carry the Dark bytes. Service icons have one file and are read twice; that
    costs nothing and keeps the lookup uniform.

    The comma-only URI form is required. `data:image/svg+xml;base64,` exports a broken-image
    placeholder rather than failing, so the export "succeeds" and only looking at the picture shows
    it.
    """
    uris: dict[tuple[str, str], str] = {}
    date = package_date(package)
    for theme in THEMES:
        variant = PALETTES[theme].variant
        for key, relative in ICONS.items():
            resolved = relative.format(d=date, v=variant)
            path = package / resolved
            if not path.is_file():
                raise SystemExit(f"build_diagrams: {resolved} missing from {package}")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            uris[(key, theme)] = f"data:image/svg+xml,{encoded}"
    return uris


def render(
    diagram: Diagram, lang: str, theme: str, uris: dict[tuple[str, str], str]
) -> str:
    p = PALETTES[theme]
    suffix = "".join(
        part
        for part in (
            f"-{lang}" if lang != "ja" else "",
            f"-{theme}" if theme != "light" else "",
        )
    )
    name = f"{diagram.name}{suffix}"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<mxfile host="app.diagrams.net" modified="{MODIFIED}" '
            'agent="build_diagrams.py" version="24.0.0" type="device">'
        ),
        f'  <diagram id="{diagram.diagram_id}{suffix}" name="{name}">',
        (
            '    <mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1" '
            'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            f'pageWidth="{diagram.width}" pageHeight="{diagram.height}" '
            f'background="{p.background}" math="0" shadow="0">'
        ),
        "      <root>",
        '        <mxCell id="0" />',
        '        <mxCell id="1" parent="0" />',
    ]

    def vertex(
        cid: str, value: str, style: str, x: int, y: int, w: int, h: int
    ) -> None:
        lines.append(
            f"        <mxCell id={quoteattr(cid)} value={quoteattr(value)} "
            f'style={quoteattr(style)} vertex="1" parent="1">'
        )
        lines.append(
            f'          <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />'
        )
        lines.append("        </mxCell>")

    for group in diagram.groups:
        stroke = p.cloud_stroke if group.kind == "cloud" else p.region_stroke
        vertex(
            group.cid,
            label(group.label, lang),
            group_style(group.gr_icon, stroke, p.ink, group.dashed),
            group.x,
            group.y,
            group.width,
            group.height,
        )
    # Frames and boxes before nodes, so an icon draws on top of the container it sits in.
    for frame in diagram.frames:
        vertex(
            frame.cid,
            label(frame.label, lang),
            frame_style(p.frame_stroke, p.ink),
            frame.x,
            frame.y,
            frame.width,
            frame.height,
        )
    for box in diagram.boxes:
        vertex(
            box.cid,
            label(box.label, lang),
            box_style(p.box_stroke, p.ink),
            box.x,
            box.y,
            box.width,
            box.height,
        )
    for node in diagram.nodes:
        size = ICON_SIZE[node.icon]
        vertex(
            node.cid,
            label(node.label, lang),
            icon_style(uris[(node.icon, theme)], p.ink),
            node.x,
            node.y,
            size,
            size,
        )
    for edge in diagram.edges:
        value = label(edge.label, lang) if edge.label else ""
        lines.append(
            f"        <mxCell id={quoteattr(edge.cid)} value={quoteattr(value)} "
            f'style={quoteattr(edge.style(p.ink, p.background))} edge="1" '
            f"source={quoteattr(edge.source)} "
            f'target={quoteattr(edge.target)} parent="1">'
        )
        lines.append('          <mxGeometry relative="1" as="geometry" />')
        lines.append("        </mxCell>")
    for note in diagram.notes:
        vertex(
            note.cid,
            label(note.label, lang),
            note_style(p.note_fill, p.frame_stroke, p.note_ink),
            note.x,
            note.y,
            note.width,
            note.height,
        )

    lines += ["      </root>", "    </mxGraphModel>", "  </diagram>", "</mxfile>", ""]
    return "\n".join(lines)


# --- checking ------------------------------------------------------------------------------------


def cells(xml: str) -> list[tuple[str, str, str, str]]:
    """Reduce a document to what a reader sees, so formatting is not compared."""
    out = []
    for cell in ET.fromstring(xml).find(".//root").iter("mxCell"):
        geometry = cell.find("mxGeometry")
        geo = (
            " ".join(f"{k}={v}" for k, v in sorted(geometry.attrib.items()))
            if geometry is not None
            else ""
        )
        style = re.sub(
            r"image=data:image/svg\+xml,([A-Za-z0-9+/=]{16})[A-Za-z0-9+/=]*",
            r"image=<\1...>",
            cell.get("style") or "",
        )
        out.append((cell.get("id") or "", cell.get("value") or "", style, geo))
    return out


def check(uris: dict[tuple[str, str], str]) -> int:
    problems = 0
    total = 0
    for diagram in DIAGRAMS:
        for lang in LANGS:
            for theme in THEMES:
                total += 1
                path = DIAGRAM_DIR / diagram.filename(lang, theme)
                if not path.is_file():
                    print(f"  missing   {path.relative_to(ROOT)}", file=sys.stderr)
                    problems += 1
                    continue
                want = cells(render(diagram, lang, theme, uris))
                got = cells(path.read_text(encoding="utf-8"))
                if want == got:
                    continue
                problems += 1
                print(f"  differs   {path.relative_to(ROOT)}", file=sys.stderr)
                for a, b in zip(want, got):
                    if a != b:
                        print(f"      spec: {a}", file=sys.stderr)
                        print(f"      file: {b}", file=sys.stderr)
                if len(want) != len(got):
                    print(
                        f"      cell count spec={len(want)} file={len(got)}",
                        file=sys.stderr,
                    )
    if problems:
        print(
            "\n  A generated diagram was edited by hand, or the spec moved without a regenerate.\n"
            "  Run: python3 tools/build_diagrams.py --write --export",
            file=sys.stderr,
        )
        return 1
    print(f"diagrams: {total} file(s) match the spec")
    return 0


# --- exporting -----------------------------------------------------------------------------------


# draw.io stamps a fresh random element id into every SVG export and uses it twice: as the root id
# and as the CSS selector for its adaptive-background rule. Left alone, re-exporting an unchanged
# diagram still rewrites every SVG, and the files that did not change bury the one that did — the
# same failure the fixed MODIFIED timestamp prevents in the .drawio files. The id only has to be
# unique within the document, so deriving it from the file name is enough.
SVG_RANDOM_ID = re.compile(r"ge-svg-[A-Za-z0-9_-]+")


def stabilize_svg(target: Path) -> None:
    text = target.read_text(encoding="utf-8")
    stabilized = SVG_RANDOM_ID.sub(f"ge-svg-{target.stem}", text)
    if stabilized != text:
        target.write_text(stabilized, encoding="utf-8")


def export(diagram: Diagram, lang: str, theme: str) -> None:
    source = DIAGRAM_DIR / diagram.filename(lang, theme)
    stem = source.stem
    if not DRAWIO_CLI.is_file():
        print(
            f"  draw.io CLI not found at {DRAWIO_CLI}; skipping export", file=sys.stderr
        )
        return
    runs = (
        # SVG for the repository: crawlers and screen readers can reach the text.
        (IMAGE_DIR / f"{stem}.svg", ["--format", "svg", "--embed-svg-images"]),
        # PNG at 2x for the blog posts, which do not render SVG reliably.
        (PNG_DIR / f"{stem}@2x.png", ["--format", "png", "--scale", "2"]),
    )
    for target, extra in runs:
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                str(DRAWIO_CLI),
                "--export",
                "--border",
                "12",
                *extra,
                "--output",
                str(target),
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        if target.suffix == ".svg":
            stabilize_svg(target)
        print(f"  exported  {target.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="regenerate the .drawio files"
    )
    parser.add_argument("--export", action="store_true", help="also export SVG and PNG")
    parser.add_argument(
        "--check", action="store_true", help="compare committed files to the spec"
    )
    parser.add_argument("--icons", help="path to the AWS Architecture Icons package")
    args = parser.parse_args()

    if not (args.write or args.check):
        parser.error("give --write or --check")

    uris = data_uris(icon_package(args.icons))

    if args.check:
        return check(uris)

    DIAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for diagram in DIAGRAMS:
        for lang in LANGS:
            for theme in THEMES:
                path = DIAGRAM_DIR / diagram.filename(lang, theme)
                path.write_text(render(diagram, lang, theme, uris), encoding="utf-8")
                print(f"  wrote     {path.relative_to(ROOT)}")
                if args.export:
                    export(diagram, lang, theme)
    return 0


if __name__ == "__main__":
    sys.exit(main())
