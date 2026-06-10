# Firestore Runtime Design (GitHub Actions Phase 1)

Scope:
- Runtime: GitHub Actions
- State storage: Firestore
- Authentication: GitHub OIDC + Workload Identity Federation (WIF)

Principles:
- Delivery guarantee: `at-least-once`
- Partial failures (`partial_failure`) are recorded in Firestore while GitHub Actions exits with `exit code != 0`
- `snapshots` serve as the "comparison baseline"
- `snapshots` are updated only when `events + deliveries` have been successfully persisted

---

## Collections

### `snapshots` (no TTL)

Purpose:
- Comparison baseline for diff detection (previous fetch results)

Document ID examples:
- `bangumi_12345`
- `anilist_山田太郎`

Key fields:
- `sourceType`
- `sourceKey`
- `targetLabel`
- `lastSnapshot` (array)
- `lastSnapshotHash`
- `lastCheckedAt`
- `updatedAt`

### `runs` (TTL 30 days)

Purpose:
- Execution history summary

Key fields:
- `startedAt`
- `finishedAt`
- `status` (`running` / `success` / `partial_failure`)
- `runtime` (`github_actions`)
- `triggerType` (`schedule` / `manual`)
- `dryRun`
- `summary`
- `errors`
- `expiresAt`

### `events` (TTL 30 days)

Purpose:
- Detection events (Outbox parent)

Key fields:
- `runId`
- `sourceKey`
- `sourceType`
- `eventType` (`new_credits_detected`)
- `payload` (`title`, `message`, `diffItems`, `diffCount`)
- `diffCount`
- `status` (`pending` / `partially_sent` / `sent` / `failed`)
- `dedupeKey`
- `createdAt`
- `updatedAt`
- `expiresAt`

### `deliveries` (TTL 30 days)

Purpose:
- Per-destination delivery status (retry targets)

Key fields:
- `eventId`
- `runId`
- `channel` (`email` / `line` / `console`)
- `destinationKey`
- `status` (`pending` / `failed` / `sent`)
- `attemptCount`
- `maxAttempts`
- `nextRetryAt`
- `lastErrorMessage`
- `createdAt`
- `updatedAt`
- `expiresAt`

---

## Execution Flow

1. Create a `runs` document with status `running`
2. Retry carried-over deliveries: resend `deliveries` with `pending/failed` status where `nextRetryAt <= now`
3. Fetch each source and determine diffs
4. If diffs are found, create `events + deliveries` (Outbox pattern)
5. Update `snapshots` once step 4 succeeds
6. Immediately deliver new `deliveries` (with in-run retry)
7. Aggregate-update `events.status` based on `deliveries`
8. Finalize `runs` with status `success` or `partial_failure`

---

## Retry Policy

Defaults:
- `NOTIFY_RETRY_MAX_RETRIES=2`
- `NOTIFY_RETRY_INITIAL_DELAY_SECONDS=60`

Behavior:
- In-run retry: 60s -> 120s (3 attempts total)
- On failure, `deliveries.nextRetryAt` is updated with exponential backoff and retried in the next run

---

## Exit Code Policy (GitHub Actions)

- `0`: Complete success
- `non-0`: Errors including `partial_failure`

Note:
- Even with `partial_failure`, the state is persisted in `runs.status` and `deliveries`, allowing retries in the next run
