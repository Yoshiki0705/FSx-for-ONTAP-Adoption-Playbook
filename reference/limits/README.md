# 上限値・クォータ / Limits and Quotas

[🏠 リポジトリトップ](../../README.md) | [Reference](../README.md)

---

## 記載ルール / Recording rules

各値には **出典** と **検証日** を付けます。ドキュメント記載値と実測値が異なる場合は
**両方**を残します。片方だけを書くと、読者はどちらの前提で設計すべきか判断できません。

Every value carries a **source** and a **verification date**. Where the documented value and the
measured value differ, keep **both** — recording only one leaves readers unable to tell which
premise to design against.

| 列 / Column | 内容 / Contents |
|---|---|
| 項目 / Item | 何の上限か / What the limit applies to |
| 値 / Value | 単位を明示。GB と GiB を区別する / State the unit explicitly; distinguish GB from GiB |
| 出典 / Source | ドキュメント URL、または「実測」/ Documentation URL, or "measured" |
| 検証日 / Verified | `YYYY-MM-DD` |
| 備考 / Notes | 検証環境、エラーの出方、回避策 / Environment, how the error surfaces, workaround |

---

## FSx for ONTAP S3 AP — オブジェクトサイズ / Object size

姉妹リポジトリで実測された値です。詳細は
[S3 AP object size limit verification](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/s3ap-object-size-limits-verification.md)
を参照してください。

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| 単一 `PutObject` | 5 GiB (5,368,709,120 B) | 実測 | 2026-08-02 | `Content-Length` で即時拒否。400 `EntityTooLarge` + `MaxSizeAllowed` |
| `UploadPart` 1 パート | 5 GiB | 実測 | 2026-08-02 | 同上 |
| オブジェクト全体 | 50 GiB (53,687,091,200 B) | 実測 | 2026-08-02 | **`CompleteMultipartUpload` でのみ検査**。全ペイロード転送後に判明する |

> **設計上の注意**: オブジェクト全体の上限は転送完了後にしか検査されません。`UploadPart` に
> 累積チェックはなく、`Complete` のエラーには `MaxSizeAllowed` が含まれません。
> **クライアント側で事前にサイズ検証してください。**
>
> **Design note**: The whole-object limit is checked only after the full payload has transferred.
> `UploadPart` has no cumulative check, and the `Complete` error omits `MaxSizeAllowed`.
> **Validate object size client-side before uploading.**

> **単位の注意**: ドキュメントは "5 GB" / "50 GB" と記載していますが、実測値はいずれも **binary
> (GiB)** です。
>
> **Unit note**: Documentation says "5 GB" / "50 GB", but both measured values are **binary (GiB)**.

検証環境 / Environment: `ap-northeast-1`

---

## 追加テンプレート / Template for new entries

```markdown
## <対象 / Subject>

| 項目 | 値 | 出典 | 検証日 | 備考 |
|---|---|---|---|---|
| TODO | TODO | TODO | YYYY-MM-DD | TODO |

検証環境 / Environment: TODO
```

---

## 関連ドキュメント / Related documents

- [知見の分類ポリシー](../../docs/ja/evidence-policy.md) / [Evidence Policy](../../docs/en/evidence-policy.md)
- [Playbook 02 — 設計](../../playbooks/02-design/) / [Design](../../playbooks/02-design/README.en.md)

---

[🏠 リポジトリトップ](../../README.md) | [Reference](../README.md)
