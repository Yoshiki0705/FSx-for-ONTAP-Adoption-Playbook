# Amazon FSx for NetApp ONTAP — Adoption Playbook

![docs](https://img.shields.io/badge/docs-lint%20passing-brightgreen) ![i18n](https://img.shields.io/badge/i18n-8%20languages-blue) ![license](https://img.shields.io/badge/license-MIT-blue) ![region](https://img.shields.io/badge/verified-ap--northeast--1-blue)

🌐 [日本語](README.md) | [English](README.en.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Español](README.es.md)

---

> Eine Wissensbasis für die Migration zu **Amazon FSx for NetApp ONTAP** und für die anschließende Arbeit an Design, Aufbau und Betrieb.
> Zwei Navigationsachsen: der Lebenszyklus (bewerten → entwerfen → migrieren → aufbauen → betreiben → optimieren) und das Thema (Datenschutz, Datennutzung, Sicherheit, Performance, Kosten, Multiprotokoll-Identität).
>
> Erkenntnisse aus der technischen Unterstützung im Feld sind hier als anonymisiertes Referenzmaterial aufbereitet. Die Struktur ist für menschliche Leser wie für KI-Agenten und Web-Crawler gleichermaßen gedacht.

---

## Erste Schritte

| Was Sie vorhaben | Leitfaden | Dauer |
|---|---|---|
| Verstehen, wie man dieses Repository durchsucht | [Navigationsleitfaden](docs/en/navigation.md) | 3 Min. |
| Entscheiden, ob und wie migriert wird | [Entscheidungsbaum: Migrationsmethode](reference/decision-trees/migration-method.md) | 10 Min. |
| Bestand des vorhandenen NAS aufnehmen | [Playbook 01 — Bewertung](playbooks/01-assess/) | 30 Min. |
| Zielkonfiguration entwerfen | [Playbook 02 — Design](playbooks/02-design/) | 60 Min. |
| Migration durchführen | [Playbook 03 — Migration](playbooks/03-migrate/) | — |
| Betrieb aufbauen | [Playbook 05 — Betrieb](playbooks/05-operate/) | — |
| Datenschutz entwerfen (Snapshot / SnapMirror / WORM) | [Domäne — Datenschutz](domains/data-protection/) | 30 Min. |
| Mit anderen Storage-Optionen vergleichen | [Vergleichsmatrizen](reference/comparison/) | 15 Min. |
| Fallbeispiele lesen (anonymisiert) | [Case Studies](case-studies/) | 10 Min. |
| Wissen ergänzen (Verfassen) | [CONTRIBUTING.md](CONTRIBUTING.md) | 10 Min. |

---

<details>
<summary><strong>🗺️ Navigation über zwei Achsen (zum Aufklappen klicken)</strong></summary>

### Lebenszyklus-Achse — `playbooks/`

Der Einstieg, wenn die Frage lautet: „In welcher Phase befinde ich mich gerade?"

| # | Modul | Behandelte Frage |
|---|---|---|
| 01 | [`01-assess/`](playbooks/01-assess/) | Was liegt auf dem aktuellen NAS, und was schränkt die Migration ein |
| 02 | [`02-design/`](playbooks/02-design/) | Welche Konfiguration, Kapazität, Durchsatz und Schutzmethode gewählt werden |
| 03 | [`03-migrate/`](playbooks/03-migrate/) | Welche Methode, wie umgeschaltet und wie zurückgerollt wird |
| 04 | [`04-build/`](playbooks/04-build/) | Wie IaC, Automatisierung und reproduzierbare Builds aufgebaut werden |
| 05 | [`05-operate/`](playbooks/05-operate/) | Wie Monitoring, Kapazität, Incident Response und Change Management laufen |
| 06 | [`06-optimize/`](playbooks/06-optimize/) | Wie weit Performance und Kosten optimiert werden |

### Themen-Achse — `domains/`

Der Einstieg, wenn die Frage lautet: „Ich muss dieses konkrete Thema recherchieren." Wird über alle Lebenszyklusphasen hinweg referenziert.

| Modul | Behandelte Frage |
|---|---|
| [`data-protection/`](domains/data-protection/) | Snapshot / SnapMirror / SnapLock / Backup und Ransomware-Vorsorge |
| [`data-utilization/`](domains/data-utilization/) | Analytik, KI/RAG, Zugriff über die S3-API |
| [`security-governance/`](domains/security-governance/) | Verschlüsselung, Audit, Berechtigungsdesign, Umgang mit regulierten Workloads |
| [`performance/`](domains/performance/) | Durchsatzdesign, Latenz, Caching, geteilte Bandbreite |
| [`cost/`](domains/cost/) | Kapazität, Tiering und die Lücke zwischen Schätzung und Messung |
| [`multiprotocol-identity/`](domains/multiprotocol-identity/) | NFS- / SMB-Koexistenz, Active-Directory-Integration, ID-Mapping |

### Übergreifende Referenz — `reference/`

| Verzeichnis | Inhalt |
|---|---|
| [`decision-trees/`](reference/decision-trees/) | Auswahl-Flussdiagramme (Migrationsmethode, Schutzmethode, Protokoll) |
| [`comparison/`](reference/comparison/) | Vergleichsmatrizen (Abwägungen symmetrisch dargestellt) |
| [`limits/`](reference/limits/) | Grenzwerte und Quotas mit Quelle und Prüfdatum |
| [`glossary/`](reference/glossary/) | ONTAP- und AWS-Terminologie |

</details>

<details>
<summary><strong>📁 Gemeinsame Modulstruktur (wie erweitert wird)</strong></summary>

Jedes Modul unter `playbooks/` und `domains/` hat die **gleiche innere Struktur**. Zum Anlegen eines neuen Moduls `_template/` kopieren.

```text
<module>/
├── README.md          # Modul-Hub (JA)
├── README.en.md       # Modul-Hub (EN)
├── notes/             # Kleinste Wissenseinheit. 1 Datei = 1 Thema
│   └── <slug>.md      # YAML-Frontmatter erforderlich
└── checklists/        # Checklisten für den Feldeinsatz
    └── <slug>.md
```

Jede Datei unter `notes/` trägt ihre Metadaten im YAML-Frontmatter, damit KI-Agenten und Web-Crawler sie als Struktur und nicht als Prosa auswerten können.

```yaml
---
title: Eingrenzung bei zu niedrigem Durchsatz während der SnapMirror-Erstsynchronisation
lifecycle: [migrate]          # Tag auf der playbooks-Achse
domains: [performance]        # Tag auf der domains-Achse
evidence: verified            # verified | documented | field-observation | hypothesis
verified_on: 2026-08-06       # Pflicht bei evidence: verified
ontap_version: 9.17.1P7D1     # Version zum Prüfzeitpunkt (sofern relevant)
region: ap-northeast-1        # Prüfregion (sofern relevant)
lang: de
---
```

Die vier `evidence`-Stufen erlauben es Lesern zu beurteilen, wie weit eine Notiz belastbar ist. Siehe [Evidenz-Richtlinie](docs/en/evidence-policy.md).

</details>

<details>
<summary><strong>📚 Umgang mit Fallbeispielen (Anonymisierungsrichtlinie)</strong></summary>

`case-studies/` enthält Erkenntnisse aus der technischen Unterstützung im Feld, aber **keinerlei nicht öffentliche Informationen**.

| Nicht enthalten | Stattdessen geschrieben |
|---|---|
| Firmen-, Organisations- oder Abteilungsnamen | Branche und Größenordnung (z. B. Fertigung / mehrere hundert TB) |
| Echte Hostnamen, IPs, Konto-IDs | Platzhalter (`10.0.x.x`, `123456789012`) |
| Architekturdiagramme im Original | Konfiguration so weit abstrahiert, wie es die Aussage erfordert |
| Personen- oder Prüfernamen | Rollenbezogene Angaben (z. B. „aus Sicht des Storage-Betriebs") |
| Support-Fallnummern, interne Ticket-IDs | „Beim Hersteller bestätigt (in Nachverfolgung)" |

Fallbeispiele werden als **verallgemeinerte Lehren** verfasst: was das Problem war, wie entschieden wurde, was dabei herauskam. Die Vorlage liegt in [`case-studies/_template/`](case-studies/_template/). Die Prüfungen vor Veröffentlichung sind über `make audit` automatisiert.

</details>

<details>
<summary><strong>🌐 Lokalisierungsrichtlinie (8 Sprachen)</strong></summary>

Um Übersetzungsaufwand und Aktualität in Balance zu halten, ist der Inhalt in **drei Stufen** geteilt.

| Stufe | Umfang | Sprachen |
|---|---|---|
| Tier 1 | Wurzel-`README`, Hauptleitfäden unter `docs/<lang>/` | Alle 8 Sprachen |
| Tier 2 | `README` je Modul | 日本語 + English |
| Tier 3 | Einzelne Dateien unter `notes/`, `checklists/` | 日本語 (English optional) |

Unterstützt: 日本語 / English / 한국어 / 简体中文 / 繁體中文 / Français / Deutsch / Español

Für Tier 1 prüft die CI, dass **Abschnittsstruktur und -anzahl über die Sprachen hinweg übereinstimmen** (`make i18n-check`). Nie übersetzt: Dateipfade, Befehle, Badge-URLs, Anker-IDs sowie Produkt- und Fachbegriffe (ONTAP, SnapMirror, FlexCache, SnapLock, S3 Access Point und ähnliche).

</details>

<details>
<summary><strong>🤖 Für KI-Agenten und Crawler</strong></summary>

Dieses Repository setzt menschliche und maschinelle Leser gleichermaßen voraus.

| Datei | Zweck |
|---|---|
| [`llms.txt`](llms.txt) | Repository-Karte für LLMs (Konvention nach [llmstxt.org](https://llmstxt.org/)) |
| [`AGENTS.md`](AGENTS.md) | Konventionen, Verbote und Prüfschritte für Coding-Agenten |
| Frontmatter in `notes/*.md` | Maschinenlesbare Metadaten (Lebenszyklus / Thema / Evidenzstufe / Prüfdatum) |
| [`reference/limits/`](reference/limits/) | Grenzwerte strukturiert mit Quelle und Prüfdatum |

**Hinweis für alle, die dieses Material zitieren**: Notizen mit `evidence: hypothesis` oder `field-observation` sind keine verifizierten Fakten. Prüfen Sie stets das Feld `evidence` im Frontmatter.

</details>

<details>
<summary><strong>🔧 Mitwirken und lokale Prüfung</strong></summary>

```bash
make help          # Verfügbare Targets auflisten
make lint          # Markdown-Lint + Validierung des Frontmatter-Schemas
make i18n-check    # Paritätsprüfung über Sprachen für Tier 1
make audit         # Prüfungen vor Veröffentlichung (Benennung / Neutralität / personenbezogene Daten / interne IDs)
make links         # Prüfung auf defekte Links
make all           # Alles Vorgenannte
```

Issues und Pull Requests sind willkommen. Konventionen zum Verfassen in [CONTRIBUTING.md](CONTRIBUTING.md), Einstufungskriterien in der [Evidenz-Richtlinie](docs/en/evidence-policy.md).

</details>

---

## Verwandte Repositories

| Repository | Inhalt |
|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | Über 45 Serverless-Verarbeitungsmuster über S3 Access Points |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | Observability-Integrationen (Metriken, Alarme, automatisierte Reaktion) |
| [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) | Lakehouse-Integrationen (Databricks / Snowflake / Athena / Glue / EMR) |
| [vmware-migration-ec2-ontap](https://github.com/Yoshiki0705/vmware-migration-ec2-ontap) | Migration VMware → EC2 + FSx for ONTAP |

---

## Haftungsausschluss

Dieses Repository enthält persönliches technisches Material und gibt nicht die offizielle Position eines Arbeitgebers wieder.
Aussagen zu Governance oder regulierten Workloads sind **allgemeine Designüberlegungen**, keine rechtliche oder Compliance-Beurteilung. Benchmark-Werte sind Messungen aus der angegebenen Prüfumgebung; sie garantieren weder allgemeine Servicegrenzen noch eine Reproduktion in Produktionsumgebungen.

## Lizenz

MIT — [LICENSE](LICENSE)

---

🌐 [日本語](README.md) | [English](README.en.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Español](README.es.md)
