# Firestore Design Checklist (Answer Sheet)

Please fill in this file and return it.  
Purpose: Finalize the implementation scope and reliability requirements under a `GitHub Actions + Firestore` setup.

Rules for filling in
- Replace `TODO:` with your chosen option
- Add free-text notes as needed
- Write `TBD` for undecided items

---

## 1. Core Principles (Most Important)

### 1-1. Delivery Guarantee Level
- [x] `at-least-once` (duplicate notifications may occur, but missed notifications are avoided)
- [ ] `at-most-once` (duplicate notifications are avoided, but missed notifications are tolerated)
- Answer: `at-least-once`
- Notes: Ideally, manage per notification target and deliver exactly once to each. Low priority.

### 1-2. Snapshot Update on Notification Failure
- [x] Update `snapshots` only on notification success (prevents missed notifications)
- [ ] Update `snapshots` even on notification failure (prioritizes duplicate notification suppression)
- Answer: `Update only on success (implemented via Outbox pattern)`
- Notes: The Firestore backend uses the Outbox pattern. Snapshots are updated once event + deliveries are persisted to Firestore. Even if the notification itself fails, the delivery record remains and will be redelivered on the next run. The local backend saves only on notification success.

### 1-3. Handling Partial Notification Failure (e.g., email succeeds / LINE fails)
- [ ] Treat as `partial_failure` and fail the entire run (non-zero exit)
- [x] Treat as `partial_failure` but consider the entire run successful
- Answer: `partial_failure is recorded, but the run itself continues`
- Notes: Run status is set to `partial_failure` (when redelivery_failed > 0 or notification_error exists). Failed deliveries remain in the outbox and are redelivered on the next run.

### 1-4. Tolerance for Duplicate Notifications
- [x] Somewhat tolerable (monitoring use case, so avoiding missed notifications takes priority)
- [ ] Should be avoided as much as possible (duplicates are nearly unacceptable)
- Answer: `Somewhat tolerable`
- Notes: dedupe_key (SHA-256 of source_key + diff) suppresses duplicate event generation for identical diffs, but at the delivery level, duplicates may occur due to at-least-once semantics.

---

## 2. Retry / Redelivery

### 2-1. In-Run Retry
- [x] Required (recommended)
- [ ] Not required
- Answer: `Required`

### 2-2. In-Run Retry Count (Initial Value)
- [ ] 0 (no retries)
- [ ] 1
- [x] 2
- [ ] 3
- [ ] Other:
- Answer: `2` (configurable via `NOTIFY_RETRY_MAX_RETRIES` environment variable, default 2)

### 2-3. Cross-Run Retry / Outbox (Carry Over to Next Run)
- [x] Required from Phase 1
- [ ] Add in Phase 2 (not needed initially)
- [ ] Not required
- Answer: `Implemented from Phase 1`
- Notes: At the start of each run, `_process_redeliveries()` automatically resends failed deliveries whose `next_retry_at` has elapsed. `next_retry_at` is calculated using exponential backoff (initial delay 60s, multiplier 2x).

### 2-4. Redelivery Target
- [x] Only resend failed notifications
- [ ] Re-detecting the same diff on re-execution is sufficient (no dedicated redelivery needed)
- Answer: `Only resend failed notifications`

---

## 3. Firestore Storage Design (Phase 1 Scope)

### 3-1. Collections to Implement in Phase 1
- [ ] `snapshots` + `runs` only (recommended)
- [x] `snapshots` + `runs` + `events` + `deliveries` all at once
- Answer: `snapshots + runs + events + deliveries` (all implemented)

### 3-2. Granularity of Information Stored in `runs`
- [x] Summary-focused (counts, status, error overview)
- [ ] Store detailed logs as well (more per-source detail)
- Answer: `Summary-focused`
- Notes: startedAt, finishedAt, status, runtime, triggerType, dryRun, summary (dict), errors (list). TTL 30 days.

### 3-3. Content Stored in `snapshots`
- [x] Full results (equivalent to current behavior)
- [ ] Minimal (only keys needed for diff detection)
- Answer: `Full results`
- Notes: All results stored in lastSnapshot + SHA-256 hash (lastSnapshotHash) for fast diff detection. No TTL (retained permanently).

---

## 4. Retention Period / Operations

### 4-1. Retention Period for `runs`
- [x] 30 days
- [ ] 90 days (recommended)
- [ ] 180 days
- [ ] Indefinite
- [ ] Other:
- Answer: `30 days` (expiresAt set via `_ttl_after()`, auto-deleted by Firestore TTL policy)

### 4-2. Retention Period for `events` / `deliveries` (Phase 2)
- [x] 30 days
- [ ] 60 days (recommended)
- [ ] 90 days
- [ ] Indefinite
- [ ] TBD
- Answer: `30 days` (implemented with the same TTL setting as runs)

### 4-3. Concurrent Manual and Scheduled Runs (Including Future)
- [x] Not a concern for now (duplicate runs are tolerable)
- [ ] Want mutual exclusion from Phase 1
- [ ] Add mutual exclusion in Phase 2
- Answer: `Not a concern for now`

---

## 5. Execution Platform / Secrets / Budget

### 5-1. Current Execution Platform
- [x] GitHub Actions (recommended)
- [ ] Cloud Run Job (migrate now)
- [ ] Other:
- Answer: `GitHub Actions`

### 5-2. Secret Management (Current)
- [x] GitHub Actions Secrets (recommended)
- [ ] GCP Secret Manager (migrate now)
- [ ] Other:
- Answer: `GitHub Actions Secrets + Variables`
- Notes: Plan to migrate secrets to Secret Manager when moving the execution platform to Cloud Run. Non-sensitive values are managed via GitHub Variables.

### 5-3. Monthly Budget Estimate (Rough)
- [x] Prioritize near-free (~$0-5)
- [ ] Low cost is fine (~$5-15)
- [ ] Willing to spend moderately (~$15-50)
- [ ] TBD
- Answer: `Prioritize near-free (~$0-5)`

---

## 6. Future Requirements (Reflect in Design Only for Now)

### 6-1. Expected Number of Monitoring Targets (Future)
- [x] Single target only
- [ ] A few (2-10)
- [ ] Possibly 10 or more
- Answer: `Single target only`

### 6-2. Future Expansion of Notification Targets
- [x] Email / LINE is sufficient
- [ ] May want to add Slack / Discord / Webhook
- Answer: `Email / LINE is sufficient`

### 6-3. Need for Operations Dashboard / Analytics
- [ ] Not needed (log review is sufficient)
- [ ] Would like run history visualization (simple)
- [x] BigQuery / dashboard in the future is in scope
- Answer: `BigQuery / dashboard in the future is in scope`

---

## 7. Final Confirmation (May We Proceed with Implementation Based on These Answers?)

- [x] Proceed with implementation based on the above answers
- [ ] Want an additional design review before implementation
- Answer: `Already implemented (Phase 1 complete, implementation finished based on all decisions above)`

Additional notes / free text:
- All Phase 1 collections (snapshots / runs / events / deliveries) are implemented
- At-least-once delivery via the Outbox pattern is operational
- 106 tests cover all layers (pytest / ruff / mypy all green)
- Dead-letter mechanism is not implemented (failed deliveries expire naturally after 30 days via TTL)
