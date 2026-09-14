# svc-gamma Disaster Recovery Runbook

## Overview
svc-gamma is the legacy notifications dispatcher, scheduled for
decommission in favor of svc-notify-v2. Primary region ap-southeast-1,
secondary ap-northeast-1.

## Recovery Objectives
TBD — pending sign-off from the platform team. See JIRA-8821.

## Failover Procedure
1. Page on-call.
2. Manually repoint DNS via the AWS console (no script exists yet).
3. Cross fingers.

## Rollback
No rollback procedure has been written for this service.

## Notes
- Last runbook review: 2024-05-02
- Owner: unassigned (legacy team disbanded)
