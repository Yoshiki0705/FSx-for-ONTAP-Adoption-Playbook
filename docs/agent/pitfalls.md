# Common pitfalls

> Extracted from `AGENTS.md` so it is not loaded on every turn. Read this when a gate fails and the cause is not obvious, or before finalizing a change.
>
> `AGENTS.md` remains authoritative on any disagreement.

| Pitfall | Solution |
|---|---|
| `evidence: verified` without `verified_on` | `make lint` fails. Either add the date or downgrade the tier |
| A measured number with no environment stated | Always state ONTAP version, region, and configuration next to the number |
| Tier 1 doc updated in Japanese only | `make i18n-check` fails. Update every language the manifest names, in the same commit |
| Adjusting `../` counts while translating a file | The counterpart belongs at the same depth under `docs/<lang>/`. Only the language segment may differ |
| Hand-editing a switcher line, or adding a language to it manually | `make switcher-check` fails. Run `sync_lang_switcher.py --write` |
| A link that resolves but sends the reader into another language | `make links` cannot see this. `make switcher-check` can, and it runs that check unconditionally |
| Translating a note and then updating only the Japanese version later | `make i18n-check` compares every file that exists in both languages, not only Tier 1 and 2. A translation that exists has to keep up |
| Creating `docs/en/reference/` for one file | `reference/` is bilingual single files today. Follow that style or split the whole tree deliberately |
| Bare `FSx` or `FSxN` slipping into prose | `make audit` fails. Only "Amazon FSx for NetApp ONTAP" / "FSx for ONTAP" <!-- allow:naming --> |
| Suggesting BlueXP / Workload Factory / NetApp Console | Reframe to CloudWatch / ONTAP REST API / FabricPool / DataSync / Snapshot-FlexClone-SnapMirror <!-- allow:naming --> |
| **Enabling any immutability feature without an explicit instruction naming the retention value** | Stop and ask. See [Immutability (WORM) features](../../AGENTS.md#immutability-worm-features-never-enable-one-on-your-own-judgement). A 128 MiB SnapLock audit log volume locked a whole file system for six months |
| Reading the "how to enable" page but not the "how to delete" page | Reversibility is documented on the teardown page. Read the exit before the entry |
| Assuming "use the minimum retention" is protection | Find the parameter that actually binds. A volume `RetentionPeriod` of `0 YEARS` did not prevent a six-month lock set by a *different* parameter the AWS API cannot even express |
| Treating verification as a reason to skip the irreversibility gate | Use a disposable file system or account. The incident that created this rule was verification work |
| Vendor-versus phrasing in a comparison | State trade-offs symmetrically and add a "how to choose" section |
| Invented `**X Engineer lens**` callout | Relabel to a neutral topic note (`**Security note**`) |
| Case study with a recognizable configuration | Abstract to industry + scale band; drop anything identifying |
| Personal path `/Users/<name>/` in an example | Use `${PROJECT_DIR}` or a relative path |
| Dark diagram not regenerated after a light edit | Regenerate; the light/dark pair must stay in sync |
| Reading a `@2x` PNG directly | Exceeds the 2000px limit. Downscale to a preview first |
| Working past a `ruff` version mismatch | `make python` now fails instead of warning. Install the pinned version; if it still fires, a second binary is earlier on `PATH` (`which -a ruff`) |
| Citing another repo's finding without a link | Always link the source repository and doc |

## Silencing the audit

`make audit` has two escape hatches. Both are claims, not conveniences.

| Form | Scope | When it is honest |
|---|---|---|
| an HTML comment containing `allow:<category>` | the line it appears on | The match is a false positive — a proper noun, or a verbatim external title that contains a forbidden form |
| an HTML comment containing `audit-file-allow` plus a comma-separated category list | the whole file | The document *defines* the rules and therefore has to quote the patterns it forbids. `AGENTS.md` and `CONTRIBUTING.md` are the only files that qualify |

Both markers are matched anywhere on a line, HTML comment or not — so writing either token in
prose creates a real exemption. That is why the file-level one is spelled out in words here
instead of shown literally: quoting it would silence this file. Valid categories are `naming`,
`neutrality`, `pii`, `role-label`, and `all`.

Prefer the per-line form. A file-level allowance also exempts every mistake added to that
file later, which is how an exemption granted for one good reason turns into an unmonitored
file. Inside a table, the comment goes **within** the last cell — placing it after the
closing pipe adds a column and fails `markdownlint`.
