#!/usr/bin/env python3
"""Build the Japanese GCP-to-FSx for ONTAP procedure deck.

The deck is a handoff aid. Provider operations whose interface is still open are shown as
stop points and are never presented as runnable commands.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".private/gcp-fsx-ontap-peering-procedure-ja.pptx"
IMAGE_DIR = ROOT / "docs/_assets/images/png"
CONSOLE_VOLUMES = ROOT / "docs/_assets/images/aws-console-gcnv-peer-svm-volumes.png"
CONSOLE_VPC_CREATE = ROOT / "docs/_assets/images/aws-console-vpc-create.png"
CONSOLE_SUBNETS = ROOT / "docs/_assets/images/aws-console-subnets.png"
CONSOLE_ROUTE_TABLES = ROOT / "docs/_assets/images/aws-console-route-tables.png"
CONSOLE_VPN = ROOT / "docs/_assets/images/aws-console-vpn-connections.png"
CONSOLE_SECURITY = ROOT / "docs/_assets/images/aws-console-security-groups.png"

NAVY = RGBColor(35, 47, 62)
BLUE = RGBColor(66, 133, 244)
ORANGE = RGBColor(255, 153, 0)
RED = RGBColor(198, 40, 40)
TEXT = RGBColor(32, 33, 36)
MUTED = RGBColor(90, 100, 110)
PALE_BLUE = RGBColor(239, 246, 255)
PALE_ORANGE = RGBColor(255, 247, 235)
PALE_RED = RGBColor(255, 244, 244)
PALE_YELLOW = RGBColor(255, 251, 234)
WHITE = RGBColor(255, 255, 255)
DARK_PANEL = RGBColor(47, 61, 78)
JP_FONT = "Yu Gothic"
CODE_FONT = "Menlo"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]


def add_text(
    slide,
    text,
    x,
    y,
    w,
    h,
    size=18,
    color=TEXT,
    bold=False,
    align=PP_ALIGN.LEFT,
    font=JP_FONT,
    valign=MSO_ANCHOR.TOP,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def add_title(slide, title, subtitle=None):
    add_text(slide, title, 0.55, 0.22, 12.2, 0.58, size=30, color=NAVY, bold=True)
    if subtitle:
        add_text(slide, subtitle, 0.58, 0.84, 12.0, 0.32, size=16, color=MUTED)
    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.55), Inches(1.22), Inches(12.2), Inches(0.025)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = ORANGE
    line.line.fill.background()


def add_footer(slide, number=None):
    number = len(prs.slides)
    add_text(
        slide,
        "GCP × Amazon FSx for NetApp ONTAP | 検証環境向け手順",
        0.55,
        7.12,
        10.8,
        0.2,
        9,
        MUTED,
    )
    add_text(slide, str(number), 12.1, 7.08, 0.6, 0.22, 10, MUTED, align=PP_ALIGN.RIGHT)


def add_panel(slide, title, body, x, y, w, h, fill=WHITE, accent=BLUE, body_size=18):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = accent
    shape.line.width = Pt(1.2)
    add_text(slide, title, x + 0.18, y + 0.12, w - 0.36, 0.34, 20, accent, True)
    add_text(slide, body, x + 0.18, y + 0.55, w - 0.36, h - 0.68, body_size, TEXT)
    return shape


def add_bullets(slide, items, x, y, w, h, size=18, color=TEXT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.04)
    tf.margin_top = Inches(0.02)
    for index, item in enumerate(items):
        p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        p.text = item
        p.level = 0
        p.space_after = Pt(8)
        p.font.name = JP_FONT
        p.font.size = Pt(size)
        p.font.color.rgb = color
    return box


def add_code(slide, text, x, y, w, h):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(245, 247, 250)
    shape.line.color.rgb = RGBColor(180, 188, 198)
    add_text(
        slide, text, x + 0.12, y + 0.1, w - 0.24, h - 0.2, 13.5, TEXT, font=CODE_FONT
    )
    return shape


def add_image(slide, filename, x, y, w, h):
    slide.shapes.add_picture(
        str(IMAGE_DIR / filename),
        Inches(x),
        Inches(y),
        width=Inches(w),
        height=Inches(h),
    )


def new_slide(title, subtitle=None):
    slide = prs.slides.add_slide(blank)
    add_title(slide, title, subtitle)
    return slide


# 1. Title
slide = prs.slides.add_slide(blank)
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = NAVY
add_text(
    slide, "GCP と Amazon FSx for NetApp ONTAP", 0.7, 1.32, 11.9, 0.8, 34, WHITE, True
)
add_text(
    slide,
    "ピアリング接続とデータ検証の作業手順",
    0.72,
    2.25,
    11.6,
    0.65,
    28,
    RGBColor(255, 204, 128),
    True,
)
add_text(
    slide,
    "read-only preflight / NFS validation / direction-specific replication handoff",
    0.74,
    3.18,
    11.5,
    0.38,
    17,
    RGBColor(225, 232, 240),
)
add_panel(
    slide,
    "この資料の使い方",
    "上から順に実行し、各スライドの停止条件を run ledger に記録する。\nOpen の操作は interface と証拠が揃うまで実行しない。",
    0.75,
    4.2,
    5.7,
    1.45,
    DARK_PANEL,
    RGBColor(255, 204, 128),
    18,
)
add_panel(
    slide,
    "公開資料の境界",
    "実アカウント ID、IP、DNS、credential は placeholder に置き換える。\nクラウド変更、認証、cleanup の破壊操作はこの資料作成中に実行しない。",
    6.85,
    4.2,
    5.7,
    1.45,
    DARK_PANEL,
    RGBColor(122, 180, 255),
    18,
)
add_text(
    slide, "日本語版 | 16:9 | 17 slides", 0.75, 6.7, 4, 0.3, 14, RGBColor(220, 230, 240)
)

# 2. Scope and stop boundary
slide = new_slide(
    "1. 作業範囲と停止境界", "Set A は実行可能な確認、Set B は Open の handoff"
)
add_panel(
    slide,
    "Set A | この資料で実行する確認",
    "ネットワークの forward / return\nNFS mount の source / FSTYPE\n48 ファイルの fixture と SHA-256\nDP volume の read-only\nrun-created 資源だけの cleanup",
    0.7,
    1.55,
    5.8,
    4.85,
    PALE_BLUE,
    BLUE,
)
add_panel(
    slide,
    "Set B | 状態を確認して止める",
    "cluster peering / SVM peering\nSnapMirror FSx for ONTAP → GCNV\nReverse Resync GCNV → FSx for ONTAP\nFlexCache の両方向\n正式 interface が不明な provider 操作",
    6.85,
    1.55,
    5.8,
    4.85,
    PALE_RED,
    RED,
)
add_footer(slide, 2)

# 3. Overview
slide = new_slide("2. 全体構成", "NFS のデータ経路と、管理面の未確定操作を分けて読む")
add_image(slide, "gcp-fsx-ontap-peering-overview@2x.png", 0.75, 1.35, 11.85, 5.55)
add_footer(slide, 3)

# 4. Ledger and ownership
slide = new_slide("3. 作業前の台帳", "値の推測をせず、対象・方向・所有者を先に固定する")
add_panel(
    slide,
    "GCP 側",
    "project / region\nVPC / Cloud VPN / Cloud Router\nCompute Engine client\nGoogle Cloud NetApp Volumes SVM / volume",
    0.7,
    1.5,
    3.8,
    4.9,
    PALE_BLUE,
    BLUE,
)
add_panel(
    slide,
    "AWS 側",
    "account / region / VPC\nAWS Site-to-Site VPN / route table\nFSx for ONTAP SVM\ngcnv_snapmirror_src / gcnv_flexcache_origin",
    4.8,
    1.5,
    3.8,
    4.9,
    PALE_ORANGE,
    ORANGE,
)
add_panel(
    slide,
    "必須の記録",
    "sample_run_id\nsource / destination / direction\nowner / rollback / current state\nshared resource か run-created か",
    8.9,
    1.5,
    3.8,
    4.9,
    PALE_YELLOW,
    ORANGE,
)
add_footer(slide, 4)

# 5. Network preflight
slide = new_slide(
    "4. Phase 1 | ネットワーク事前確認",
    "変更前に GCP の learned route と AWS の return route を別々に読む",
)
add_code(
    slide,
    'gcloud compute vpn-tunnels list \\\n  --regions <gcp-region> --filter="name:<vpn-name>"\ngcloud compute routers get-status <router-name> \\\n  --region <gcp-region> --format=json',
    0.72,
    1.5,
    5.9,
    2.3,
)
add_code(
    slide,
    "aws ec2 describe-vpn-connections \\\n  --region <aws-region> --vpn-connection-ids <vpn-id> \\\n  --query 'VpnConnections[].VgwTelemetry'\naws ec2 describe-route-tables \\\n  --region <aws-region> --filters Name=association.subnet-id,Values=<subnet-id>",
    6.72,
    1.5,
    5.9,
    2.3,
)
add_panel(
    slide,
    "合格条件",
    "GCP tunnel / BGP が確立し、AWS 側に GCP client CIDR の戻り経路がある。",
    0.72,
    4.15,
    5.9,
    1.25,
    PALE_BLUE,
    BLUE,
)
add_panel(
    slide,
    "停止条件",
    "route、owner、target が不一致なら security rule や route を変更せず停止する。",
    6.72,
    4.15,
    5.9,
    1.25,
    PALE_RED,
    RED,
)
add_footer(slide, 5)

# 6. Reachability
slide = new_slide(
    "5. Phase 1 | NFS 到達性", "TCP 2049 が成功するまで mount と書き込みへ進まない"
)
add_code(
    slide,
    'NFS_ENDPOINT="<nfs-endpoint>"\ntimeout 5 bash -c "</dev/tcp/$NFS_ENDPOINT/2049"',
    0.85,
    1.65,
    5.5,
    1.45,
)
add_panel(
    slide,
    "確認する面",
    "GCP client CIDR → AWS route table → AWS Site-to-Site VPN → FSx for ONTAP subnet → security group / NACL → export policy",
    6.7,
    1.55,
    5.5,
    2.0,
    PALE_BLUE,
    BLUE,
)
add_panel(
    slide,
    "停止する状態",
    "TCP 2049 不通\nCloud Shell など VPC 外からの試験だけ\n戻り経路または export policy が未確認",
    0.85,
    3.65,
    5.5,
    2.1,
    PALE_RED,
    RED,
)
add_panel(
    slide,
    "証拠",
    "probe の時刻、client identity、endpoint、source CIDR、結果を同じ run ID に記録する。",
    6.7,
    3.85,
    5.5,
    1.7,
    PALE_YELLOW,
    ORANGE,
)
add_footer(slide, 6)

# 7. Safe mount
slide = new_slide(
    "6. Phase 2 | NFS mount の安全確認",
    "fixture を作る前に mount source と FSTYPE を検査する",
)
add_code(
    slide,
    'mountpoint -q <mount-root>\nfindmnt -T <mount-root> -o TARGET,SOURCE,FSTYPE,OPTIONS\nSOURCE=$(findmnt -n -T <mount-root> -o SOURCE)\nFSTYPE=$(findmnt -n -T <mount-root> -o FSTYPE)\ntest "$FSTYPE" = nfs || test "$FSTYPE" = nfs4',
    0.7,
    1.45,
    7.0,
    2.8,
)
add_panel(
    slide,
    "SOURCE の一致",
    "<nfs-endpoint>:<export-path> と台帳の値が一致すること。\n既存の run directory や marker があれば停止する。",
    8.0,
    1.55,
    4.6,
    2.1,
    PALE_BLUE,
    BLUE,
)
add_panel(
    slide,
    "Fail closed",
    "mountpoint 失敗\nlocal filesystem\nunexpected export\n既存 marker\nfixture 作成前に停止",
    0.7,
    4.65,
    5.8,
    1.35,
    PALE_RED,
    RED,
)
add_panel(
    slide,
    "書き込み先",
    "<mount-root>/gcp-fsx-ontap-<sample_run_id>\n新規ディレクトリだけを対象にする。",
    6.8,
    4.65,
    5.8,
    1.35,
    PALE_YELLOW,
    ORANGE,
)
add_footer(slide, 7)

# 8. Fixture
slide = new_slide(
    "7. Phase 2 | 48 ファイル fixture",
    "固定 seed と manifest を作り、件数を先に確定する",
)
add_bullets(
    slide,
    [
        "1. 新規の fixture directory を作る。",
        "2. sample-001.txt ～ sample-048.txt を固定 seed から生成する。",
        "3. manifest.sha256 を sorted relative path で保存する。",
        "4. 48 件以外、extra、missing があれば次へ進まない。",
    ],
    0.75,
    1.55,
    5.5,
    3.4,
    19,
)
add_code(
    slide,
    'RUN_ID="<sample-run-id>"\nFIXTURE_ROOT="<mount-root>/gcp-fsx-ontap-$RUN_ID"\npython3 <fixture-generator> "$FIXTURE_ROOT"\ntest "$(find "$FIXTURE_ROOT" -name \'sample-*.txt\' | wc -l)" -eq 48',
    6.7,
    1.55,
    5.8,
    2.3,
)
add_panel(
    slide,
    "公開資料との差",
    "fixture の手順は再現用。過去の 48/48 観測は retained run record が揃うまで verified に昇格しない。",
    0.75,
    5.35,
    11.75,
    0.95,
    PALE_YELLOW,
    ORANGE,
)
add_footer(slide, 8)

# 9. Hash and DP
slide = new_slide(
    "8. Phase 2 | SHA-256 と DP read-only", "hash、件数、read-only を別々の判定にする"
)
add_code(
    slide,
    "find <fixture-root> -name 'sample-*.txt' -print | sort\nsha256sum -c <(awk -F '\\t' '{print $1 \"  \" $2}' \\\n  <fixture-root>/manifest.sha256)\ntouch <dp-mount>/write-test",
    0.7,
    1.55,
    6.3,
    2.6,
)
add_panel(
    slide,
    "Hash の合格",
    "total=48\nsuccess=48\nfailed=0\nmissing=0\nextra=0",
    7.35,
    1.55,
    2.45,
    2.6,
    PALE_BLUE,
    BLUE,
)
add_panel(
    slide,
    "DP の合格",
    "findmnt で DP volume と確認\ntouch が Read-only file system\n別のエラーは合格にしない",
    10.05,
    1.55,
    2.55,
    2.6,
    PALE_ORANGE,
    ORANGE,
)
add_panel(
    slide,
    "記録",
    "source、destination、volume role、manifest、時刻、run ID を private ledger に保存する。",
    0.7,
    4.75,
    11.8,
    1.0,
    PALE_YELLOW,
    ORANGE,
)
add_footer(slide, 9)

# 10. Dedicated roles
slide = new_slide(
    "9. Phase 3 | 専用リソースの役割", "SnapMirror と FlexCache の資源を混在させない"
)
add_panel(
    slide,
    "SnapMirror source",
    "SVM: gcnv_peer_svm\nVolume: gcnv_snapmirror_src\nDirection: FSx for ONTAP → GCNV\nDestination role: DP / read-only",
    0.7,
    1.55,
    3.8,
    4.5,
    PALE_ORANGE,
    ORANGE,
)
add_panel(
    slide,
    "FlexCache origin",
    "SVM: gcnv_peer_svm\nVolume: gcnv_flexcache_origin\nOrigin / cache directionを別台帳\nCreation interface: Open",
    4.8,
    1.55,
    3.8,
    4.5,
    PALE_BLUE,
    BLUE,
)
add_panel(
    slide,
    "共通の停止",
    "provider resource identity 不一致\nowner 不明\napplications 不足\npost-state query 不明\n未検証 command の要求",
    8.9,
    1.55,
    3.8,
    4.5,
    PALE_RED,
    RED,
)
add_footer(slide, 10)

# AWS Management Console read-only evidence
slide = new_slide(
    "AWS console | read-only 確認",
    "東京リージョンの既存 FSx for ONTAP。ID、UUID、ARN、時刻はマスク済み",
)
slide.shapes.add_picture(
    str(CONSOLE_VOLUMES),
    Inches(0.65),
    Inches(1.35),
    width=Inches(7.6),
    height=Inches(5.8),
)
add_panel(
    slide,
    "AWS console / ONTAP CLI で確認できたこと",
    "SVM: gcnv_peer_svm\nSnapMirror source: DP / 100 GiB\nFlexCache origin: RW / 100 GiB\nONTAP: 9.18.1P6\nSSH: cluster management endpoint\nSVM peer: peered / snapmirror, flexcache\nSnapMirror: Snapmirrored / Idle / Healthy true",
    8.45,
    1.55,
    4.05,
    3.25,
    PALE_BLUE,
    BLUE,
    16,
)
add_panel(
    slide,
    "停止条件",
    "Cluster peer: Unavailable\ncreate / initialize / Reverse Resync / FlexCache create は未実行\n\nread-only 状態だけでは Open を解除しない",
    8.45,
    5.05,
    4.05,
    1.35,
    PALE_RED,
    RED,
    16,
)
add_footer(slide)

# Beginner runbook: AWS VPC resources
slide = new_slide(
    "実行手順 A | AWS VPC resource の作成順序",
    "既存 resource は変更せず、disposable 構成だけを承認後に作成する",
)
add_code(
    slide,
    "aws ec2 create-vpc --cidr-block <aws-vpc-cidr>\naws ec2 create-subnet --vpc-id <vpc-id> \\\n  --cidr-block <subnet-cidr> --availability-zone <az>\naws ec2 create-route-table --vpc-id <vpc-id>\naws ec2 associate-route-table \\\n  --route-table-id <route-table-id> --subnet-id <subnet-id>\naws ec2 create-vpn-gateway --type ipsec.1 \\\n  --amazon-side-asn <aws-private-asn>",
    0.7,
    1.45,
    7.1,
    3.45,
)
add_panel(
    slide,
    "作成前の固定値",
    "CIDR の重複なし\nAZ / subnet / route table\nAWS ASN / GCP BGP ASN\nowner / cost limit / cleanup owner\nshared resource ではないこと",
    8.1,
    1.55,
    4.4,
    2.5,
    PALE_BLUE,
    BLUE,
    17,
)
add_panel(
    slide,
    "STOP",
    "既存 VPC、subnet、route table、VGW は変更しない。\ncreate response だけで成功と判定しない。\npost-state を fresh read する。",
    8.1,
    4.35,
    4.4,
    1.45,
    PALE_RED,
    RED,
    16,
)
add_footer(slide)

# Beginner runbook: VPN, routes, and security
slide = new_slide(
    "実行手順 A-2 | VPN、route、security rule",
    "forward / return と必要ポートを別々に検証する",
)
add_code(
    slide,
    "aws ec2 create-customer-gateway --type ipsec.1 \\\n  --public-ip <gcp-vpn-public-ip> --bgp-asn <gcp-bgp-asn>\naws ec2 create-vpn-connection --type ipsec.1 \\\n  --customer-gateway-id <cgw-id> --vpn-gateway-id <vgw-id>\naws ec2 enable-vgw-route-propagation \\\n  --route-table-id <route-table-id> --gateway-id <vgw-id>\naws ec2 create-security-group --group-name <run-sg> \\\n  --description <description> --vpc-id <vpc-id>\naws ec2 authorize-security-group-ingress \\\n  --group-id <sg-id> --protocol tcp --port 2049 --cidr <gcp-cidr>",
    0.7,
    1.45,
    7.1,
    3.8,
)
add_panel(
    slide,
    "許可する通信",
    "TCP 22: EC2 → cluster management endpoint\nTCP 2049: GCP client → NFS endpoint\nTCP 11104 / 11105: intercluster\nICMP: intercluster reachability\nNACL の戻り ephemeral port",
    8.1,
    1.55,
    4.4,
    2.75,
    PALE_BLUE,
    BLUE,
    16,
)
add_panel(
    slide,
    "検証と rollback",
    "Cloud VPN / Cloud Router / BGP\nAWS VPN telemetry / return route\nroute table association\nsecurity group / NACL\n作成 resource だけ逆順で cleanup",
    8.1,
    4.55,
    4.4,
    1.35,
    PALE_YELLOW,
    ORANGE,
    16,
)
add_footer(slide)

# Beginner runbook: AWS console VPC screen evidence
slide = new_slide(
    "AWS console | VPC / subnet / route table",
    "作成ボタンと入力項目を確認する。作成は承認後に実施する",
)
slide.shapes.add_picture(
    str(CONSOLE_VPC_CREATE),
    Inches(0.7),
    Inches(1.35),
    width=Inches(7.3),
    height=Inches(5.75),
)
add_panel(
    slide,
    "画面の順序",
    "VPC → VPC を作成\nSubnet → サブネットを作成\nRoute tables → ルートテーブルを作成\n\nCIDR、AZ、tag、VPC association は ledger と照合する。",
    8.2,
    1.55,
    4.3,
    2.45,
    PALE_BLUE,
    BLUE,
    17,
)
add_panel(
    slide,
    "証拠",
    "公開画像は account、resource ID、CIDR、IP をマスク。\n作成後は list page と detail page を再表示して state を確認する。",
    8.2,
    4.35,
    4.3,
    1.55,
    PALE_YELLOW,
    ORANGE,
    16,
)
add_footer(slide)

slide = new_slide(
    "AWS console | VPN / security resource screens",
    "gateway、VPN connection、security group、NACL の入口を確認する",
)
slide.shapes.add_picture(
    str(CONSOLE_VPN),
    Inches(0.7),
    Inches(1.35),
    width=Inches(5.9),
    height=Inches(3.15),
)
slide.shapes.add_picture(
    str(CONSOLE_SECURITY),
    Inches(6.75),
    Inches(1.35),
    width=Inches(5.9),
    height=Inches(3.15),
)
add_panel(
    slide,
    "左メニューの確認順",
    "Virtual Private Gateways\nCustomer gateways\nSite-to-Site VPN connections\nSecurity groups\nNetwork ACLs\n\n作成・変更は approval gate 後に実施。",
    0.7,
    4.85,
    5.9,
    1.45,
    PALE_BLUE,
    BLUE,
    16,
)
add_panel(
    slide,
    "確認する値",
    "state、VPC attachment、BGP ASN、remote endpoint、route table association、inbound / outbound rules。実値は公開画像へ残さない。",
    6.75,
    4.85,
    5.9,
    1.45,
    PALE_YELLOW,
    ORANGE,
    16,
)
add_footer(slide)

# Beginner runbook: target discovery
slide = new_slide(
    "実行手順 A | AWS 対象の discovery",
    "最初に ID、SVM、volume role を読み取り、台帳と一致させる",
)
add_code(
    slide,
    'export AWS_PROFILE="<aws-profile>"\nexport AWS_REGION="<aws-region>"\nexport FILE_SYSTEM_ID="<file-system-id>"\naws fsx describe-file-systems --file-system-ids "$FILE_SYSTEM_ID" \\\n  --query \'FileSystems[0].{Lifecycle:Lifecycle,Endpoints:OntapConfiguration.Endpoints}\'\naws fsx describe-storage-virtual-machines --filters Name=file-system-id,Values="$FILE_SYSTEM_ID"\naws fsx describe-volumes --filters Name=file-system-id,Values="$FILE_SYSTEM_ID"',
    0.7,
    1.45,
    7.1,
    3.35,
)
add_panel(
    slide,
    "合格条件",
    "file system / SVM / volume が台帳と一致。\nLifecycle が FAILED、対象が複数、role 不明なら停止。\nSVM endpoint と cluster management endpoint を分ける。",
    8.1,
    1.55,
    4.4,
    2.5,
    PALE_BLUE,
    BLUE,
    17,
)
add_panel(
    slide,
    "参照",
    "AWS console: FSx → File systems / Storage virtual machines / Volumes\nAWS CLI: describe-file-systems / describe-storage-virtual-machines / describe-volumes",
    8.1,
    4.35,
    4.4,
    1.45,
    PALE_YELLOW,
    ORANGE,
    16,
)
add_footer(slide)

# Beginner runbook: EC2 and credentials
slide = new_slide(
    "実行手順 B | EC2、SSH、credential",
    "既存 EC2 を優先し、Secrets Manager の値を表示しない",
)
add_code(
    slide,
    "aws ec2 describe-instances --instance-ids <ec2-instance-id> \\\n  --query 'Reservations[0].Instances[0].{State:State.Name,Subnet:SubnetId,SG:SecurityGroups}'\numask 077\nSECRET_JSON=$(mktemp)\ntrap 'rm -f \"$SECRET_JSON\"' EXIT\naws secretsmanager get-secret-value --secret-id <secret-name> \\\n  --query SecretString --output text > \"$SECRET_JSON\"",
    0.7,
    1.45,
    7.1,
    3.6,
)
add_panel(
    slide,
    "EC2 の選択条件",
    "FSx for ONTAP の cluster management endpoint と NFS endpoint へ到達。\nTCP 22 / 2049 は必要 CIDR だけ許可。\n新規 EC2 は disposable、IAM role、subnet、SG、cleanup を台帳へ記録。",
    8.1,
    1.55,
    4.4,
    2.65,
    PALE_BLUE,
    BLUE,
    16,
)
add_panel(
    slide,
    "credential の禁止事項",
    "標準出力、shell history、SSH 引数、ログ、PowerPoint に password を出さない。\nSVM endpoint ではなく cluster management endpoint を使う。",
    8.1,
    4.55,
    4.4,
    1.25,
    PALE_RED,
    RED,
    16,
)
add_footer(slide)

# Beginner runbook: ONTAP state
slide = new_slide(
    "実行手順 C | ONTAP state の取得",
    "mutation 前に version、peer、relationship の実際の出力を保存する",
)
add_code(
    slide,
    'ssh fsxadmin@<cluster-management-dns> version\nssh fsxadmin@<cluster-management-dns> \\\n  "vserver show -vserver <fsx-svm-name>"\nssh fsxadmin@<cluster-management-dns> \\\n  "volume show -vserver <fsx-svm-name>"\nssh fsxadmin@<cluster-management-dns> \\\n  "snapmirror show -vserver <fsx-svm-name>"\nssh fsxadmin@<cluster-management-dns> "vserver peer show"\nssh fsxadmin@<cluster-management-dns> "cluster peer show"',
    0.7,
    1.45,
    7.1,
    3.7,
)
add_panel(
    slide,
    "今回の verified state",
    "ONTAP 9.18.1P6\nSVM peer: peered\napplications: snapmirror, flexcache\nSnapMirror: Snapmirrored / Idle / Healthy true",
    8.1,
    1.55,
    4.4,
    2.55,
    PALE_BLUE,
    BLUE,
    17,
)
add_panel(
    slide,
    "STOP",
    "cluster peer: Unavailable\ncreate / initialize / break / resync / FlexCache create は実行しない。\n出力は private ledger に保存する。",
    8.1,
    4.45,
    4.4,
    1.45,
    PALE_RED,
    RED,
    17,
)
add_footer(slide)

# 11. Peering
slide = new_slide(
    "10. Phase 3 | Cluster / SVM peering",
    "GCNV が initiate、FSx for ONTAP が accept。片側 state だけで完了にしない",
)
add_panel(
    slide,
    "GCP 側で収集",
    "replication resource identity\ninitiate request の method / body\npassphrase handoff\noperation completion predicate",
    0.7,
    1.55,
    3.8,
    4.4,
    PALE_BLUE,
    BLUE,
)
add_panel(
    slide,
    "AWS 側で収集",
    "acceptance interface\nlocal / peer cluster identity\nlocal / peer SVM identity\napplications: SnapMirror / FlexCache",
    4.8,
    1.55,
    3.8,
    4.4,
    PALE_ORANGE,
    ORANGE,
)
add_panel(
    slide,
    "両側の合格",
    "fresh read を同じ run ID に記録\npeering state が両側で一致\nidentity、ownership、applications が台帳と一致\n欠けたら replication へ進まない",
    8.9,
    1.55,
    3.8,
    4.4,
    PALE_RED,
    RED,
)
add_footer(slide, 11)

# 12. Forward SnapMirror
slide = new_slide(
    "11. Phase 4 | SnapMirror FSx for ONTAP → GCNV",
    "方向 A: source / destination / post-state を分けて確認",
)
add_image(slide, "gcp-fsx-ontap-snapmirror-fsx-to-gcnv@2x.png", 0.7, 1.35, 7.1, 4.35)
add_panel(
    slide,
    "実行前の確認",
    "source = gcnv_snapmirror_src\ndestination = <gcnv-destination-volume>\nrelationship interface = documented\ninitialize / transfer の完了 predicate = documented",
    8.1,
    1.5,
    4.4,
    2.55,
    PALE_ORANGE,
    ORANGE,
    17,
)
add_panel(
    slide,
    "Open の扱い",
    "GCNV 側の create / initialize interface が確定していないため、ここでは command を実行しない。",
    8.1,
    4.35,
    4.4,
    1.25,
    PALE_RED,
    RED,
    17,
)
add_footer(slide, 12)

# 13. Reverse Resync
slide = new_slide(
    "12. Phase 5 | Reverse Resync GCNV → FSx for ONTAP",
    "方向 B: Break 後の write state と新しい方向を別に確認",
)
add_image(
    slide, "gcp-fsx-ontap-reverse-resync-gcnv-to-fsx@2x.png", 0.7, 1.35, 7.1, 4.35
)
add_panel(
    slide,
    "実行前の確認",
    "break / stop の authoritative interface\nGCNV source role\nFSx for ONTAP destination role\nreverse operation と post-state query",
    8.1,
    1.5,
    4.4,
    2.55,
    PALE_BLUE,
    BLUE,
    17,
)
add_panel(
    slide,
    "停止条件",
    "`snapmirror resync` などの推測 command を実行しない。identity、direction、DP/read-only state が不一致なら停止。",
    8.1,
    4.35,
    4.4,
    1.25,
    PALE_RED,
    RED,
    17,
)
add_footer(slide, 13)

# 14. FlexCache forward
slide = new_slide(
    "13. Phase 6 | FlexCache FSx for ONTAP origin → GCNV cache",
    "方向 A: origin と cache の作成責任を確定してから進む",
)
add_image(
    slide,
    "gcp-fsx-ontap-flexcache-fsx-origin-to-gcnv-cache@2x.png",
    0.7,
    1.35,
    7.1,
    4.35,
)
add_panel(
    slide,
    "台帳",
    "origin = <FSx for ONTAP SVM:volume>\ncache = <GCNV SVM:volume>\nclient protocol = NFS / SMB\ncache state query = <documented>",
    8.1,
    1.5,
    4.4,
    2.55,
    PALE_BLUE,
    BLUE,
    17,
)
add_panel(
    slide,
    "Open",
    "GCNV cache creation interface、owner、post-state は未検証。SVM peering の applications だけでは成功証拠にならない。",
    8.1,
    4.35,
    4.4,
    1.25,
    PALE_RED,
    RED,
    17,
)
add_footer(slide, 14)

# 15. FlexCache reverse
slide = new_slide(
    "14. Phase 7 | FlexCache GCNV origin → FSx for ONTAP cache",
    "方向 B: origin の反転を想定せず、別の関係として確認",
)
add_image(
    slide,
    "gcp-fsx-ontap-flexcache-gcnv-origin-to-fsx-cache@2x.png",
    0.7,
    1.35,
    7.1,
    4.35,
)
add_panel(
    slide,
    "台帳",
    "origin = <GCNV SVM:volume>\ncache = <FSx for ONTAP SVM:volume>\norigin/cache direction\nNFS / SMB access path",
    8.1,
    1.5,
    4.4,
    2.55,
    PALE_ORANGE,
    ORANGE,
    17,
)
add_panel(
    slide,
    "停止条件",
    "cache create / modify / delete の interface と inverse operation が不明なら、作成も削除も実行しない。",
    8.1,
    4.35,
    4.4,
    1.25,
    PALE_RED,
    RED,
    17,
)
add_footer(slide, 15)

# 16. Cleanup
slide = new_slide(
    "15. Cleanup | run-created だけを片付ける",
    "shared resource、active transfer、依存関係は owner review へ残す",
)
add_bullets(
    slide,
    [
        "1. fixture directory と一時 mount を解除する。既存 mount は解除しない。",
        "2. run-created の一時 client だけを、owner と identity の fresh read 後に停止・削除する。",
        "3. run-created の route / security rule / BGP advertisement だけを、直前の値と照合して戻す。",
        "4. VPN、Cloud Router、VGW、SVM、volume、peering、active transfer は共有・依存関係を確認して残す。",
        "5. relationship の break / delete は別承認なしに実行しない。",
    ],
    0.85,
    1.5,
    11.7,
    4.2,
    19,
)
add_panel(
    slide,
    "削除しない対象",
    "shared / pre-existing resource、owner 不明、active transfer、依存 relationship、逆操作不明",
    1.0,
    5.85,
    11.2,
    0.72,
    PALE_RED,
    RED,
    17,
)
add_footer(slide, 16)

# 17. Completion checklist
slide = new_slide(
    "16. 完了判定と参照先", "状態の証拠とファイル内容の証拠を分離して閉じる"
)
add_panel(
    slide,
    "完了条件",
    "☐ route / return / TCP 2049\n☐ NFS source / FSTYPE\n☐ 48 files / manifest / SHA-256\n☐ DP read-only\n☐ cleanup 境界",
    0.7,
    1.5,
    3.8,
    4.45,
    PALE_BLUE,
    BLUE,
    17,
)
add_panel(
    slide,
    "Open のまま残す項目",
    "☐ GCNV peering interface\n☐ FSx for ONTAP acceptance interface\n☐ SnapMirror create / initialize\n☐ Reverse Resync\n☐ FlexCache create / state",
    4.8,
    1.5,
    3.8,
    4.45,
    PALE_RED,
    RED,
    17,
)
add_panel(
    slide,
    "詳細文書",
    "gcp-to-fsx-ontap-preflight-and-sample-validation.md\ngcp-to-fsx-ontap-peering-and-replication-open-items.md\n方向別 SVG / dark theme 図は各文書から参照",
    8.9,
    1.5,
    3.8,
    4.45,
    PALE_YELLOW,
    ORANGE,
    17,
)
add_text(
    slide,
    "完了とは、全項目を実行することではなく、実行した項目と Open の項目を台帳で区別できる状態。",
    0.9,
    6.3,
    11.5,
    0.45,
    20,
    NAVY,
    True,
    PP_ALIGN.CENTER,
)
add_footer(slide, 17)

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print(OUT)
