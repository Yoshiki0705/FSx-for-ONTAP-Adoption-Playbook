# Amazon FSx for NetApp ONTAP — Adoption Playbook

![docs](https://img.shields.io/badge/docs-lint%20passing-brightgreen) ![i18n](https://img.shields.io/badge/i18n-8%20languages-blue) ![license](https://img.shields.io/badge/license-MIT-blue) ![region](https://img.shields.io/badge/verified-ap--northeast--1-blue)

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](../zh-TW/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->

---

> **Amazon FSx for NetApp ONTAP** 로의 마이그레이션과 그 이후의 설계·구축·운영을 진행하기 위한 지식 모음입니다.
> 라이프사이클(평가 → 설계 → 마이그레이션 → 구축 → 운영 → 최적화)과 주제(데이터 보호·데이터 활용·보안·성능·비용·멀티프로토콜 ID)의 **두 축**으로 찾을 수 있습니다.
>
> 기술 지원 현장에서 얻은 지식을 익명화된 참고 자료로 정리하고 있습니다. 사람인 독자와 AI 에이전트 / 웹 크롤러 양쪽에서 참조할 수 있는 구조를 의도했습니다.

---

## 시작하기

| 하려는 작업 | 가이드 | 소요 시간 |
|---|---|---|
| 이 리포지토리를 둘러보는 방법 알기 | [내비게이션 가이드](navigation.md) | 3분 |
| 마이그레이션 가능성과 방법 판단 | [마이그레이션 방식 결정 트리](../ja/reference/decision-trees/migration-method.md) | 10분 |
| 검증된 상한값 확인 | [상한값·쿼터](../ja/reference/limits/) | 5분 |
| 지식의 신뢰도를 읽는 방법 알기 | [지식 분류 정책](evidence-policy.md) | 5분 |
| 지식 추가하기(집필) | [CONTRIBUTING.md](../../CONTRIBUTING.md) | 10분 |

> **수록 현황**: 라이프사이클 6개 모듈과 테마 6개 모듈은 현재 "다룰 질문과 구조를 정의한 단계"입니다(`notes/`는 미수록).
> 각 모듈 README에 해당 모듈이 답할 예정인 질문이 정리되어 있습니다.
> 골격만 있는 입구에 독자의 시간을 쓰지 않도록, 위 표에는 **현재 내용이 있는 자료만** 실었습니다. 모듈 전체 구성은 아래 2축 내비게이션을 참조하세요.

---

<details>
<summary><strong>🗺️ 2축 내비게이션 (클릭하여 펼치기)</strong></summary>

### 라이프사이클 축 — `playbooks/`

"지금 나는 어느 단계에 있는가"에서 출발하는 입구입니다.

| # | 모듈 | 다루는 질문 |
|---|---|---|
| 01 | [`01-assess/`](../en/playbooks/01-assess/) | 현행 NAS에 무엇이 있고, 무엇이 마이그레이션의 제약이 되는가 |
| 02 | [`02-design/`](../en/playbooks/02-design/) | 어떤 구성·용량·스루풋·보호 방식을 선택하는가 |
| 03 | [`03-migrate/`](../en/playbooks/03-migrate/) | 어떤 방식으로, 어떻게 전환하고, 어떻게 되돌리는가 |
| 04 | [`04-build/`](../en/playbooks/04-build/) | IaC·자동화·재현 가능한 구축을 어떻게 구성하는가 |
| 05 | [`05-operate/`](../en/playbooks/05-operate/) | 모니터링·용량·장애 대응·변경 관리를 어떻게 운영하는가 |
| 06 | [`06-optimize/`](../en/playbooks/06-optimize/) | 성능과 비용을 어디까지 다듬을 것인가 |

### 주제 축 — `domains/`

"이 논점을 조사하고 싶다"에서 출발하는 입구입니다. 라이프사이클 전체에서 참조됩니다.

| 모듈 | 다루는 질문 |
|---|---|
| [`data-protection/`](../en/domains/data-protection/) | Snapshot / SnapMirror / SnapLock / 백업·랜섬웨어 대응 |
| [`data-utilization/`](../en/domains/data-utilization/) | 분석·AI/RAG·S3 API 경유 데이터 활용 |
| [`security-governance/`](../en/domains/security-governance/) | 암호화·감사·권한 설계·규제 대응의 관점 |
| [`performance/`](../en/domains/performance/) | 스루풋 설계·레이턴시·캐시·공유 대역 |
| [`cost/`](../en/domains/cost/) | 용량·티어링과 견적 대비 실측의 차이 |
| [`multiprotocol-identity/`](../en/domains/multiprotocol-identity/) | NFS / SMB 공존·Active Directory 연계·ID 매핑 |

### 횡단 참조 — `reference/`

| 디렉터리 | 개요 |
|---|---|
| [`decision-trees/`](../ja/reference/decision-trees/) | 선택 플로차트(마이그레이션 방식·보호 방식·프로토콜) |
| [`comparison/`](../ja/reference/comparison/) | 선택지 비교 매트릭스(트레이드오프를 대칭으로 기재) |
| [`limits/`](../ja/reference/limits/) | 상한값·쿼터와 그 출처·검증일 |
| [`glossary/`](../ja/reference/glossary/) | ONTAP / AWS 용어의 정의 |

</details>

<details>
<summary><strong>📁 모듈의 공통 구조 (확장 방법)</strong></summary>

`playbooks/`와 `domains/`의 각 모듈은 **동일한 내부 구조**를 가집니다. 새 모듈을 추가할 때는 `_template/`을 복사하세요.

```text
docs/<lang>/{playbooks,domains}/<module>/
├── README.md          # 모듈 허브
├── notes/             # 지식의 최소 단위. 1 파일 = 1 논점
│   └── <slug>.md      # YAML frontmatter 필수
└── checklists/        # 현장에서 사용하는 체크리스트
    └── <slug>.md
```

`notes/`의 각 파일은 YAML frontmatter로 메타데이터를 가집니다. AI 에이전트와 웹 크롤러가 구조로 해석할 수 있도록 하기 위함입니다.

```yaml
---
title: SnapMirror 초기 동기화에서 스루풋이 나오지 않을 때의 원인 분리
lifecycle: [migrate]          # playbooks 축의 태그
domains: [performance]        # domains 축의 태그
evidence: verified            # verified | documented | field-observation | hypothesis
verified_on: 2026-08-06       # evidence: verified 일 때 필수
ontap_version: 9.17.1P7D1     # 검증 시 버전(해당하는 경우)
region: ap-northeast-1        # 검증 리전(해당하는 경우)
lang: ko
---
```

`evidence`의 4단계는 독자가 "어디까지 신뢰하고 사용할 수 있는지"를 판단하기 위한 구분입니다. 자세한 내용은 [지식 분류 정책](evidence-policy.md)을 참조하세요.

</details>

<details>
<summary><strong>📚 사례의 취급 (익명화 정책)</strong></summary>

`case-studies/`에는 기술 지원 현장에서 얻은 지식을 실지만, **공개할 수 없는 정보는 일절 포함하지 않습니다**.

| 포함하지 않는 것 | 대신 쓰는 것 |
|---|---|
| 기업명·조직명·부서명 | 업종과 규모 구간(예: 제조업 / 수백 TB 규모) |
| 구체적인 호스트명·IP·계정 ID | 플레이스홀더(`10.0.x.x`, `123456789012`) |
| 실제 구성도 그대로 | 논점이 전달되는 범위로 추상화한 구성 |
| 담당자명·리뷰어명 | 역할 기반 표기(예: 스토리지 운영 담당의 관점) |
| 지원 케이스 번호·내부 티켓 ID | "벤더에 확인 완료(추적 중)" |

사례는 "무엇이 문제였고, 어떻게 판단했으며, 결과가 어땠는지"를 **일반화된 교훈**으로 씁니다. 템플릿은 [`case-studies/_template/`](../ja/case-studies/_template/)에 있습니다. 공개 전 확인은 `make audit`으로 자동화되어 있습니다.

</details>

<details>
<summary><strong>🌐 다국어 정책 (8개 언어)</strong></summary>

번역 비용과 최신성을 양립시키기 위해 **3단계**로 구분합니다.

| 단계 | 대상 | 언어 |
|---|---|---|
| Tier 1 | 루트 `README`, `docs/<lang>/`의 주요 가이드 | 8개 언어 전부 |
| Tier 2 | 각 모듈의 `README` | 日本語 + English |
| Tier 3 | `notes/`, `checklists/`의 개별 파일 | 日本語(English은 선택) |

지원 언어: 日本語 / English / 한국어 / 简体中文 / 繁體中文 / Français / Deutsch / Español

Tier 1은 **섹션 구성과 개수가 언어 간에 일치**하는지를 CI에서 검사합니다(`make i18n-check`). 번역하지 않는 것: 파일 경로, 명령어, 배지 URL, 앵커 ID, 제품명·기술 용어(ONTAP, SnapMirror, FlexCache, SnapLock, S3 Access Point 등).

</details>

<details>
<summary><strong>🤖 AI 에이전트 / 크롤러용</strong></summary>

이 리포지토리는 사람인 독자와 기계 독자 양쪽을 상정합니다.

| 파일 | 용도 |
|---|---|
| [`llms.txt`](../../llms.txt) | LLM용 리포지토리 전체 맵([llmstxt.org](https://llmstxt.org/) 준수) |
| [`AGENTS.md`](../../AGENTS.md) | 코딩 에이전트용 규약·금지 사항·검증 절차 |
| `notes/*.md`의 frontmatter | 기계 판독 가능한 메타데이터(라이프사이클 / 주제 / 증적 수준 / 검증일) |
| [`reference/limits/`](../ja/reference/limits/) | 상한값을 출처·검증일과 함께 구조화 |

**지식을 인용하는 쪽에 대한 주의**: `evidence: hypothesis`나 `field-observation` 노트는 검증된 사실이 아닙니다. frontmatter의 `evidence`를 반드시 확인하세요.

</details>

<details>
<summary><strong>🔧 기여·로컬 검증</strong></summary>

```bash
make help          # 사용 가능한 타깃 목록
make lint          # Markdown lint + frontmatter 스키마 검증
make i18n-check    # Tier 1 문서의 언어 간 패리티 검사
make audit         # 공개 전 확인(명명 / 중립성 / 개인정보 / 내부 ID)
make links         # 링크 끊김 검사
make all           # 위 전부
```

Issue / Pull Request를 환영합니다. 집필 규약은 [CONTRIBUTING.md](../../CONTRIBUTING.md), 지식 분류 기준은 [지식 분류 정책](evidence-policy.md)을 참조하세요.

</details>

---

## 관련 리포지토리

| 리포지토리 | 개요 |
|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | S3 Access Points 서버리스 처리 패턴 모음(45+) |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | 가관측성 통합(메트릭, 알림, 자동 대응) |
| [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) | Lakehouse 통합(Databricks / Snowflake / Athena / Glue / EMR) |
| [vmware-migration-ec2-ontap](https://github.com/Yoshiki0705/vmware-migration-ec2-ontap) | VMware → EC2 + FSx for ONTAP 마이그레이션 |

---

## 면책

본 리포지토리는 개인이 정리한 기술 정보이며, 소속 조직의 공식 견해가 아닙니다.
거버넌스나 규제 대응에 관한 기술은 **일반적인 설계상의 고려 사항**이며, 법무·컴플라이언스상의 판단이 아닙니다. 벤치마크 값은 기재된 검증 환경에서의 실측이며, 일반적인 서비스 상한이나 프로덕션 환경에서의 재현을 보장하지 않습니다.

이 리포지토리의 일본어판이 기술적 정본입니다. 다른 언어판은 기계 지원 번역이며 공개 전 원어민 검수를 거치지 않았습니다. 내용이 다를 경우 일본어판이 우선합니다. 오류를 발견하시면 [Issue](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues)로 알려주십시오.

## 라이선스

MIT — [LICENSE](../../LICENSE)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](../zh-TW/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->
