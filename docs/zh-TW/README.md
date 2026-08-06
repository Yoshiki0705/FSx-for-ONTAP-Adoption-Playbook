# Amazon FSx for NetApp ONTAP — Adoption Playbook

![docs](https://img.shields.io/badge/docs-lint%20passing-brightgreen) ![i18n](https://img.shields.io/badge/i18n-8%20languages-blue) ![license](https://img.shields.io/badge/license-MIT-blue) ![region](https://img.shields.io/badge/verified-ap--northeast--1-blue)

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->

---

> 為遷移至 **Amazon FSx for NetApp ONTAP** 以及後續設計、建置、營運工作而整理的知識庫。
> 提供**兩個檢索軸**：生命週期（評估 → 設計 → 遷移 → 建置 → 營運 → 最佳化）與主題（資料保護、資料活用、安全、效能、成本、多協定身分）。
>
> 將技術支援現場獲得的經驗整理為匿名化的參考資料。結構上同時面向人類讀者與 AI 代理 / 網路爬蟲。

---

## 開始使用

| 你想做的事 | 指南 | 預計時間 |
|---|---|---|
| 了解如何瀏覽本儲存庫 | [導覽指南](navigation.md) | 3 分鐘 |
| 判斷能否遷移以及如何遷移 | [遷移方式決策樹](../ja/reference/decision-trees/migration-method.md) | 10 分鐘 |
| 查看已驗證的上限值 | [上限值與配額](../ja/reference/limits/) | 5 分鐘 |
| 了解如何判讀知識的可信度 | [知識分類政策](evidence-policy.md) | 5 分鐘 |
| 從公開資訊中查找第一手資訊 | [公開的第一手資訊與案例入口](../ja/case-studies/public-references.md) (日本語) | 5 分鐘 |
| 補充知識（撰寫） | [CONTRIBUTING.md](../../CONTRIBUTING.md) | 10 分鐘 |

> **收錄情況**：生命週期 6 個模組與主題 6 個模組目前處於「已定義待解決的問題與結構」的階段（`notes/` 尚未收錄）。
> 各模組的 README 列出了該模組計畫回答的問題。
> 為了不讓讀者把時間花在只有骨架的入口上，上表只列出**目前已有內容的資料**。模組全貌請參見下方的雙軸導覽。

---

<details>
<summary><strong>🗺️ 雙軸導覽（點擊展開）</strong></summary>

### 生命週期軸 — `playbooks/`

從「我現在處於哪個階段」出發的入口。

| # | 模組 | 所解答的問題 |
|---|---|---|
| 01 | [`01-assess/`](../en/playbooks/01-assess/) | 現有 NAS 上有什麼，什麼會成為遷移的限制 |
| 02 | [`02-design/`](../en/playbooks/02-design/) | 選擇哪種組態、容量、傳輸量與保護方式 |
| 03 | [`03-migrate/`](../en/playbooks/03-migrate/) | 採用哪種方式、如何切換、如何回復 |
| 04 | [`04-build/`](../en/playbooks/04-build/) | 如何組織 IaC、自動化與可重現的建置 |
| 05 | [`05-operate/`](../en/playbooks/05-operate/) | 如何運作監控、容量、故障應變與變更管理 |
| 06 | [`06-optimize/`](../en/playbooks/06-optimize/) | 效能與成本要調校到什麼程度 |

### 主題軸 — `domains/`

從「我要研究這個議題」出發的入口。跨生命週期被引用。

| 模組 | 所解答的問題 |
|---|---|
| [`data-protection/`](../en/domains/data-protection/) | Snapshot / SnapMirror / SnapLock / 備份與勒索軟體應變 |
| [`data-utilization/`](../en/domains/data-utilization/) | 分析、AI/RAG、經由 S3 API 的資料活用 |
| [`security-governance/`](../en/domains/security-governance/) | 加密、稽核、權限設計、法規議題的思考方式 |
| [`performance/`](../en/domains/performance/) | 傳輸量設計、延遲、快取、共用頻寬 |
| [`cost/`](../en/domains/cost/) | 容量、分層，以及估算與實測之間的落差 |
| [`multiprotocol-identity/`](../en/domains/multiprotocol-identity/) | NFS / SMB 共存、Active Directory 整合、ID 對應 |

### 橫向參考 — `reference/`

| 目錄 | 內容 |
|---|---|
| [`decision-trees/`](../ja/reference/decision-trees/) | 選擇流程圖（遷移方式、保護方式、協定） |
| [`comparison/`](../ja/reference/comparison/) | 選項比較矩陣（對稱地列出取捨） |
| [`limits/`](../ja/reference/limits/) | 上限與配額，附出處與驗證日期 |
| [`glossary/`](../ja/reference/glossary/) | ONTAP / AWS 術語定義 |

</details>

<details>
<summary><strong>📁 模組的通用結構（如何擴充）</strong></summary>

`playbooks/` 與 `domains/` 下的每個模組都擁有**相同的內部結構**。新增模組時請複製 `_template/`。

```text
docs/<lang>/{playbooks,domains}/<module>/
├── README.md          # 模組樞紐
├── notes/             # 知識的最小單位。1 個檔案 = 1 個議題
│   └── <slug>.md      # 必須包含 YAML frontmatter
└── checklists/        # 現場使用的檢查清單
    └── <slug>.md
```

`notes/` 下的每個檔案都以 YAML frontmatter 攜帶中介資料，目的是讓 AI 代理與網路爬蟲能夠將其作為結構來解析。

```yaml
---
title: SnapMirror 初始同步傳輸量偏低時的排查
lifecycle: [migrate]          # playbooks 軸的標籤
domains: [performance]        # domains 軸的標籤
evidence: verified            # verified | documented | field-observation | hypothesis
verified_on: 2026-08-06       # evidence: verified 時必填
ontap_version: 9.17.1P7D1     # 驗證時的版本（如適用）
region: ap-northeast-1        # 驗證區域（如適用）
lang: zh-TW
---
```

`evidence` 的四個級別用於讓讀者判斷「該敘述可以信賴到什麼程度」。詳情參見[知識分級政策](evidence-policy.md)。

</details>

<details>
<summary><strong>📚 案例的處理方式（匿名化政策）</strong></summary>

`case-studies/` 收錄技術支援現場獲得的經驗，但**絕不包含任何不可公開的資訊**。

| 不收錄的內容 | 改寫為 |
|---|---|
| 企業名、組織名、部門名 | 產業與規模區間（例：製造業 / 數百 TB 規模） |
| 具體主機名、IP、帳戶 ID | 佔位符（`10.0.x.x`、`123456789012`） |
| 原樣的架構圖 | 抽象到能傳達議題的程度 |
| 負責人姓名、審閱者姓名 | 基於角色的表述（例：從儲存營運的視角） |
| 支援案例編號、內部工單 ID | 「已向廠商確認（追蹤中）」 |

案例以**一般化的教訓**來撰寫：問題是什麼、如何判斷、結果如何。範本位於 [`case-studies/_template/`](../ja/case-studies/_template/)。公開前檢查已透過 `make audit` 自動化。

</details>

<details>
<summary><strong>🌐 多語言政策（8 種語言）</strong></summary>

為兼顧翻譯成本與時效性，劃分為**三個層級**。

| 層級 | 範圍 | 語言 |
|---|---|---|
| Tier 1 | 根 `README`、`docs/<lang>/` 的主要指南 | 全部 8 種語言 |
| Tier 2 | 各模組的 `README` | 日本語 + English |
| Tier 3 | `notes/`、`checklists/` 的個別檔案 | 日本語（English 可選） |

支援語言：日本語 / English / 한국어 / 简体中文 / 繁體中文 / Français / Deutsch / Español

Tier 1 由 CI 檢查**章節結構與數量在各語言間是否一致**（`make i18n-check`）。不翻譯的內容：檔案路徑、命令、徽章 URL、錨點 ID、產品名與技術術語（ONTAP、SnapMirror、FlexCache、SnapLock、S3 Access Point 等）。

</details>

<details>
<summary><strong>🤖 面向 AI 代理 / 爬蟲</strong></summary>

本儲存庫同時面向人類讀者與機器讀者。

| 檔案 | 用途 |
|---|---|
| [`llms.txt`](../../llms.txt) | 面向 LLM 的儲存庫整體地圖（遵循 [llmstxt.org](https://llmstxt.org/)） |
| [`AGENTS.md`](../../AGENTS.md) | 面向編碼代理的規約、禁止事項與驗證步驟 |
| `notes/*.md` 的 frontmatter | 機器可讀的中介資料（生命週期 / 主題 / 證據級別 / 驗證日期） |
| [`reference/limits/`](../ja/reference/limits/) | 將上限值與出處、驗證日期一併結構化 |

**給引用方的提醒**：標記為 `evidence: hypothesis` 或 `field-observation` 的筆記並非已驗證的事實。請務必確認 frontmatter 中的 `evidence`。

</details>

<details>
<summary><strong>🔧 貢獻與本機驗證</strong></summary>

```bash
make help          # 列出可用目標
make lint          # Markdown lint + frontmatter 結構驗證
make i18n-check    # Tier 1 文件的跨語言一致性檢查
make audit         # 公開前檢查（命名 / 中立性 / 個人資訊 / 內部 ID）
make links         # 連結失效檢查
make all           # 以上全部
```

歡迎提交 Issue / Pull Request。撰寫規約見 [CONTRIBUTING.md](../../CONTRIBUTING.md)，知識分級標準見[知識分級政策](evidence-policy.md)。

</details>

---

## 相關儲存庫

| 儲存庫 | 內容 |
|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | S3 Access Points 無伺服器處理模式集（45+） |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | 可觀測性整合（指標、告警、自動應變） |
| [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) | Lakehouse 整合（Databricks / Snowflake / Athena / Glue / EMR） |
| [vmware-migration-ec2-ontap](https://github.com/Yoshiki0705/vmware-migration-ec2-ontap) | VMware → EC2 + FSx for ONTAP 遷移 |

---

## 免責聲明

本儲存庫為個人整理的技術資訊，不代表所屬組織的官方立場。
關於治理或法規遵循的敘述皆為**一般性的設計考量**，而非法務或法遵判斷。基準測試數值為所載驗證環境下的實測結果，不保證等同於通用服務上限，也不保證在生產環境中可重現。

本儲存庫的日語版為技術正式版本。其他語言為機器輔助譯文，發布前未經母語審校；如有出入，以日語版為準。如發現錯誤，歡迎透過 [Issue](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues) 回報。

## 授權

MIT — [LICENSE](../../LICENSE)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->
