# Amazon FSx for NetApp ONTAP — Adoption Playbook

## Público

- Arquitectos que deciden si adoptar FSx for ONTAP y cómo configurarlo
- Responsables de implementación que planifican migración, construcción y paso a producción
- Responsables de operación que gestionan rendimiento, protección, seguridad y costes después del lanzamiento

## Fuera de alcance

Este repositorio no sustituye:

- La elaboración o negociación de contratos
- La interpretación de licencias
- Las cotizaciones de precios o estimaciones formales
- Los procedimientos de migración desde servicios SaaS de intercambio de archivos
- Las decisiones de adopción o compra específicas de un entorno
- Las decisiones finales legales, regulatorias o de cumplimiento

Siguen dentro del alcance los datos para decidir basados en fuentes públicas, así como las observaciones de implementación y las perspectivas de diseño claramente separadas de los hechos documentados.

## Estado de las traducciones

![docs](https://img.shields.io/badge/docs-lint%20passing-brightgreen) ![i18n](https://img.shields.io/badge/i18n-Tier%201%3A%208%20languages-blue) ![license](https://img.shields.io/badge/license-MIT-blue) ![region](https://img.shields.io/badge/verified-ap--northeast--1-blue)

La orientación inicial Tier 1 está disponible en ocho idiomas. Los hubs de módulos Tier 2 están disponibles en japonés y English. El cuerpo de `notes/` y `checklists/` está principalmente en japonés, con traducciones seleccionadas al English. La versión japonesa es la referencia para la exactitud técnica.

## Comprobaciones antes de producción

- [Revisión antes de producción](../ja/playbooks/04-build/checklists/pre-production-review.md) (日本語) — ajustes irreversibles y pruebas que deben ejecutarse antes del lanzamiento
- [El cifrado en reposo es automático; en tránsito está desactivado por defecto](../ja/domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md) (日本語) — límites de responsabilidad del cifrado en tránsito y la auditoría

## Empezar

| Lo que quieres hacer | Guía | Tiempo |
|---|---|---|
| Decidir si FSx for ONTAP encaja con la carga | [Elegir almacenamiento de archivos de AWS](../ja/reference/decision-trees/file-storage-selection.md) (日本語) | 10 min |
| Entender cómo recorrer este repositorio | [Guía de navegación](navigation.md) | 3 min |
| Entender los niveles de evidencia | [Política de niveles de evidencia](evidence-policy.md) | 5 min |

<details>
<summary><strong>Más puntos de entrada</strong></summary>

| Situación | Punto de entrada |
|---|---|
| Elegir un método de migración | [Árbol de decisión de migración](../ja/reference/decision-trees/migration-method.md) (日本語) |
| Consultar límites y cuotas | [Límites y cuotas](../ja/reference/limits/) |
| Comparar compensaciones | [Matrices de comparación](../ja/reference/comparison/) (日本語) |
| Partir de un sector o carga | [Mapa de recursos por sector](../ja/reference/industry-resource-map.md#業種から入ったときの読む順序) (日本語) |
| Contribuir conocimiento | [CONTRIBUTING.md](../../CONTRIBUTING.md) |

</details>

> El árbol de decisión de almacenamiento permite parar cuando FSx for ONTAP no encaja.
> Cada README de módulo enumera sus preguntas y documentos asociados; una respuesta ausente se marca `_未追加_`.

<details>
<summary><strong>Rutas por síntoma y contenido disponible</strong></summary>

### Entrar desde un síntoma

**Para cuando el punto de partida es lo que ocurre y no lo que se quiere hacer.** Consulta el [índice de árboles de decisión](../ja/reference/decision-trees/) (日本語) y el [índice de comparaciones](../ja/reference/comparison/) (日本語).

| Lo que ocurre | A dónde ir |
|---|---|
| **La factura supera lo previsto** | [cost-higher-than-expected.md](../ja/reference/decision-trees/cost-higher-than-expected.md) (日本語) — Primera bifurcación: facturado por lo aprovisionado o por lo consumido |
| **El rendimiento no llega** | [measured-throughput-triage.md](../ja/reference/decision-trees/measured-throughput-triage.md) (日本語) — Cuál de los cuatro techos se alcanzó |
| **Hace falta un cambio y el orden no está claro** | [what-to-change-and-in-what-order.md](../ja/reference/decision-trees/what-to-change-and-in-what-order.md) (日本語) — Por reversibilidad, no por efecto esperado |
| **La plantilla tuvo éxito y la configuración sigue incompleta** | [where-a-setting-is-created.md](../ja/reference/decision-trees/where-a-setting-is-created.md) (日本語) — Lo que crea la API de AWS y lo que solo existe en el lado ONTAP |
| **Una solicitud por un punto de acceso S3 es rechazada** | [access-point-authorization.md](../ja/reference/decision-trees/access-point-authorization.md) (日本語) — Del síntoma a la capa que rechazó |
| **Demasiadas formas de restringir el acceso** | [access-restriction-options.md](../ja/reference/comparison/access-restriction-options.md) (日本語) — No están en una sola capa |
| **Un valor de inventario no sirve para decidir** | [inventory-sources.md](../ja/reference/comparison/inventory-sources.md) (日本語) — Una lista hecha desde la configuración no coincide con la realidad |
| **Sin decisión sobre cómo alcanzar la configuración de ONTAP** | [ontap-configuration-routes.md](../ja/reference/comparison/ontap-configuration-routes.md) (日本語) — Toda ruta sale de la gestión por plantilla |

---

### Disponible hoy

Cada documento trata un solo asunto por archivo y lleva siempre **sus fuentes primarias** y **un procedimiento para comprobarlo en tu propio entorno**.
El cuerpo del texto está por ahora en japonés. La lista completa está en el README de cada módulo, junto a las preguntas correspondientes — [ciclo de vida](../ja/playbooks/) / [temas](../ja/domains/) / [referencia](../ja/reference/).

</details>

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
| [`observability/`](../en/domains/observability/) | Elección de la vía de monitorización, Harvest / Prometheus, residencia de los datos |
| [`client-access/`](../en/domains/client-access/) | Acceso desde un equipo Windows, WSL2 o Mac: vía de acceso, montaje, credenciales en el equipo |

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

**Este repositorio trata las decisiones. Las implementaciones y las mediciones están en los repositorios de abajo.** El mismo dato en dos sitios queda obsoleto en uno de ellos.

**A dónde ir después depende de lo que ya se haya decidido.**

| Decidido aquí | Ir a | Qué contiene |
|---|---|---|
| **La fuente de verdad es Amazon S3 y el uso es principalmente de lectura** | [S3-Burst-on-ONTAP-Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | Un árbol de decisión sobre adoptar esta arquitectura y **las mediciones de los protocolos de archivos** |
| **Exponer los datos por un punto de acceso S3 y procesarlos sin servidores** | [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | Implementaciones de patrones de procesamiento y patrones de operación del sistema de archivos |
| **Alimentar una canalización de IA o RAG respetando los permisos originales** | [FSx-for-ONTAP-Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | Una implementación sobre Amazon Bedrock y AWS CDK. **Los permisos se reconstruyen en un índice aparte y se evalúan en la recuperación** |
| **Agregar datos dispersos de edge o IoT antes de analizarlos** | [ONTAP-Edge-to-Cloud-AI](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI) | Agregación en ONTAP y luego Bedrock / Athena / SageMaker por puntos de acceso S3. **Solo las diferencias propias de IoT; la elección de la capa de almacenamiento viene de aquí** |
| **En qué capa está la defensa frente a ransomware** | [FSx-for-ONTAP-Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | ONTAP ARP, respuesta por eventos con FPolicy e integraciones de terceros |
| **La ruta de supervisión ya está elegida** | [FSx-for-ONTAP-Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | Métricas, alertas y respuesta automatizada |
| **Llevar los datos a una plataforma analítica** | [FSx-for-ONTAP-Lakehouse-Integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Integraciones con Databricks / Snowflake / Athena / Glue / EMR |
| **Migrar desde VMware** | [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) | Migración a Amazon EC2 con FSx for ONTAP |

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
