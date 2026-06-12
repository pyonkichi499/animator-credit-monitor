# Firestore: Role and Update Timing of `snapshots`

This memo organizes the responsibilities and update conditions of `snapshots` in a Firestore-based design.

---

## 1. What is `snapshots`?

`snapshots` is a collection that stores the "previously fetched results (comparison baseline)" for each monitored target.

Purpose:
- Detect differences on the next run
- Maintain a baseline of "already seen data"

Important:
- `snapshots` is not the place to manage "notification success/failure"
- Notification state is managed by `events` / `deliveries`

---

## 2. Responsibilities of `snapshots`

Responsibilities that `snapshots` owns:
- Storing previously fetched data (baseline)
- Serving as the comparison source for diff detection
- Recording the last check timestamp

Responsibilities that `snapshots` does NOT own:
- Success/failure of notification delivery
- Retry management
- Delivery state per notifier

---

## 3. Document Granularity (Firestore)

- 1 monitored target = 1 document
- Examples:
  - `snapshots/bangumi_12345`
  - `snapshots/anilist_山田太郎`

---

## 4. Recommended Document Structure (Example)

```json
{
  "sourceType": "anilist",
  "sourceKey": "anilist_山田太郎",
  "targetLabel": "山田太郎",
  "lastSnapshot": [
    {
      "id": "123",
      "title": "作品A",
      "role": "原画",
      "date": "2026-02"
    },
    {
      "id": "456",
      "title": "作品B",
      "role": "作画監督",
      "date": "2026-01"
    }
  ],
  "lastSnapshotHash": "sha256:...",
  "lastCheckedAt": "2026-02-23T00:00:00Z",
  "updatedAt": "2026-02-23T00:00:01Z"
}
```

Field descriptions:
- `sourceType`: `bangumi` / `anilist`
- `sourceKey`: Unique key (e.g., `bangumi_12345`)
- `targetLabel`: Human-readable display name (optional)
- `lastSnapshot`: Previously fetched list (the core data for diff comparison)
- `lastSnapshotHash`: Hash (optional, for optimization)
- `lastCheckedAt`: Timestamp of the last successful fetch
- `updatedAt`: Timestamp of the last document update

---

## 5. Options for Update Timing

### A. Update `snapshots` only on notification success

Meaning:
- Data for which notifications have not been sent is treated as "not yet seen"

Advantages:
- Intuitive as a philosophy for preventing missed notifications

Disadvantages (significant when using Outbox/retry):
- `snapshots` does not advance if some notification targets fail
- The same diff is likely to be re-detected on the next run
- Duplicate `events` tend to accumulate (duplicate events)

Suitable cases:
- Not using Outbox
- Re-detection is sufficient as a retry mechanism

---

### B. Update `snapshots` when `events + deliveries` are successfully persisted (Recommended)

Meaning:
- Once the diff has been "saved as a retryable event," it is considered not missed

Advantages:
- `snapshots` can advance as a comparison baseline
- Notification failures can be handled via `deliveries` retries
- The same diff is unlikely to be re-detected on the next run
- Clear separation of responsibilities between `snapshots` (comparison baseline) and `deliveries` (delivery state)

Disadvantages:
- `snapshots` is updated even if notifications have not been delivered
- Therefore, persistence failures of `events/deliveries` must be prevented

Suitable cases:
- Using Outbox (`events` / `deliveries`)
- Wanting carry-over retry capability

---

## 6. Concrete Example (Email success / LINE failure)

Assumptions:
- 3 new diffs detected
- Email succeeds
- LINE fails

### A. Update `snapshots` only on notification success

- `snapshots` is not updated
- The same 3 items are likely treated as diff again on the next run
- Duplicate notifications are likely sent to Email as well

### B. Update `snapshots` on successful creation of `events + deliveries`

- 1 `events` document created
- `deliveries` (email, line) created
- `snapshots` updated
- On the next run, the same 3 items normally do not appear as diff
- Only the failed LINE delivery can be retried via `deliveries`

---

## 7. Recommended Conclusion for This Project

Prerequisites:
- `at-least-once`
- Some degree of duplicate notifications is acceptable
- Carry-over retry from Phase 1
- Firestore holds `events` / `deliveries`

Given these prerequisites, treating `snapshots` as follows is the most consistent approach.

- `snapshots` = Baseline for diff comparison
- Update condition = When `events + deliveries` are successfully persisted

This achieves:
- Prevention of missed notifications (guaranteed by `events/deliveries`)
- Suppression of duplicate events (by updating `snapshots`)
- Retry of partial failures (guaranteed by `deliveries`)

---

## 8. Responsibility Assignment (Summary)

- `snapshots`: Baseline for diff comparison
- `events`: Detected diffs (content that should be notified)
- `deliveries`: Delivery state and retry state per notification target
- `runs`: Execution history summary
