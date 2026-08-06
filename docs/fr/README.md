# Amazon FSx for NetApp ONTAP — Adoption Playbook

![docs](https://img.shields.io/badge/docs-lint%20passing-brightgreen) ![i18n](https://img.shields.io/badge/i18n-8%20languages-blue) ![license](https://img.shields.io/badge/license-MIT-blue) ![region](https://img.shields.io/badge/verified-ap--northeast--1-blue)

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](../zh-TW/README.md) | [Français](README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->

---

> Une base de connaissances pour migrer vers **Amazon FSx for NetApp ONTAP**, puis pour les travaux de conception, de construction et d'exploitation qui suivent.
> Deux axes de navigation : le cycle de vie (évaluer → concevoir → migrer → construire → exploiter → optimiser) et le thème (protection des données, exploitation des données, sécurité, performance, coût, identité multiprotocole).
>
> Les constats issus du support technique sur le terrain sont organisés ici sous forme de matériel de référence anonymisé. La structure est pensée pour être lisible par des humains comme par des agents d'IA et des robots d'indexation.

---

## Démarrer

| Ce que vous voulez faire | Guide | Durée |
|---|---|---|
| Comprendre comment parcourir ce dépôt | [Guide de navigation](navigation.md) | 3 min |
| Décider s'il faut migrer, et comment | [Arbre de décision : méthode de migration](../ja/reference/decision-trees/migration-method.md) | 10 min |
| Consulter les limites vérifiées | [Limites et quotas](../ja/reference/limits/) | 5 min |
| Comprendre comment lire les niveaux de confiance | [Politique de niveaux de preuve](evidence-policy.md) | 5 min |
| Trouver les sources primaires publiques | [Sources publiques et comment les pondérer](../ja/case-studies/public-references.md) (日本語) | 5 min |
| Ajouter des connaissances (rédaction) | [CONTRIBUTING.md](../../CONTRIBUTING.md) | 10 min |

> **État de la couverture** : **les 12 modules ont tous du contenu.**
> Le README de chaque module liste les questions qu'il traite et le document correspondant ;
> une question sans réponse écrite est marquée `_未追加_`. Les notes sont pour l'instant en japonais.

### Disponible aujourd'hui

Chaque document traite un seul sujet par fichier et porte toujours **ses sources primaires** ainsi qu'**une procédure de vérification dans votre propre environnement**.
Le corps du texte est pour l'instant en japonais. La liste complète figure dans le README de chaque module, en regard des questions correspondantes — [cycle de vie](../ja/playbooks/) / [thèmes](../ja/domains/) / [référence](../ja/reference/).

---

<details>
<summary><strong>🗺️ Navigation à deux axes (cliquer pour déplier)</strong></summary>

### Axe cycle de vie — `playbooks/`

L'entrée à privilégier quand la question est « à quelle phase en suis-je ? ».

| # | Module | Question traitée |
|---|---|---|
| 01 | [`01-assess/`](../en/playbooks/01-assess/) | Ce qui existe sur le NAS actuel, et ce qui contraindra la migration |
| 02 | [`02-design/`](../en/playbooks/02-design/) | Quelle configuration, capacité, débit et méthode de protection retenir |
| 03 | [`03-migrate/`](../en/playbooks/03-migrate/) | Quelle méthode employer, comment basculer, comment revenir en arrière |
| 04 | [`04-build/`](../en/playbooks/04-build/) | Comment structurer l'IaC, l'automatisation et des builds reproductibles |
| 05 | [`05-operate/`](../en/playbooks/05-operate/) | Comment mener supervision, capacité, réponse aux incidents et gestion du changement |
| 06 | [`06-optimize/`](../en/playbooks/06-optimize/) | Jusqu'où pousser l'optimisation de la performance et du coût |

### Axe thématique — `domains/`

L'entrée à privilégier quand la question est « je dois creuser ce sujet précis ». Référencé à toutes les phases du cycle de vie.

| Module | Question traitée |
|---|---|
| [`data-protection/`](../en/domains/data-protection/) | Snapshot / SnapMirror / SnapLock / sauvegarde et préparation aux rançongiciels |
| [`data-utilization/`](../en/domains/data-utilization/) | Analytique, IA/RAG, accès via l'API S3 |
| [`security-governance/`](../en/domains/security-governance/) | Chiffrement, audit, conception des droits, approche des charges réglementées |
| [`performance/`](../en/domains/performance/) | Dimensionnement du débit, latence, cache, bande passante partagée |
| [`cost/`](../en/domains/cost/) | Capacité, tiering, et l'écart entre estimations et mesures |
| [`multiprotocol-identity/`](../en/domains/multiprotocol-identity/) | Coexistence NFS / SMB, intégration Active Directory, mappage d'identités |

### Référence transversale — `reference/`

| Répertoire | Contenu |
|---|---|
| [`decision-trees/`](../ja/reference/decision-trees/) | Organigrammes de choix (méthode de migration, protection, protocole) |
| [`comparison/`](../ja/reference/comparison/) | Matrices de comparaison (compromis énoncés de façon symétrique) |
| [`limits/`](../ja/reference/limits/) | Limites et quotas, avec source et date de vérification |
| [`glossary/`](../ja/reference/glossary/) | Terminologie ONTAP et AWS |

</details>

<details>
<summary><strong>📁 Structure commune des modules (comment étendre)</strong></summary>

Chaque module sous `playbooks/` et `domains/` possède la **même structure interne**. Pour ajouter un module, copiez `_template/`.

```text
docs/<lang>/{playbooks,domains}/<module>/
├── README.md          # Hub du module
├── notes/             # Plus petite unité de connaissance. 1 fichier = 1 sujet
│   └── <slug>.md      # Frontmatter YAML obligatoire
└── checklists/        # Listes de contrôle pour le terrain
    └── <slug>.md
```

Chaque fichier de `notes/` porte ses métadonnées dans un frontmatter YAML, afin que les agents d'IA et les robots d'indexation puissent l'interpréter comme une structure et non comme de la prose.

```yaml
---
title: Diagnostiquer un débit insuffisant lors de la synchronisation initiale SnapMirror
lifecycle: [migrate]          # Étiquette sur l'axe playbooks
domains: [performance]        # Étiquette sur l'axe domains
evidence: verified            # verified | documented | field-observation | hypothesis
verified_on: 2026-08-06       # Obligatoire si evidence: verified
ontap_version: 9.17.1P7D1     # Version lors de la vérification (le cas échéant)
region: ap-northeast-1        # Région de vérification (le cas échéant)
lang: fr
---
```

Les quatre niveaux d'`evidence` permettent au lecteur de juger jusqu'où une note peut être utilisée. Voir la [politique de niveaux de preuve](evidence-policy.md).

</details>

<details>
<summary><strong>📚 Traitement des cas d'usage (politique d'anonymisation)</strong></summary>

`case-studies/` contient des constats issus du support technique sur le terrain, mais **aucune information non publique, sans exception**.

| Non inclus | Écrit à la place |
|---|---|
| Noms d'entreprise, d'organisation, de service | Secteur et ordre de grandeur (ex. industrie manufacturière / plusieurs centaines de To) |
| Noms d'hôtes, IP, identifiants de compte réels | Valeurs fictives (`10.0.x.x`, `123456789012`) |
| Schémas d'architecture tels quels | Configuration abstraite au niveau que le propos exige |
| Noms de personnes ou de relecteurs | Références par rôle (ex. « du point de vue de l'exploitation du stockage ») |
| Numéros de dossier de support, identifiants de tickets internes | « Confirmé auprès de l'éditeur (suivi en cours) » |

Les cas d'usage sont rédigés comme des **enseignements généralisés** : quel était le problème, comment la décision a été prise, quel a été le résultat. Le modèle se trouve dans [`case-studies/_template/`](../ja/case-studies/_template/). Les contrôles avant publication sont automatisés par `make audit`.

</details>

<details>
<summary><strong>🌐 Politique de localisation (8 langues)</strong></summary>

Pour concilier coût de traduction et fraîcheur du contenu, celui-ci est réparti en **trois niveaux**.

| Niveau | Périmètre | Langues |
|---|---|---|
| Tier 1 | `README` racine, guides principaux sous `docs/<lang>/` | Les 8 langues |
| Tier 2 | `README` de chaque module | 日本語 + English |
| Tier 3 | Fichiers de `notes/`, `checklists/` | 日本語 (English facultatif) |

Langues prises en charge : 日本語 / English / 한국어 / 简体中文 / 繁體中文 / Français / Deutsch / Español

Pour le Tier 1, la CI vérifie que **la structure et le nombre de sections concordent entre les langues** (`make i18n-check`). Jamais traduits : chemins de fichiers, commandes, URL de badges, identifiants d'ancres, noms de produits et termes techniques (ONTAP, SnapMirror, FlexCache, SnapLock, S3 Access Point, etc.).

</details>

<details>
<summary><strong>🤖 Pour les agents d'IA et les robots d'indexation</strong></summary>

Ce dépôt suppose des lecteurs humains autant que des lecteurs machines.

| Fichier | Rôle |
|---|---|
| [`llms.txt`](../../llms.txt) | Carte du dépôt destinée aux LLM (convention [llmstxt.org](https://llmstxt.org/)) |
| [`AGENTS.md`](../../AGENTS.md) | Conventions, interdits et étapes de vérification pour les agents de codage |
| Frontmatter des `notes/*.md` | Métadonnées lisibles par machine (cycle de vie / thème / niveau de preuve / date de vérification) |
| [`reference/limits/`](../ja/reference/limits/) | Limites structurées avec source et date de vérification |

**Avertissement pour toute citation** : les notes marquées `evidence: hypothesis` ou `field-observation` ne sont pas des faits vérifiés. Vérifiez toujours le champ `evidence` du frontmatter.

</details>

<details>
<summary><strong>🔧 Contribution et vérification locale</strong></summary>

```bash
make help          # Lister les cibles disponibles
make lint          # Lint Markdown + validation du schéma de frontmatter
make i18n-check    # Contrôle de parité entre langues pour le Tier 1
make audit         # Contrôles avant publication (nommage / neutralité / données personnelles / identifiants internes)
make links         # Contrôle des liens rompus
make all           # Tout ce qui précède
```

Les Issues et Pull Requests sont bienvenues. Voir [CONTRIBUTING.md](../../CONTRIBUTING.md) pour les conventions de rédaction et la [politique de niveaux de preuve](evidence-policy.md) pour les critères de classement.

</details>

---

## Dépôts liés

| Dépôt | Contenu |
|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | Plus de 45 modèles de traitement serverless via S3 Access Points |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | Intégrations d'observabilité (métriques, alertes, réponse automatisée) |
| [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations) | Intégrations Lakehouse (Databricks / Snowflake / Athena / Glue / EMR) |
| [vmware-migration-ec2-ontap](https://github.com/Yoshiki0705/vmware-migration-ec2-ontap) | Migration VMware → EC2 + FSx for ONTAP |

---

## Avertissement

Ce dépôt rassemble du matériel technique personnel et ne représente pas la position officielle d'un employeur.
Les propos relatifs à la gouvernance ou aux charges réglementées sont des **considérations de conception d'ordre général**, non des avis juridiques ou de conformité. Les valeurs de référence sont des mesures issues de l'environnement de vérification indiqué ; elles ne garantissent ni les limites générales du service ni une reproduction en production.

La version japonaise de ce dépôt fait référence pour l'exactitude technique. Les autres langues sont des traductions assistées par machine qui n'ont pas été relues par des locuteurs natifs avant publication ; en cas de divergence, la version japonaise prévaut. Les corrections sont bienvenues via une [Issue](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues).

## Licence

MIT — [LICENSE](../../LICENSE)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](../zh-TW/README.md) | [Français](README.md) | [Deutsch](../de/README.md) | [Español](../es/README.md)
<!-- lang-switcher:end -->
