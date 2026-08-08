# RECOVERY AND CONTINUATION PROMPT

```text
[@Remote Desktop Commander]
[@superpowers]
[@Composio]
[@posthog]
[@product-design]
```

Recover and continue the existing Hands-Off Money Machine implementation.

Do not restart the programme.

## Recovery procedure

1. Search for the canonical repository, preferring:
   - `D:\hands-off-money-machine`;
   - `/mnt/d/hands-off-money-machine`;
   - any path recorded in `IMPLEMENTATION_STATE.json`.
2. Read:
   - `AGENTS.md`;
   - `docs/control/IMPLEMENTATION_STATE.json`;
   - `docs/control/NEXT_SESSION.md`;
   - the latest entries in `IMPLEMENTATION_LOG.md`;
   - `DECISIONS.md`;
   - `TEST_EVIDENCE.md`.
3. Inspect:
   - git remote;
   - current branch;
   - exact HEAD;
   - git status;
   - recent commits;
   - running containers/services;
   - failing tests;
   - incomplete migrations;
   - leased/running/stalled jobs.
4. Compare the requested session prompt with `current_session`, `completed_sessions` and repository evidence.
5. Resume the first incomplete action in the requested session.
6. Preserve all completed work, decisions, fixtures, receipts, failures and user changes.
7. Do not ask Omar to repeat context already in the repository.
8. Do not create a second repo, second workflow engine or new architecture.
9. Run a focused verification of prior-session foundations before modifying them.
10. Continue until the requested session's exit criteria are met.

## State conflict handling

If control files disagree with code or git:

- current code, migrations, tests, git history and runtime evidence take precedence;
- repair the control files;
- record the contradiction;
- continue from the real state.

If a previous assistant claimed completion without evidence:

- mark the session incomplete;
- complete it now;
- do not restart earlier completed work.

## Response

Return only the requested session's completion format and next prompt after updating control files and committing.
