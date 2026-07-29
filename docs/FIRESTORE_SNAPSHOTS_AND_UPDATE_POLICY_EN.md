# Firestore `snapshots` Update Policy

## Responsibility

`snapshots` stores the previous result for each monitored target and acts as the baseline for the next diff.

It does not own:

- notification success/failure
- redelivery state
- per-notifier delivery results

Those belong to `events` and `deliveries`.

## Document Granularity

- `snapshots/bangumi_{person_id}`
- `snapshots/anilist_{target_name}`

Stored fields:

- `sourceType`, `sourceKey`, `targetLabel`
- `lastSnapshot`
- `lastSnapshotHash`
- `lastCheckedAt`, `updatedAt`

`lastSnapshotHash` is retained for audit/future optimization. Current diff detection does not use it.

## Current Update Conditions

### No Diff

Unless this is a dry run, save the fetched result and update the checked time.

### Diff Found

1. Persist `events` and `deliveries` in a Firestore batch.
2. Advance the snapshot after the batch succeeds.
3. Send the deliveries.

A notification failure does not roll back the snapshot. The failed delivery is retried in the next run.

### Empty Fetch

The code cannot distinguish a failed fetch from a genuinely empty result, so it preserves the snapshot.

### Dry Run

The newly fetched result does not update the snapshot. Existing delivery redelivery at run start is a separate operation and still runs.

## Partial Failure Example

With `NOTIFIERS=console,email`, when console succeeds and email fails:

- create one event
- create console and email deliveries
- update the snapshot
- console delivery becomes `sent`
- email delivery becomes `failed`
- event becomes `partially_sent`
- run becomes `partial_failure`, and the CLI exits non-zero
- retry the failed email delivery in the next run

## Difference from the Local Backend

The local backend has no Outbox. A notification failure prevents the history JSON from advancing, so the same diff is detected again on the next run.

## Duplicates

Firestore events store a `dedupeKey`, but the current implementation does not query existing events or enforce uniqueness. The Outbox and snapshot update prevent normal re-detection, but concurrent runs can still create duplicate events or notifications.
