# Translation terms

<!-- audit-file-allow: naming -->
<!-- Lists the product terms that must survive translation verbatim, so it necessarily writes them
     out. The file-level allowance exempts it from the naming audit. -->

Fixed renderings for the terms that carry a judgment, plus the list of things that are never
translated. Read this before translating a Tier 1 document.

It sits next to [`i18n-manifest.txt`](i18n-manifest.txt) because both are localization machinery
rather than reader content. The manifest decides *which* languages a document needs; this decides
*how* its vocabulary is rendered.

Why it exists: without a fixed table the same term drifts between files and between languages, and
drift in a word like "irreversible" or "verified" changes what a reader believes they are allowed to
do.

---

## Never translated

| Category | Examples |
|---|---|
| File paths and directory names | `docs/ja/navigation.md`, `notes/`, `_template/` |
| Commands and targets | `make all`, `make switcher-write`, `python3 tools/check_links.py` |
| Badge and image URLs | `img.shields.io/...` |
| Anchor IDs in code spans | `#before-adopting-into-production` |
| Frontmatter keys and values | `evidence`, `verified_on`, `lifecycle`, `domains`, `lang` |
| Evidence tier values | `verified`, `documented`, `field-observation`, `hypothesis` |
| Product and technical terms | Amazon FSx for NetApp ONTAP, FSx for ONTAP, ONTAP, SnapMirror, FlexCache, FlexClone, SnapLock, FabricPool, S3 Access Point, SVM, LIF, NFS, SMB, Active Directory, Snapshot |

**The evidence tier values are identifiers, not prose.** They appear in frontmatter and are matched
by `tools/validate_frontmatter.py`. Translate the *explanation* of a tier, never the tier name — a
reader who sees a translated tier name cannot match it against what the files actually contain.

Anchor targets are a related trap. Headings *are* translated, so each language generates its own
anchors. A link inside a translated document must use that language's anchor, never the Japanese
one. `tools/check_links.py` verifies anchors, so a copied Japanese anchor fails the gate.

---

## Fixed renderings

Terms whose wording changes what a reader thinks they may do. Use exactly these.

| ja | en | ko | zh-CN | zh-TW | fr | de | es |
|---|---|---|---|---|---|---|---|
| 証跡区分 | evidence tier | 근거 등급 | 证据等级 | 證據等級 | niveau de preuve | Evidenzstufe | nivel de evidencia |
| 検証済み | verified (reproduced) | 검증 완료 | 已验证 | 已驗證 | vérifié | verifiziert | verificado |
| 再現する | reproduce | 재현하다 | 复现 | 重現 | reproduire | reproduzieren | reproducir |
| 検証環境 | test environment | 검증 환경 | 验证环境 | 驗證環境 | environnement de test | Testumgebung | entorno de pruebas |
| 本番環境 | production | 운영 환경 | 生产环境 | 生產環境 | production | Produktion | producción |
| 不可逆 | irreversible | 되돌릴 수 없음 | 不可逆 | 不可逆 | irréversible | nicht umkehrbar | irreversible |
| 上限値 | limit | 상한값 | 上限值 | 上限值 | limite | Grenzwert | límite |
| 一般化する | generalize | 일반화하다 | 一般化 | 一般化 | généraliser | verallgemeinern | generalizar |
| 前提 | assumption | 전제 | 前提 | 前提 | hypothèse de départ | Annahme | supuesto |
| 昇格 / 降格 | promotion / demotion | 승급 / 강등 | 升级 / 降级 | 升級 / 降級 | promotion / rétrogradation | Höherstufung / Herabstufung | promoción / degradación |
| 匿名化 | anonymization | 익명화 | 匿名化 | 匿名化 | anonymisation | Anonymisierung | anonimización |
| 導線 | reading path | 이동 경로 | 阅读路径 | 閱讀路徑 | parcours de lecture | Leseweg | ruta de lectura |

---

## Authority notice

Every Tier 1 document carries this, symmetrically. Japanese states that it is authoritative; every
other language states that Japanese is.

| Language | Wording |
|---|---|
| ja | 本ドキュメントの日本語版が技術的な正典です。他言語版は翻訳であり、内容が食い違う場合は日本語版が優先します。 |
| en | The Japanese version of this document is authoritative for technical accuracy. Other languages are translations; where they disagree, the Japanese version prevails. |
| ko | 이 문서의 일본어판이 기술적 정본입니다. 다른 언어판은 번역이며, 내용이 다를 경우 일본어판이 우선합니다. |
| zh-CN | 本文档的日语版为技术正式版本。其他语言为译文，如有出入，以日语版为准。 |
| zh-TW | 本文件的日語版為技術正式版本。其他語言為譯文，如有出入，以日語版為準。 |
| fr | La version japonaise de ce document fait référence pour l'exactitude technique. Les autres langues sont des traductions ; en cas de divergence, la version japonaise prévaut. |
| de | Die japanische Fassung dieses Dokuments ist für die technische Richtigkeit maßgeblich. Andere Sprachen sind Übersetzungen; bei Abweichungen gilt die japanische Fassung. |
| es | La versión en japonés de este documento es la de referencia en cuanto a exactitud técnica. Los demás idiomas son traducciones; en caso de discrepancia, prevalece la versión en japonés. |

Translations here are produced with machine assistance and are not natively reviewed before
publication. A reader deciding whether to act on a statement is entitled to know that, which is why
the notice is required rather than optional.

Corrections are welcome as an
[Issue](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues).

---

## Related

- [`i18n-manifest.txt`](i18n-manifest.txt) — which languages each Tier 1 guide requires
- [CONTRIBUTING.md](../CONTRIBUTING.md) — the tier policy and what qualifies for eight languages
- [AGENTS.md](../AGENTS.md) — the same rules for coding agents
- [Glossary](ja/reference/glossary/) — definitions of the technical terms themselves (ja / en)
