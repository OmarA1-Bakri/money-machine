# SESSION 14 — PRODUCTION PACKAGING AND DEPLOYMENT

Execute under the Master Control Prompt and recovery protocol.

## Objective

Package and deploy the complete system to the selected existing environment without introducing unnecessary cloud infrastructure or recurring spend.

## Actions

### 1. Select the deployment target from evidence

Inspect available machines and existing infrastructure.

Prefer:

1. an existing suitable VPS or always-on machine already owned by Omar;
2. the current Windows/WSL2 machine for local commissioning;
3. a new paid environment only if Omar has explicitly approved it.

Do not create unapproved spend.

Record the selected target and rationale in `docs/architecture/DEPLOYMENT.md`.

### 2. Finalise production containers

Build production images for:

- API;
- worker;
- scheduler;
- web.

Use one Python image where sensible.

Configure:

- non-root runtime where practical;
- health checks;
- restart policy;
- persistent PostgreSQL volume;
- artifact storage;
- runtime browser profiles;
- environment/secrets;
- log rotation;
- browser dependencies;
- resource limits appropriate to the host.

### 3. Reverse proxy and access

Use Caddy or the existing reverse proxy.

Support:

- HTTPS where a domain is available;
- local/private access where no domain is configured;
- operator-console authentication;
- API protection;
- health endpoints.

Do not delay local commissioning for a public domain.

### 4. Database and release process

Implement:

- migration on deployment;
- seed/upgrade idempotency;
- release version;
- rollback to prior container image;
- database backup before migration;
- compatibility checks.

### 5. Backup and restore automation

Provide PowerShell and Bash commands for:

- database backup;
- artifact backup;
- restore;
- verification;
- retention cleanup.

Schedule backups in production.

### 6. Runtime service management

Support:

- start;
- stop;
- restart;
- status;
- logs;
- worker scale within host limits;
- scheduler singleton;
- migration;
- safe update.

### 7. Deploy

Deploy the latest exact commit.

Prove:

- all services healthy;
- database migrated;
- seed present;
- operator console accessible;
- worker leasing;
- scheduler tick;
- fixture/simulation workflow;
- PostHog event path where configured;
- restart after host/service reboot.

### 8. CI release path

Complete a private-repo release workflow that:

- runs tests;
- builds images;
- records commit/image tags;
- deploys through the selected mechanism or produces an exact deploy command;
- never exposes secrets.

### 9. Runbooks

Complete:

```text
LOCAL_DEVELOPMENT.md
ACCOUNT_CONNECTIONS.md
LIVE_COMMISSIONING.md
INCIDENTS.md
BACKUP_RESTORE.md
PROVIDER_RECOVERY.md
```

Keep them operational and concise.

### 10. Review and checkpoint

Use DevOps and operational-recovery reviewers. Fix defects.

Commit:

```text
feat(deploy): package and deploy production runtime
```

Tag a pre-commissioning release:

```text
v0.1.0-rc1
```

## Exit criteria

- Production stack is deployed on the selected environment.
- Services survive restart.
- Backups run and restore has evidence.
- Operator console is accessible.
- Simulation workflow passes in the deployed runtime.
- Release and rollback paths exist.
- Control files and commit are current.

## Required exit code

```text
SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE
```

Next prompt:

```text
18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md
```
