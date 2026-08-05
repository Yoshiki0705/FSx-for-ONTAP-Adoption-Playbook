# Security Policy

## Scope

This repository contains **documentation only**. There is no application, no deployed
infrastructure, and no runtime that could be exploited. The security concerns that do apply are:

1. **Accidental disclosure** — non-public information committed by mistake
2. **Supply chain** — the GitHub Actions workflows and the standard-library tooling in `tools/`
3. **Misleading guidance** — documentation that would lead a reader to build something insecure

## Reporting

| Concern | How to report |
|---|---|
| Disclosure of non-public information (company name, real identifier, personal data) | Open a **private security advisory** via the repository's Security tab. Do not open a public issue — that would amplify the exposure |
| Guidance that would lead to an insecure configuration | Open a normal public issue; discussing it openly helps other readers |
| Vulnerability in a workflow or in `tools/` | Private security advisory |

For accidental disclosure, please include the file path and line. Do **not** quote the sensitive
value itself in the report.

## Response

Disclosure reports are treated as the highest priority. The offending content is removed from the
default branch first, then history rewriting is assessed separately — note that git history is
cached by the host and may persist even after a force-push, so removal from `main` is a mitigation
rather than a guarantee.

## Preventive controls

| Control | What it covers |
|---|---|
| `make audit` | Naming, vendor-neutrality, personal data, internal identifiers, role-labeled callouts |
| `gitleaks` (CI, plus weekly schedule) | Credential patterns, including ones committed before the rule existed |
| `.gitignore` | `.private/`, `.kiro/`, key material, `.env` files <!-- gitleaks:allow --> |
| `case-studies/README.md` | Anonymization table applied before any case study is written |
| Human review | Whether "someone who knows this environment would recognize it" — automated checks cannot judge this |

Contributors: read the "書いてはいけないもの" section of [CONTRIBUTING.md](CONTRIBUTING.md) before
your first commit.

## Placeholders

Documentation deliberately shows the shape of identifiers. These are the sanctioned placeholders;
anything else is treated as a real value by the audit.

| Kind | Placeholder |
|---|---|
| AWS account ID | `123456789012` |
| File system ID | `fs-0123456789abcdef0` <!-- gitleaks:allow --> |
| VPC / subnet / security group | `vpc-0123456789abcdef0`, `subnet-…`, `sg-…` <!-- gitleaks:allow --> |
| Internal IP | `10.0.x.x` or `<management-ip>` |
| Secret ARN suffix | `-XXXXXX` |
| Email | `user@example.com` |
| Local path | `${PROJECT_DIR}` or a relative path |
