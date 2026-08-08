# Hands-Off Money Machine — ChatGPT Full Implementation Prompt Pack

## Purpose

This prompt pack instructs ChatGPT to build the complete autonomous system described by *The Hands-Off Money Machine Playbook*.

The playbook is accepted as the authoritative business-process specification. This implementation programme does **not** pause for additional commercial proof, replace the business model, or insert a conservative approval process. Its job is to convert the manual playbook into a durable, linked, fully automated operating system.

The implementation is divided into bounded sessions so ChatGPT can complete the work reliably without losing state between chats.

## Target repository

- **Repository name:** `hands-off-money-machine`
- **Default Windows path:** `D:\hands-off-money-machine`
- **Default WSL2 path:** `/mnt/d/hands-off-money-machine`
- **Remote:** private GitHub repository where authenticated access exists
- **Architecture:** one private modular-monolith monorepo, not one repository per agent

The repository path is a default. Session 00 must first search for an existing implementation and reuse it if one already exists.

## Required tools

Open every implementation chat with the available tools enabled:

```text
[@Remote Desktop Commander]
[@superpowers]
[@Composio]
[@posthog]
[@product-design]
```

Use GitHub access or the authenticated `gh` CLI where available.

## How to run the programme

### First chat

Paste, in this order:

1. `01_MASTER_CONTROL_PROMPT.md`
2. `03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md`

Attach or make available:

- `The-Hands-Off-Money-Machine-Playbook.pdf`
- this prompt pack

Do not paste every session prompt at once.

### Every later chat

Paste, in this order:

1. `01_MASTER_CONTROL_PROMPT.md`
2. `19_RECOVERY_AND_CONTINUATION_PROMPT.md`
3. the next numbered session prompt

The agent must read the repository's control files and current git state before continuing. It must not restart completed work.

### When a session hits the context limit

Open a new chat and paste:

1. `01_MASTER_CONTROL_PROMPT.md`
2. `19_RECOVERY_AND_CONTINUATION_PROMPT.md`
3. the same session prompt

The recovery prompt instructs ChatGPT to resume the unfinished session from repository evidence.

## Session sequence

| Session | Objective |
|---:|---|
| 00 | Discover existing work, create or adopt the repository, ingest the playbook and establish checkpoints |
| 01 | Convert the playbook into canonical architecture, contracts, state machine and agent roster |
| 02 | Build the engineering foundation, database, migrations, API skeleton, CI and local runtime |
| 03 | Build the durable orchestrator, job queue, scheduler, dependencies, retries and recovery |
| 04 | Build the agent runtime, prompt registry, structured contracts and complete roster registration |
| 05 | Implement research → shortlist → Low-Ticket scoring → teardown → product spec → dedupe |
| 06 | Implement the Notion integration foundation and browser/API action layer |
| 07 | Implement full Notion product builds, colour variants, publishing and product QA |
| 08 | Implement listing copy, imagery, video and delivery-PDF asset generation |
| 09 | Implement Etsy draft, preflight, publication, ramp control and post-publish verification |
| 10 | Implement weekly metrics, 30-day maturity, culling, multiplication and automatic successor work |
| 11 | Implement customer-support, broken-link and product-repair workflows |
| 12 | Build the operator console and PostHog operational telemetry |
| 13 | Run complete E2E, restart, duplicate-effect, failure-injection and hardening work |
| 14 | Package and deploy the production system on the selected existing environment |
| 15 | Connect live accounts, commission full autonomy and complete final handover |

## Operating principle

The implementation must preserve the playbook's loop:

```text
Research → build → list → measure → cull → multiply
```

The key engineering requirement is that each completed job automatically creates or unlocks the next job. Omar must not copy outputs between agents or remember when to restart the workflow.

## Expected completion signal

The final session may only exit with:

```text
HANDS_OFF_MONEY_MACHINE_COMMISSIONED
```

That code is valid only after the full linked system, runtime, tests, deployment and live-account commissioning are complete or every remaining blocker is an exact external credential/account action outside ChatGPT's control.
