# Next Session

Session 01 is complete and **Session 02 is activated and incomplete** (state revision 16). Continue with `prompts/implementation/05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md`.

## Session 02 entry conditions

1. Start from the committed Session 01 state-pointer checkpoint. Revalidate the canonical root, immutable source hashes, branch, and control state before changing the schema or persistence design.
2. Session 02 is already activated (revision 16) with its eight evidence keys installed as false. Do not re-activate; a second activation is rejected. Later sessions must add their own contract to `SESSION_EVIDENCE_KEYS` before activating.
3. Session 01 contracts are the schema input. Implement the PostgreSQL schema against the lineage chain carried by `AgentResult`, `ArtifactReference`, `EffectReference`, and the product and listing contracts; do not redesign the taxonomies without a decision record.
4. Keep provider effects in simulation. Session 01 completion commissions no agent and authorizes no publication, purchase, spend, customer message, or provider write.
5. Carry-forward work, each recorded in `DECISIONS.md` or the review record: the durable orchestrator must call `require_successor_spawn` on the MULTIPLY spawn path (Session 03); the decision layer must refuse unreconciled `MetricsSnapshot` inputs (Session 02); launch-sale configuration belongs to merchandising (Session 08); vendor capability for every `DIRECT_API` selection is UNVERIFIED until the owning session reads and cites the vendor reference; the CodeRabbit vendor re-review of the Session 00 fixes is still rate-limited.

Session 01 evidence: the Chapter 12-16 and Prompt 1-13 maps with no ownerless job, eleven architecture documents with the six required diagrams, seven complete ADRs, the executable lifecycle and job tables with exhaustive rejection tests, the fifteen required Pydantic contracts under strict frozen versioned policy, playbook defaults bound into those contracts through configuration, an explicit capability channel for every provider operation with a test that holds the matrix to the configuration, thirteen adversarial findings plus three closure-review highs resolved, and a green Python, Compose and web gate.
