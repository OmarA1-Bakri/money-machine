# Artifact Lineage

**Contract status:** Session 01 immutable lineage design; persistence and storage implementations follow in later sessions.

## Lineage chain

```text
Product
→ ProductSpec version
→ producing job
→ agent run
→ agent definition and prompt version
→ source inputs and parent artifacts
→ artifact hash and storage reference
→ QA/preflight result
→ listing version
→ provider effect receipt
```

No arrow is inferred from filenames, timestamps, model prose, or telemetry. Each link is a durable typed reference.

## Artifact record

An `ArtifactReference` identifies:

- artifact UUID and schema version;
- logical role and media type;
- SHA-256 digest, byte size, and storage reference;
- producing job and agent-run UUIDs;
- creation time in UTC;
- sensitivity/retention classification.

The full artifact record additionally links template/prompt versions, source inputs, parent artifacts, render manifest, QA results, and any provider object/version created from it. Content is immutable. A changed byte sequence creates a new artifact ID/version even when its logical role is unchanged.

## Material artifact classes

| Class | Examples | Required parents | Required verification |
|---|---|---|---|
| Research evidence | admitted observation export, teardown report | source references, research/teardown run | provenance and schema validation |
| Product specification | ProductSpec version | decisions, research, teardown | contract and dedupe eligibility |
| Product build | Notion structure manifest, formulas, link set | approved ProductSpec | product QA |
| Variant | isolated variant manifest/link | QA-passed build, variant plan | equivalence, duplication, indexing, fresh-view checks |
| Listing copy | title, description, tags, price facts | verified product facts | claim and provider-constraint checks |
| Media | ten images, walkthrough video | screenshots, product facts, render manifest | deterministic render and visual/claim QA |
| Delivery | README/access and optional gift PDFs | verified links/facts | URL policy, export hash, click tests |
| Listing version | complete immutable package | copy, media, delivery, price, draft fields | preflight and provider reconciliation |
| Metrics/decision evidence | snapshot export, cohort calculation | provider observation and listing intervals | reconciliation and rule-version check |
| Repair output | replacement link/file/listing version | incident, affected artifact version | rerun of the affected QA/preflight contract |

## Production and validation flow

1. The job declares required input artifact IDs and expected output roles.
2. The agent run references exact prompt and definition versions.
3. Output bytes are produced in denied temporary storage and hashed before registration.
4. The artifact record and parent edges commit with the agent result.
5. QA references the exact artifact IDs and produces evidence references.
6. A listing version can include only artifacts whose required checks pass.
7. Provider upload/publication records the exact listing and artifact versions plus effect receipt.
8. Any replacement creates a new version and marks dependent checks stale until rerun.

## Truth and privacy boundaries

- Product claims resolve to typed `product_facts` and their evidence.
- Page, feature, media, tag, link, price, review, user, and sales claims cannot be invented by a prompt.
- The private PDF is never copied into artifact storage or redistributed.
- Credentials, cookies, customer/provider payloads, browser profiles, screenshots containing secrets, and machine-local receipts remain denied runtime data.
- Committed documentation stores only safe IDs, hashes, schemas, and copyright-safe derived mappings.

## Repair and retirement

Artifact repair never mutates a published historical version. It creates a new artifact and listing version, links the incident and superseded version, executes an idempotent provider update, reconciles the result, and reruns fresh-view/link/preflight checks. Retired content remains addressable for lineage while storage garbage collection may remove only unreferenced, policy-expired bytes.

## Consistency invariants

- Hash, byte size, and storage object agree before registration.
- Parent edges cannot form a cycle.
- A QA result cannot cover a later artifact version.
- A listing version cannot change after preflight.
- Publication and deactivation receipts reference one listing version and idempotency record.
- A `MULTIPLY` successor references the parent decision/product but owns new ProductSpec, workflow, and artifact lineage.