# svc-beta Disaster Recovery Runbook

## Overview
svc-beta is the internal billing ledger service. Primary region us-east-1,
secondary us-west-2.

## Recovery Objectives
- **RTO:** 10 minutes from declared incident to restored primary traffic.
- **RPO:** 2 minutes.

## Failover Procedure
1. On-call declares incident in #svc-beta-incidents.
2. Run `./scripts/failover.sh us-west-2`.
3. Confirm DNS cutover via `dig api.svc-beta.internal`.
4. Run smoke test suite (`make smoke-test`).
5. Announce failover complete in incident channel.

## Rollback
1. Verify ledger write queue is drained on the promoted replica.
2. Run `./scripts/rollback.sh us-east-1` to repoint DNS and demote us-west-2
   back to replica.
3. Run reconciliation job (`make reconcile-ledger`) to confirm no writes
   were lost during the window.
4. Announce rollback complete in incident channel.

## Notes
- Last runbook review: 2026-03-01
- Owner: billing-team
