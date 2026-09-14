# svc-alpha Disaster Recovery Runbook

## Overview
svc-alpha is the customer-facing reporting API. Primary region eu-west-1,
secondary eu-north-1.

## Recovery Objectives
- **RTO:** 15 minutes from declared incident to restored primary traffic.
- **RPO:** 5 minutes (async replication lag budget).

## Failover Procedure
1. On-call declares incident in #svc-alpha-incidents.
2. Run `./scripts/failover.sh eu-north-1`.
3. Confirm DNS cutover via `dig api.svc-alpha.internal`.
4. Run smoke test suite (`make smoke-test`).
5. Announce failover complete in incident channel.

## Rollback
If issues are found after failover, engineering should try to move traffic
back to the primary region. Coordinate with the platform team before doing
this. There isn't a scripted path yet for this service — it was on the
Q3 backlog but got deprioritized. Ask in #platform-oncall if this comes up.

## Notes
- Last runbook review: 2025-01-10
- Owner: reporting-team
