# 0005 Artifact Lineage

**Status:** Accepted

## Context

Product claims, listing media, delivery files, template links, and decisions must be reproducible and truthful. Generated files without provenance cannot prove what was built, tested, or published.

## Decision

Represent every material output as an immutable artifact version. An artifact records content hash, media type, logical role, storage reference, byte size, producing job, agent run, prompt version, schema version, source artifact/input references, creation time, and sensitivity class. Provider objects also retain provider ID and reconciled version metadata without storing secrets.

Lineage must connect:

`Product → ProductSpec version → producing job → agent run → prompt version → source inputs → artifact hash → QA result → listing version`.

Artifact links form a directed acyclic graph. Derived artifacts reference all material parents. QA and preflight results reference the exact artifact versions checked. A listing version references the exact copy, media, delivery files, price decision, and product facts sent to a provider. Replacing an artifact creates a new version and invalidates or reruns dependent checks; it never mutates historical evidence.

Hashes are computed from bytes before storage. Evidence references identify a durable record and optional digest, not unstructured claims. Runtime receipts and customer/provider payloads remain in denied runtime storage; committed documentation contains no sensitive evidence.

## Rationale

Immutable lineage supports reproducibility, claim verification, incident repair, deduplication, and audit without treating logs or model prose as truth.

## Consequences

- Storage garbage collection must retain every version referenced by a non-retired lineage.
- Publishing and repair operate on explicit listing/artifact versions.
- Duplicate bytes may share storage while retaining distinct logical references.
- QA becomes stale when any checked dependency changes.
- Operators can trace a provider listing back to exact inputs and decisions.

## Rejected alternatives

- **Mutable latest-file paths:** destroy historical truth and repair evidence.
- **Database rows without content hashes:** cannot prove byte identity.
- **Logs as lineage:** logs are incomplete, mutable operational observations.
- **Embedding files in events:** bloats workflow records and complicates retention.
- **Storing only provider URLs:** external content can change independently.

## Revisit when

Revisit storage layout or hash algorithm when scale, retention, or interoperability requires it. Preserve immutable versions, parent references, exact QA/listing linkage, and migration-verifiable digests.