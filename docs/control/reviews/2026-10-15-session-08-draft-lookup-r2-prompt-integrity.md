# Session 08 Prompt Integrity Review — draft lookup r2

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Remediate the draft re-read. Do not activate Session 08. No live HTTP.

The prompt file is not amended. This record is the corrective addendum for the r2 slice.

## Review

**Fidelity:** CONDITIONAL APPROVE. The fixture client still adopts one exact marker line and posts only when lookup misses. r1 compared the re-read by `count` alone.

**Safety:** An equal-count delete and insert can hide the marker on a page already read, and the client then posts a second draft. That is the high finding amended below.

**Gameability:** `True == 1` and `1.0 == 1`. A count check that is not `type(count) is int` posts. A duplicate check that is absent posts when both walks return the same repeated id.

## Addendum

1. Walk every page, then walk every page again. Compare the sorted listing ids and the adopted id. Any difference raises `count` and does not post.
2. On both walks, `results` is a list, `count` is an exact int and not a bool, every `listing_id` is an exact int and not a bool, and no id appears twice.
3. `True`, `1.0`, `"1"`, and `None` as the re-read count each raise `malformed` and do not post.
4. A transport error or a missing `results` on the second walk raises and does not post.
5. Pending is still written only after both walks, and only when the marker is absent.
6. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD.
