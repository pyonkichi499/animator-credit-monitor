# Firestore Design Decisions and Implementation Status

This document records the decisions currently implemented by the Firestore backend and explicitly lists missing features.

## 1. Delivery Guarantee

- Selected: `at-least-once`
- Prefer avoiding missed notifications.
- Duplicate delivery may occur.
- Exactly-once delivery is not guaranteed.

`events.dedupeKey` is stored, but it is not currently used to query existing events or enforce uniqueness.

## 2. Snapshot Updates

### Firestore

- Diff found: update the snapshot after the `events + deliveries` batch succeeds.
- No diff: save the fetched result unless this is a dry run.
- Empty fetch: preserve the snapshot.
- Notification failure: keep the advanced snapshot and retry the delivery in the next run.

### Local

- Update the history JSON only after notification success.
- On notification failure, keep the old history and detect the same diff again next time.

## 3. Partial Failure

- Run status: `partial_failure`
- Continue processing where possible.
- CLI / GitHub Actions: non-zero exit.
- Retry failed deliveries in the next run.

## 4. Retry / Redelivery

- In-run retry: enabled
- Default retries: 2 (3 attempts total)
- Initial delay: 60 seconds
- Backoff multiplier: 2
- Cross-run redelivery: enabled
- Redelivery query limit per run: 100

Not implemented:

- stopping after `maxAttempts`
- dead-letter collection
- manual redelivery CLI

## 5. Collections

### `snapshots`

- Full fetched result per monitored target
- No TTL
- Stores `lastSnapshotHash`, but diff calculation does not use it

### `runs`

- Start/end, status, summary, and errors
- `running` / `success` / `partial_failure` / `failed`
- Intended for a 30-day TTL through `expiresAt`

### `events`

- Detected diff and notification payload
- `pending` / `sent` / `partially_sent` / `failed`
- Intended for a 30-day TTL

### `deliveries`

- Per-channel delivery state
- Current channels: `console` / `email`
- `pending` / `failed` / `sent`
- Intended for a 30-day TTL

## 6. Runtime

- Current runtime: GitHub Actions
- Authentication: GitHub OIDC + WIF
- State: Firestore
- Notification: console / SMTP email
- Credentials: GitHub Actions Secrets
- Non-sensitive settings: GitHub Actions Variables

## 7. Concurrency

- No run-level locking is implemented.
- Scheduled and manual runs may overlap.
- Concurrent runs may create duplicate events for the same diff.

## 8. Retention

- `snapshots`: indefinite
- `runs`: 30 days
- `events`: 30 days
- `deliveries`: 30 days

Deletion depends on Firestore TTL policies rather than application-side cleanup.

## 9. Future Candidates

- concurrent-run locking
- enforcing `maxAttempts`
- dead-letter / operational redelivery
- Slack / Discord / generic webhook
- Secret Manager
- Cloud Run Job
- BigQuery / dashboard

None of these are currently implemented.
