# Session 08 Prompt Integrity Review — previous xref

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Refuse a PDF trailer that names `/Prev`. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 6 reads embedded links from the PDF the renderer wrote. `PdfDocument` keeps the xref at `startxref` and does not read `/Prev`. An incremental section can hold an object the newest table does not name. The walk then never sees it.

Open pulls #63, #68, #78, #79, #80, #81, #82, and #83 stay untouched. This slice edits `pdf_reader.py` and a new unit test.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — One xref is not the whole file**

- **Prompt lines:** 127–136. Link checks apply to the PDF that will ship.
- **Authority:** The reader already walks every object the newest xref names, including objects nothing else references.
- **Consequence of literal execution:** A `/Prev` generation is ignored, so an object that lives only there is not checked.
- **Amendment:** A trailer that contains `Prev` raises `pdf prev` before the cache is filled. The reader does not follow the offset.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Following `/Prev` would parse attacker-chosen bytes**

- **Prompt lines:** 127–136.
- **Amendment:** Refuse the key. Do not seek to the previous offset and do not merge tables.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — A normal trailer hides the missing check**

- **Cheap fake:** Delete the `Prev` refusal. Every fixture PDF without that key still parses.
- **Amendment:** One crafted trailer with `/Prev 0` fails `test_a_previous_xref_is_refused`. A trailer without `Prev` still parses.

## 3. Corrective addendum

1. Prove the prompt hash, then raise `ValueError("pdf prev")` when the trailer contains `Prev`.
2. Do not follow the offset. A trailer without `Prev` still parses.
3. Do not edit `IMPLEMENTATION_STATE.json`, `.github/workflows/ci.yml`, or the files of open pulls #63, #68, #78, #79, #80, #81, #82, and #83. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code. No live HTTP.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| `file:` allow, sendBeacon, raster text | Operator park | The screenshot route and capture policy stay as they are |
| Uppercase hosts, spelled-email gaps, further host defangs | Open pulls #79, #81, #82 | Those files are owned |
| Live S3, live Etsy, publish | Operator hold | Live provider transport |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. The `/Prev` refusal may start. The prompt file stays unamended.
