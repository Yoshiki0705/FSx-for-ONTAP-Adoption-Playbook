# Amazon FSx for NetApp ONTAP — Adoption Playbook

![docs](https://img.shields.io/badge/docs-lint%20passing-brightgreen) ![i18n](https://img.shields.io/badge/i18n-8%20languages-blue) ![license](https://img.shields.io/badge/license-MIT-blue) ![region](https://img.shields.io/badge/verified-ap--northeast--1-blue)

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](../ko/README.md) | [简体中文](README.md) | [繁體中文](../zh-TW/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->

---

> 面向迁移到 **Amazon FSx for NetApp ONTAP** 以及后续设计、构建、运维工作的知识库。
> 提供**两个检索轴**：生命周期（评估 → 设计 → 迁移 → 构建 → 运维 → 优化）与主题（数据保护、数据利用、安全、性能、成本、多协议身份）。
>
> 将技术支持现场获得的经验整理为匿名化的参考资料。结构上同时面向人类读者与 AI 代理 / 网络爬虫。

---

## 开始使用

| 你想做的事 | 指南 | 预计时间 |
|---|---|---|
| 了解如何浏览本仓库 | [导航指南](navigation.md) | 3 分钟 |
| 判断能否迁移以及如何迁移 | [迁移方式决策树](../ja/reference/decision-trees/migration-method.md) | 10 分钟 |
| 查看已验证的上限值 | [上限值与配额](../ja/reference/limits/) | 5 分钟 |
| 了解如何判读知识的可信度 | [知识分类政策](evidence-policy.md) | 5 分钟 |
| 从公开信息中查找一次信息 | [公开的一次信息与案例入口](../ja/case-studies/public-references.md) (日本語) | 5 分钟 |
| 补充知识（撰写） | [CONTRIBUTING.md](../../CONTRIBUTING.md) | 10 分钟 |

> **收录情况**：12 个模块中已有 8 个模块具备内容（`notes/` 7 篇、`checklists/` 1 篇）。
> 其余 4 个模块（[`02-design/`](../ja/playbooks/02-design/)、[`06-optimize/`](../ja/playbooks/06-optimize/)、[`security-governance/`](../ja/domains/security-governance/)、[`cost/`](../ja/domains/cost/)）目前处于已定义待解决问题的阶段。
> 为了不让读者把时间花在只有骨架的入口上，上表只列出**目前已有内容的资料**。各篇笔记目前以日语撰写，模块全貌请参见下方的双轴导航。

### 目前可阅读的资料

每篇资料均为「1 个文件 = 1 个议题」，并且必定包含**一次信息的出处**与**在自己环境中确认的步骤**。正文目前为日语，因此标题也保留日语原文。

- [容量が余っていても書けなくなる](../ja/playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md) (日本語)
- [ACL 保持は権限の問題であってツールの問題ではない](../ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md) (日本語)
- [監視は平均値で失敗する](../ja/playbooks/05-operate/notes/monitoring-fails-on-averages.md) (日本語)
- [Snapshot があることと復旧できることは別](../ja/domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) (日本語)
- [ボリュームのセキュリティスタイルが権限評価のモデルを決める](../ja/domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) (日本語)
- [スループットは 1 つの設定値では決まらない](../ja/domains/performance/notes/where-throughput-is-determined-and-shared.md) (日本語)
- [FSx for ONTAP S3 AP は「S3 として使える」わけではない](../ja/domains/data-utilization/notes/s3-access-point-constraints.md) (日本語)
- [本番投入前レビュー](../ja/playbooks/04-build/checklists/pre-production-review.md) (日本語)

此外，各模块的 README 会标示该模块回答的问题，以及尚未撰写的条目。

---

<details>
<summary><strong>🗺️ 双轴导航（点击展开）</strong></summary>

### 生命周期轴 — `playbooks/`

从"我现在处于哪个阶段"出发的入口。

| # | 模块 | 所解答的问题 |
|---|---|---|
| 01 | [`01-assess/`](../en/playbooks/01-assess/) | 现有 NAS 上有什么，什么会成为迁移的约束 |
| 02 | [`02-design/`](../en/playbooks/02-design/) | 选择哪种配置、容量、吞吐量与保护方式 |
| 03 | [`03-migrate/`](../en/playbooks/03-migrate/) | 采用哪种方式、如何切换、如何回滚 |
| 04 | [`04-build/`](../en/playbooks/04-build/) | 如何组织 IaC、自动化与可复现的构建 |
| 05 | [`05-operate/`](../en/playbooks/05-operate/) | 如何运转监控、容量、故障响应与变更管理 |
| 06 | [`06-optimize/`](../en/playbooks/06-optimize/) | 性能与成本要调优到什么程度 |

### 主题轴 — `domains/`

从"我要研究这个议题"出发的入口。跨生命周期被引用。

| 模块 | 所解答的问题 |
|---|---|
| [`data-protection/`](../en/domains/data-protection/) | Snapshot / SnapMirror / SnapLock / 备份与勒索软件应对 |
| [`data-utilization/`](../en/domains/data-utilization/) | 分析、AI/RAG、经由 S3 API 的数据利用 |
| [`security-governance/`](../en/domains/security-governance/) | 加密、审计、权限设计、合规议题的思考方式 |
| [`performance/`](../en/domains/performance/) | 吞吐量设计、延迟、缓存、共享带宽 |
| [`cost/`](../en/domains/cost/) | 容量、分层，以及估算与实测之间的差异 |
| [`multiprotocol-identity/`](../en/domains/multiprotocol-identity/) | NFS / SMB 共存、Active Directory 集成、ID 映射 |

### 横向参考 — `reference/`

| 目录 | 内容 |
|---|---|
| [`decision-trees/`](../ja/reference/decision-trees/) | 选择流程图（迁移方式、保护方式、协议） |
| [`comparison/`](../ja/reference/comparison/) | 选项比较矩阵（对称地列出权衡） |
| [`limits/`](../ja/reference/limits/) | 上限与配额，附出处与验证日期 |
| [`glossary/`](../ja/reference/glossary/) | ONTAP / AWS 术语定义 |

</details>

<details>
<summary><strong>📁 模块的通用结构（如何扩展）</strong></summary>

`playbooks/` 与 `domains/` 下的每个模块都拥有**相同的内部结构**。新增模块时请复制 `_template/`。

```text
docs/<lang>/{playbooks,domains}/<module>/
├── README.md          # 模块枢纽
├── notes/             # 知识的最小单位。1 个文件 = 1 个议题
│   └── <slug>.md      # 必须包含 YAML frontmatter
└── checklists/        # 现场使用的检查清单
    └── <slug>.md
```

`notes/` 下的每个文件都以 YAML frontmatter 携带元数据，目的是让 AI 代理与网络爬虫能够将其作为结构来解析。

```yaml
---
title: SnapMirror 初始同步吞吐量偏低时的排查
lifecycle: [migrate]          # playbooks 轴的标签
domains: [performance]        # domains 轴的标签
evidence: verified            # verified | documented | field-observation | hypothesis
verified_on: 2026-08-06       # evidence: verified 时必填
ontap_version: 9.17.1P7D1     # 验证时的版本（如适用）
region: ap-northeast-1        # 验证区域（如适用）
lang: zh-CN
---
```

`evidence` 的四个级别用于让读者判断"该记述可以信赖到什么程度"。详情参见[知识分级政策](evidence-policy.md)。

</details>

<details>
<summary><strong>📚 案例的处理方式（匿名化政策）</strong></summary>

`case-studies/` 收录技术支持现场获得的经验，但**绝不包含任何不可公开的信息**。

| 不收录的内容 | 改写为 |
|---|---|
| 企业名、组织名、部门名 | 行业与规模区间（例：制造业 / 数百 TB 规模） |
| 具体主机名、IP、账户 ID | 占位符（`10.0.x.x`、`123456789012`） |
| 原样的架构图 | 抽象到能传达议题的程度 |
| 负责人姓名、评审者姓名 | 基于角色的表述（例：从存储运维的视角） |
| 支持案例编号、内部工单 ID | "已向厂商确认（跟踪中）" |

案例以**一般化的教训**来撰写：问题是什么、如何判断、结果如何。模板位于 [`case-studies/_template/`](../ja/case-studies/_template/)。公开前检查已通过 `make audit` 自动化。

</details>

<details>
<summary><strong>🌐 多语言政策（8 种语言）</strong></summary>

为兼顾翻译成本与时效性，划分为**三个层级**。

| 层级 | 范围 | 语言 |
|---|---|---|
| Tier 1 | 根 `README`、`docs/<lang>/` 的主要指南 | 全部 8 种语言 |
| Tier 2 | 各模块的 `README` | 日本語 + English |
| Tier 3 | `notes/`、`checklists/` 的单个文件 | 日本語（English 可选） |

支持语言：日本語 / English / 한국어 / 简体中文 / 繁體中文 / Français / Deutsch / Español

Tier 1 由 CI 检查**章节结构与数量在各语言间是否一致**（`make i18n-check`）。不翻译的内容：文件路径、命令、徽章 URL、锚点 ID、产品名与技术术语（ONTAP、SnapMirror、FlexCache、SnapLock、S3 Access Point 等）。

</details>

<details>
<summary><strong>🤖 面向 AI 代理 / 爬虫</strong></summary>

本仓库同时面向人类读者与机器读者。

| 文件 | 用途 |
|---|---|
| [`llms.txt`](../../llms.txt) | 面向 LLM 的仓库整体地图（遵循 [llmstxt.org](https://llmstxt.org/)） |
| [`AGENTS.md`](../../AGENTS.md) | 面向编码代理的规约、禁止事项与验证步骤 |
| `notes/*.md` 的 frontmatter | 机器可读的元数据（生命周期 / 主题 / 证据级别 / 验证日期） |
| [`reference/limits/`](../ja/reference/limits/) | 将上限值与出处、验证日期一并结构化 |

**给引用方的提醒**：标记为 `evidence: hypothesis` 或 `field-observation` 的笔记并非已验证的事实。请务必确认 frontmatter 中的 `evidence`。

</details>

<details>
<summary><strong>🔧 贡献与本地验证</strong></summary>

```bash
make help          # 列出可用目标
make lint          # Markdown lint + frontmatter 模式校验
make i18n-check    # Tier 1 文档的跨语言一致性检查
make audit         # 公开前检查（命名 / 中立性 / 个人信息 / 内部 ID）
make links         # 链接失效检查
make all           # 以上全部
```

欢迎提交 Issue / Pull Request。撰写规约见 [CONTRIBUTING.md](../../CONTRIBUTING.md)，知识分级标准见[知识分级政策](evidence-policy.md)。

</details>

---

## 相关仓库

| 仓库 | 内容 |
|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | S3 Access Points 无服务器处理模式集（45+） |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | 可观测性集成（指标、告警、自动响应） |
| [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) | Lakehouse 集成（Databricks / Snowflake / Athena / Glue / EMR） |
| [vmware-migration-ec2-ontap](https://github.com/Yoshiki0705/vmware-migration-ec2-ontap) | VMware → EC2 + FSx for ONTAP 迁移 |

---

## 免责声明

本仓库为个人整理的技术信息，不代表所属组织的官方立场。
关于治理或合规的记述均为**一般性的设计考量**，而非法务或合规判断。基准测试数值为所载验证环境下的实测结果，不保证等同于通用服务上限，也不保证在生产环境中可复现。

本仓库的日语版为技术正式版本。其他语言为机器辅助译文，发布前未经母语审校；如有出入，以日语版为准。如发现错误，欢迎通过 [Issue](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues) 反馈。

## 许可证

MIT — [LICENSE](../../LICENSE)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](../ko/README.md) | [简体中文](README.md) | [繁體中文](../zh-TW/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->
