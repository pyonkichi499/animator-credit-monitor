# Firestore Runtime Design

## Scope

- State backend: `STATE_BACKEND=firestore`
- Primary runtime: GitHub Actions
- Authentication: Application Default Credentials; GitHub Actions uses OIDC + WIF
- Delivery guarantee: `at-least-once`

## Collections

With `FIRESTORE_COLLECTION_PREFIX=dev`, the names below become `dev_snapshots`, and so on.

### `snapshots`

Diff-comparison baseline. No TTL.

Document IDs:

- `bangumi_{person_id}`
- `anilist_{target_name}`

Fields:

- `sourceType`
- `sourceKey`
- `targetLabel`
- `lastSnapshot`
- `lastSnapshotHash`
- `lastCheckedAt`
- `updatedAt`

`lastSnapshotHash` is stored, but current diff detection compares JSON-serialized items.

### `runs`

Execution audit. Intended for a 30-day TTL through `expiresAt`.

Fields:

- `startedAt`, `finishedAt`
- `status`: `running` / `success` / `partial_failure` / `failed`
- `runtime`: the current CLI sets `github_actions`
- `triggerType`: `manual` / `schedule`
- `dryRun`
- `summary`
- `errors`
- `expiresAt`

The use case attempts to finalize an unexpected exception as `failed` in a `finally` block.

### `events`

Outbox parent containing a detected diff. Intended for a 30-day TTL.

Fields:

- `runId`
- `sourceKey`, `sourceType`
- `eventType`: `new_credits_detected`
- `payload`: `title`, `message`, `diffItems`, `diffCount`
- `diffCount`
- `status`: `pending` / `sent` / `partially_sent` / `failed`
- `dedupeKey`
- `createdAt`, `updatedAt`, `expiresAt`

`dedupeKey` is a SHA-256 of the source key and diff. It is currently stored only; no uniqueness check or existing-event lookup uses it.

### `deliveries`

Per-notifier delivery state. Intended for a 30-day TTL.

Fields:

- `eventId`, `runId`
- `channel`: `console` / `email`
- `destinationKey`
- `status`: `pending` / `failed` / `sent`
- `attemptCount`
- `maxAttempts`: currently stored as `50` but not enforced
- `nextRetryAt`
- `lastErrorMessage`
- `sentAt` after success
- `createdAt`, `updatedAt`, `expiresAt`

## Execution Flow

1. Create a `runs` document as `running`.
2. Fetch and retry up to 100 existing retryable deliveries.
3. Fetch each source.
4. Skip an empty fetch and preserve the snapshot.
5. Compare the fetched items with the snapshot.
6. With no diff, save the snapshot and update the checked time unless this is a dry run.
7. With a diff and not a dry run:
   1. Save the event and deliveries in a Firestore batch.
   2. Advance the snapshot after the batch succeeds.
   3. Send the new deliveries immediately.
   4. Aggregate event status from delivery status.
8. Finalize the run as `success`, `partial_failure`, or `failed`.

## Retry

### In-Run

- Attempts: `NOTIFY_RETRY_MAX_RETRIES + 1`
- Default: initial attempt plus two retries
- Delay: 60 seconds, then 120 seconds (2x multiplier)

### Cross-Run

- Target: `pending` / `failed` with `nextRetryAt <= now`
- Up to 100 deliveries per run
- Increment `attemptCount` once after a failed dispatch
- Calculate `nextRetryAt` with exponential backoff based on persisted `attemptCount`

There is currently no `maxAttempts` stop condition or dead-letter collection. A failed delivery may remain retryable until TTL deletion.

## `--dry-run`

A Firestore dry run still:

- creates and finalizes a `runs` document
- processes **existing redeliveries at run start**, potentially updating delivery/event state
- does not create/update snapshots, events, or deliveries for the newly detected diff
- sends a newly detected diff directly without the Outbox

Therefore, `--dry-run` means "do not persist the newly fetched monitoring state"; it does not make all Firestore activity read-only.

## Status / Exit Code

- `success`: no delivery failures
- `partial_failure`: a new delivery or redelivery failed
- `failed`: unexpected exception

The CLI exits non-zero for errors including `partial_failure`. Firestore state remains available for the next run's redelivery.

## TTL Types

`expiresAt`, the Firestore TTL field, is stored as a timezone-aware `datetime`. Most other timestamp fields are ISO 8601 strings.
