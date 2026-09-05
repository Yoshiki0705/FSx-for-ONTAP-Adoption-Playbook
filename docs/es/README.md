# Amazon FSx for NetApp ONTAP — Adoption Playbook

![docs](https://img.shields.io/badge/docs-lint%20passing-brightgreen) ![i18n](https://img.shields.io/badge/i18n-8%20languages-blue) ![license](https://img.shields.io/badge/license-MIT-blue) ![region](https://img.shields.io/badge/verified-ap--northeast--1-blue)

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](../zh-TW/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](README.md)
<!-- lang-switcher:end -->

---

> Una base de conocimiento para migrar a **Amazon FSx for NetApp ONTAP** y para el trabajo de diseño, construcción y operación que viene después.
> Dos ejes de navegación: el ciclo de vida (evaluar → diseñar → migrar → construir → operar → optimizar) y el tema (protección de datos, aprovechamiento de datos, seguridad, rendimiento, coste, identidad multiprotocolo).
>
> Los hallazgos obtenidos en el soporte técnico de campo se organizan aquí como material de referencia anonimizado. La estructura está pensada para que la lean tanto personas como agentes de IA y rastreadores web.

---

## Empezar

| Lo que quieres hacer | Guía | Tiempo |
|---|---|---|
| Entender cómo recorrer este repositorio | [Guía de navegación](navigation.md) | 3 min |
| Decidir si migrar y cómo hacerlo | [Árbol de decisión: método de migración](../ja/reference/decision-trees/migration-method.md) | 10 min |
| Consultar los límites verificados | [Límites y cuotas](../ja/reference/limits/) | 5 min |
| Entender cómo leer los niveles de confianza | [Política de niveles de evidencia](evidence-policy.md) | 5 min |
| Encontrar fuentes primarias públicas | [Fuentes públicas y cómo ponderarlas](../ja/case-studies/public-references.md) (日本語) | 5 min |
| Añadir conocimiento (redacción) | [CONTRIBUTING.md](../../CONTRIBUTING.md) | 10 min |

> **Estado de la cobertura**: **los 12 módulos tienen contenido.**
> El README de cada módulo enumera las preguntas y el documento correspondiente;
> una pregunta sin respuesta escrita se marca con `_未追加_`. Las notas están por ahora en japonés.

### Disponible hoy

Cada documento trata un solo asunto por archivo y lleva siempre **sus fuentes primarias** y **un procedimiento para comprobarlo en tu propio entorno**.
El cuerpo del texto está por ahora en japonés. La lista completa está en el README de cada módulo, junto a las preguntas correspondientes — [ciclo de vida](../ja/playbooks/) / [temas](../ja/domains/) / [referencia](../ja/reference/).

---

<details>
<summary><strong>🗺️ Navegación en dos ejes (clic para desplegar)</strong></summary>

### Eje de ciclo de vida — `playbooks/`

La entrada cuando la pregunta es «¿en qué fase estoy ahora mismo?».

| # | Módulo | Pregunta que aborda |
|---|---|---|
| 01 | [`01-assess/`](../en/playbooks/01-assess/) | Qué hay en el NAS actual y qué va a limitar la migración |
| 02 | [`02-design/`](../en/playbooks/02-design/) | Qué configuración, capacidad, rendimiento y método de protección elegir |
| 03 | [`03-migrate/`](../en/playbooks/03-migrate/) | Qué método usar, cómo conmutar y cómo revertir |
| 04 | [`04-build/`](../en/playbooks/04-build/) | Cómo estructurar IaC, automatización y compilaciones reproducibles |
| 05 | [`05-operate/`](../en/playbooks/05-operate/) | Cómo llevar monitorización, capacidad, respuesta a incidentes y gestión del cambio |
| 06 | [`06-optimize/`](../en/playbooks/06-optimize/) | Hasta dónde ajustar rendimiento y coste |

### Eje temático — `domains/`

La entrada cuando la pregunta es «necesito investigar este asunto concreto». Se referencia en todas las fases del ciclo de vida.

| Módulo | Pregunta que aborda |
|---|---|
| [`data-protection/`](../en/domains/data-protection/) | Snapshot / SnapMirror / SnapLock / copias de seguridad y preparación frente a ransomware |
| [`data-utilization/`](../en/domains/data-utilization/) | Analítica, IA/RAG y acceso mediante la API de S3 |
| [`security-governance/`](../en/domains/security-governance/) | Cifrado, auditoría, diseño de permisos y enfoque de cargas reguladas |
| [`performance/`](../en/domains/performance/) | Diseño de rendimiento, latencia, caché, ancho de banda compartido |
| [`cost/`](../en/domains/cost/) | Capacidad, tiering y la diferencia entre estimaciones y mediciones |
| [`multiprotocol-identity/`](../en/domains/multiprotocol-identity/) | Coexistencia NFS / SMB, integración con Active Directory, mapeo de identidades |
| [`block-storage/`](../en/domains/block-storage/) | iSCSI / NVMe-oF, disposición de LUN, multipathing, cómputo de la capacidad |

### Referencia transversal — `reference/`

| Directorio | Contenido |
|---|---|
| [`decision-trees/`](../ja/reference/decision-trees/) | Diagramas de decisión (método de migración, protección, protocolo) |
| [`comparison/`](../ja/reference/comparison/) | Matrices de comparación (compensaciones expuestas de forma simétrica) |
| [`limits/`](../ja/reference/limits/) | Límites y cuotas, con fuente y fecha de verificación |
| [`glossary/`](../ja/reference/glossary/) | Terminología de ONTAP y AWS |

### Impartición de talleres — `workshop-studio/`

| Directorio | Contenido |
|---|---|
| [`workshop-studio/`](../ja/workshop-studio/) | Tiempos medidos y selección de módulos para ajustar un taller público de AWS Workshop Studio al tiempo real del evento (日本語) |

</details>

<details>
<summary><strong>📁 Estructura común de los módulos (cómo ampliar)</strong></summary>

Cada módulo bajo `playbooks/` y `domains/` tiene la **misma estructura interna**. Para añadir un módulo, copia `_template/`.

```text
docs/<lang>/{playbooks,domains}/<module>/
├── README.md          # Hub del módulo
├── notes/             # Unidad mínima de conocimiento. 1 archivo = 1 asunto
│   └── <slug>.md      # Frontmatter YAML obligatorio
└── checklists/        # Listas de comprobación para campo
    └── <slug>.md
```

Cada archivo de `notes/` lleva sus metadatos en un frontmatter YAML, para que los agentes de IA y los rastreadores web puedan interpretarlo como estructura y no como prosa.

```yaml
---
title: Diagnóstico de rendimiento insuficiente en la sincronización inicial de SnapMirror
lifecycle: [migrate]          # Etiqueta del eje playbooks
domains: [performance]        # Etiqueta del eje domains
evidence: verified            # verified | documented | field-observation | hypothesis
verified_on: 2026-08-06       # Obligatorio si evidence: verified
ontap_version: 9.17.1P7D1     # Versión en el momento de la verificación (si aplica)
region: ap-northeast-1        # Región de verificación (si aplica)
lang: es
---
```

Los cuatro niveles de `evidence` permiten al lector juzgar hasta qué punto puede apoyarse en una nota. Consulta la [política de niveles de evidencia](evidence-policy.md).

</details>

<details>
<summary><strong>📚 Tratamiento de los casos (política de anonimización)</strong></summary>

`case-studies/` recoge hallazgos del soporte técnico de campo, pero **no contiene ninguna información no pública**.

| No se incluye | Se escribe en su lugar |
|---|---|
| Nombres de empresa, organización o departamento | Sector y orden de magnitud (p. ej. manufactura / varios cientos de TB) |
| Nombres de host, IP o ID de cuenta reales | Marcadores (`10.0.x.x`, `123456789012`) |
| Diagramas de arquitectura tal cual | Configuración abstraída al nivel que exige el argumento |
| Nombres de personas o revisores | Referencias por rol (p. ej. «desde la perspectiva de la operación de almacenamiento») |
| Números de caso de soporte, ID de tickets internos | «Confirmado con el proveedor (en seguimiento)» |

Los casos se redactan como **lecciones generalizadas**: cuál era el problema, cómo se decidió y cuál fue el resultado. La plantilla está en [`case-studies/_template/`](../ja/case-studies/_template/). Las comprobaciones previas a la publicación están automatizadas con `make audit`.

</details>

<details>
<summary><strong>🌐 Política de localización (8 idiomas)</strong></summary>

Para equilibrar el coste de traducción con la vigencia del contenido, este se divide en **tres niveles**.

| Nivel | Alcance | Idiomas |
|---|---|---|
| Tier 1 | `README` raíz, guías principales bajo `docs/<lang>/` | Los 8 idiomas |
| Tier 2 | `README` de cada módulo | 日本語 + English |
| Tier 3 | Archivos individuales de `notes/`, `checklists/` | 日本語 (English opcional) |

Idiomas admitidos: 日本語 / English / 한국어 / 简体中文 / 繁體中文 / Français / Deutsch / Español

En el Tier 1, la CI verifica que **la estructura y el número de secciones coincidan entre idiomas** (`make i18n-check`). Nunca se traducen: rutas de archivo, comandos, URL de badges, ID de anclas ni nombres de producto y términos técnicos (ONTAP, SnapMirror, FlexCache, SnapLock, S3 Access Point y similares).

</details>

<details>
<summary><strong>🤖 Para agentes de IA y rastreadores</strong></summary>

Este repositorio asume lectores humanos y lectores máquina por igual.

| Archivo | Propósito |
|---|---|
| [`llms.txt`](../../llms.txt) | Mapa del repositorio para LLM (convención de [llmstxt.org](https://llmstxt.org/)) |
| [`AGENTS.md`](../../AGENTS.md) | Convenciones, prohibiciones y pasos de verificación para agentes de código |
| Frontmatter en `notes/*.md` | Metadatos legibles por máquina (ciclo de vida / tema / nivel de evidencia / fecha de verificación) |
| [`reference/limits/`](../ja/reference/limits/) | Límites estructurados con fuente y fecha de verificación |

**Aviso para quien cite este material**: las notas marcadas como `evidence: hypothesis` o `field-observation` no son hechos verificados. Comprueba siempre el campo `evidence` del frontmatter.

</details>

<details>
<summary><strong>🔧 Contribuir y verificación local</strong></summary>

```bash
make help          # Listar los targets disponibles
make lint          # Lint de Markdown + validación del esquema de frontmatter
make i18n-check    # Comprobación de paridad entre idiomas para el Tier 1
make audit         # Comprobaciones previas a la publicación (nomenclatura / neutralidad / datos personales / ID internos)
make links         # Comprobación de enlaces roscos
make all           # Todo lo anterior
```

Se agradecen Issues y Pull Requests. Consulta [CONTRIBUTING.md](../../CONTRIBUTING.md) para las convenciones de redacción y la [política de niveles de evidencia](evidence-policy.md) para los criterios de clasificación.

</details>

---

## Repositorios relacionados

| Repositorio | Contenido |
|---|---|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | Más de 45 patrones de procesamiento serverless sobre S3 Access Points |
| [FSx-for-ONTAP-Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | Integraciones de observabilidad (métricas, alertas, respuesta automatizada) |
| [FSx-for-ONTAP-Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Integraciones Lakehouse (Databricks / Snowflake / Athena / Glue / EMR) |
| [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) | Migración VMware → EC2 + FSx for ONTAP |

---

## Descargo de responsabilidad

Este repositorio es material técnico personal y no representa la posición oficial de ningún empleador.
Las afirmaciones sobre gobernanza o cargas reguladas son **consideraciones generales de diseño**, no juicios legales ni de cumplimiento. Las cifras de referencia son mediciones del entorno de verificación indicado; no garantizan los límites generales del servicio ni su reproducción en producción.

La versión en japonés de este repositorio es la de referencia en cuanto a exactitud técnica. Los demás idiomas son traducciones asistidas por máquina que no han sido revisadas por hablantes nativos antes de su publicación; en caso de discrepancia, prevalece la versión en japonés. Las correcciones son bienvenidas mediante una [Issue](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues).

## Licencia

MIT — [LICENSE](../../LICENSE)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../README.md) | [English](../en/README.md) | [한국어](../ko/README.md) | [简体中文](../zh-CN/README.md) | [繁體中文](../zh-TW/README.md) | [Français](../fr/README.md) | [Deutsch](../de/README.md) | [Español](README.md)
<!-- lang-switcher:end -->
