# macOS telemetry publisher ownership cutover

Evidence cutoff: `2026-08-01T20:05:22Z`. This package is staged only. It has
not changed crontab, launchd, a process, a pointer, or Telegram transport.

## Finding

Two schedulers currently invoke the same signed public telemetry publisher with
the same secret and endpoint:

| Owner | Schedule | Source | Result |
| --- | --- | --- | --- |
| `com.sapphire.alpha-telemetry-publisher` LaunchAgent | `StartInterval=60` | detached reviewed checkout `d0e0ece340f386cc9d7ec3065e728a90ca98f9dd` | accepted |
| user crontab | `*/2 * * * *` | mutable primary checkout `d1284f2d29d1fd754fc1daa7b3c71d9672b3d22a` | HTTP 422 |

The exact competing cron owner is:

```cron
*/2 * * * * /Users/aribs/Code/sapphire-alpha-dashboard/telemetry/run_publisher.sh >> /Users/aribs/autonomy-status/logs/alpha-telemetry-publisher.cron.log 2>&1
```

At the evidence cutoff:

- current crontab SHA-256: `2d7033d7c11f4d8d1f192e1739491c4b38c9a342d8ea9a05d4e85f639607cd5c`;
- exact candidate after deleting only that line: `081975f7e09c9d9d93c46396dc80198ddb28094dbcede2a8bbefe9648df3d883`;
- installed plist SHA-256: `adf6c2a22da7f96058ec84512eec72d8544207b5a2c6335a76650a9b345f580e`;
- reviewed runner SHA-256: `f58b4167468eafbbb1021a3197dfce8cb1945c7ef0dca67fc05ead3560813143`;
- reviewed merged collector SHA-256: `4bfe4a4ae5cd156a088370804571f68c8619b3f1f4a70f8ac18d82d2698ed2ee`;
- legacy merged collector SHA-256: `2500e650ccbb2874a2d13f88aad044a53785f3e471ca4f28cf44a7c60cdd1737`;
- launchd had reached run `2369`, last exit `0`, and the accepted log was current;
- the isolated read-only preflight counted `2,194` HTTP 422 failures in the
  legacy cron log; the next scheduled attempt increased that to `2,195`;
- the last eight launchd records were strictly increasing accepted receipts.

The two wrappers are byte-identical. The collectors are not. The primary
checkout is clean under `telemetry/` but is an older telemetry contract; the
reviewed checkout validates locally and is accepted by the deployed ingest.
The HTTP 422 body is not preserved by the legacy client, so the precise server
validation field is unproven. Retirement does not depend on guessing it.

## Golden contract

`backend/tests/test_retire_legacy_publisher_cron.py` freezes these invariants:

1. exactly one byte-for-byte legacy line must exist;
2. every unrelated crontab byte is preserved;
3. the before and candidate digests must match the sealed values;
4. a second read must still equal the captured before image immediately before
   install;
5. the post-install read must equal the exact candidate;
6. launchd must name the exact installed plist, reviewed runner, 60-second
   interval, healthy last exit, and a non-regressed run count;
7. continuity requires at least three new launchd runs and four new accepted
   receipts, a final receipt no older than 120 seconds, and no legacy cron-log
   growth after the in-flight grace period;
8. rollback is allowed only while the crontab still equals the exact candidate;
   a concurrent third-party change is never overwritten;
9. the tool contains no signal or launchd mutation path.

## Read-only preflight

Run from the staged worktree:

```zsh
cd /Users/aribs/ops-state/worktrees/mac-publisher-retirement-r1
/Users/aribs/Code/sapphire-alpha-dashboard/backend/.venv/bin/python \
  scripts/retire_legacy_publisher_cron.py preflight
```

The preflight reads crontab, the installed plist, the reviewed worktree, the
launchd service record, and the separate publisher logs. It does not read the
ingest secret and does not invoke either publisher.

## Exact attended cutover

Only after a fresh `PRECHECK_PASS`, invoke:

```zsh
cd /Users/aribs/ops-state/worktrees/mac-publisher-retirement-r1
/Users/aribs/Code/sapphire-alpha-dashboard/backend/.venv/bin/python \
  scripts/retire_legacy_publisher_cron.py apply \
  --confirm RETIRE_EXACT_LEGACY_PUBLISHER_CRON
```

The executor:

1. acquires an atomic transaction lock;
2. repeats every preflight assertion;
3. writes mode-0600 before/candidate evidence under
   `/Users/aribs/ops-state/rebuild-20260801/mac-publisher-retirement-r1/runs/<UTC>/`;
4. double-reads the exact before image and installs the exact candidate;
5. permits a 90-second grace period for a cron instance that was already in
   flight (the legacy path budgets 60 seconds for Windows SSH and another 10
   seconds for ingest, with margin for probes and startup);
6. observes continuity for exactly 300 more seconds, polling every five
   seconds;
7. accepts only if all golden continuity requirements hold.

Total attended observation is approximately 390 seconds plus command startup.
It spans at least two absent two-minute cron boundaries and multiple launchd
cycles.

## Rollback

On any post-install continuity failure, the executor re-reads crontab:

- if it still has candidate SHA-256 `081975f7...d883`, it installs the exact
  before snapshot `2d7033d7...cd5c` and verifies byte equality;
- if any other writer has changed it, automatic rollback refuses to overwrite
  that writer and emits `manual_reconciliation_required` with the preserved
  before/candidate files.

Rollback does not touch launchd, signal a process, invoke a publisher, send
Telegram, or change any trading/pointer state.

## Risk and execution decision

Removing this line is operationally low-risk because the legacy owner is
currently rejected while the launchd owner is accepted. The important residual
risk is source durability: launchd points to a clean but detached reviewed Git
worktree, not a content-addressed release directory. Its exact commit and file
hashes are therefore sealed into the preflight, and any drift fails closed.

The package is safe for a later one-shot attended executor after a fresh
`PRECHECK_PASS`. It should not be scheduled as an unattended recurring
automation: macOS crontab exposes no native atomic compare-and-swap primitive,
and this changes the scheduler for an outward public-data publisher. The staged
tool supplies the strongest available optimistic CAS, conflict-aware rollback,
and a bounded continuity proof.
