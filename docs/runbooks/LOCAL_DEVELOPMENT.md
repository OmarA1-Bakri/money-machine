# Local Development

Local development uses the same five services as `compose.prod.yaml`: postgres, api, web, worker, and scheduler. The postgres service keeps the `postgres-data` volume and a healthcheck. The api service keeps its healthcheck.

Worker and scheduler stay uncommissioned. Exit 78 is held, and their restart policy stays `no`. Starting a container is not a commissioned process. This runbook does not record a credential.
