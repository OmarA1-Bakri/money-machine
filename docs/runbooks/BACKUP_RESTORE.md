# Backup Restore

The Session 13 fixture copies one workflow, job, product, draft listing, and incident in memory. A second restore does not insert those rows again. A live PostgreSQL backup is refused.

Exit 78 is held. This runbook does not open a database connection and does not record a credential.
