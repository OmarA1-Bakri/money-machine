# Source Register

Registered 2026-08-08 after adoption of the sole canonical root `/mnt/d/Money Machine` (`D:\Money Machine`). Both sources remain immutable at repository root; no private copy was required.

| Source | Type | Canonical absolute path | Bytes | SHA-256 | Modified (UTC) | Internal title / version | Completeness | Git policy |
|---|---|---|---:|---|---|---|---|---|
| Original playbook | PDF, 82 pages | `/mnt/d/Money Machine/The-Hands-Off-Money-Machine-Playbook.pdf` | 829165 | `c9cd31775d1d79be31c3a8092d8d49fc71d52e695f97cbfb580fcbb35f240fad` | 2026-08-08T04:53:32.104912Z | *The Hands-Off Money Machine Playbook*; 2026 Lewis Jackson / Agents to Income | Page extraction proves pages 1-82 are present | Strictly ignored; never redistributed |
| Implementation workbook | Markdown, 6222 lines | `/mnt/d/Money Machine/hands-off-money-machine-full-implementation-workbook.md` | 157125 | `4dbecbb8ad6fdd9fe2323eb164ffd2d7c99143cf5de20de5ec98a1bdf90d7f2b` | 2026-08-07T21:33:45.970140Z | *Hands-Off Money Machine — Full Implementation Workbook*; v1.0, 2026-08-07 | Parts I-XXI and integrity appendices present | Registered engineering source |

`CANONICAL_SOURCE_REGISTER.json` is the committed, path-relative machine-readable registration artifact. Detailed pre/post-rename observations (absolute paths, timestamps, candidate roots, and comparisons) remain runtime evidence only under ignored `.omx/`; they are not source documentation. The original source files were not moved, rewritten, or normalized.

`scripts/verify_canonical_sources.py` validates this register and the continuous 1-82 coverage map in every clone. At the canonical root it additionally reads the private PDF itself, verifies its registered digest and size, walks all 82 pages in document order, and proves every page has a nonempty text-bearing content stream without emitting source text. A clean clone may omit only the ignored PDF and must use the verifier's explicit `--allow-missing-private-pdf` mode.
