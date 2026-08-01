from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts import retire_legacy_publisher_cron as cutover


LEGACY = (
    b"*/2 * * * * /Users/aribs/Code/sapphire-alpha-dashboard/telemetry/"
    b"run_publisher.sh >> /Users/aribs/autonomy-status/logs/"
    b"alpha-telemetry-publisher.cron.log 2>&1\n"
)
BEFORE = (
    b"# keep exactly\n17 */6 * * * /bin/true\n" + LEGACY + b"5 6 * * * /bin/false\n"
)
CANDIDATE = b"# keep exactly\n17 */6 * * * /bin/true\n5 6 * * * /bin/false\n"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_candidate_removes_only_the_exact_legacy_line_byte_for_byte() -> None:
    assert cutover.derive_candidate(BEFORE, LEGACY) == CANDIDATE


@pytest.mark.parametrize("current", [BEFORE.replace(LEGACY, b""), BEFORE + LEGACY])
def test_candidate_refuses_missing_or_duplicate_owner(current: bytes) -> None:
    with pytest.raises(cutover.PreconditionError):
        cutover.derive_candidate(current, LEGACY)


def test_cas_refuses_drift_before_install_without_writing() -> None:
    writes: list[bytes] = []
    current = [BEFORE + b"# concurrent writer\n"]

    with pytest.raises(cutover.PreconditionError):
        cutover.compare_and_swap_crontab(
            read=lambda: current[0],
            install=writes.append,
            expected_before_sha256=digest(BEFORE),
            expected_candidate_sha256=digest(CANDIDATE),
            legacy_line=LEGACY,
        )

    assert writes == []


def test_cas_installs_and_verifies_the_exact_candidate() -> None:
    current = [BEFORE]

    def install(value: bytes) -> None:
        current[0] = value

    result = cutover.compare_and_swap_crontab(
        read=lambda: current[0],
        install=install,
        expected_before_sha256=digest(BEFORE),
        expected_candidate_sha256=digest(CANDIDATE),
        legacy_line=LEGACY,
    )

    assert current[0] == CANDIDATE
    assert result.before_sha256 == digest(BEFORE)
    assert result.candidate_sha256 == digest(CANDIDATE)


def test_cas_detects_postinstall_foreign_content_without_blind_overwrite() -> None:
    foreign = CANDIDATE + b"# concurrent writer\n"
    reads = iter([BEFORE, BEFORE, foreign])
    writes: list[bytes] = []

    with pytest.raises(cutover.ConcurrentMutationError):
        cutover.compare_and_swap_crontab(
            read=lambda: next(reads),
            install=writes.append,
            expected_before_sha256=digest(BEFORE),
            expected_candidate_sha256=digest(CANDIDATE),
            legacy_line=LEGACY,
        )

    assert writes == [CANDIDATE]


def test_rollback_restores_exact_snapshot_only_while_candidate_is_owned() -> None:
    current = [CANDIDATE]

    def install(value: bytes) -> None:
        current[0] = value

    cutover.rollback_if_owned(
        read=lambda: current[0],
        install=install,
        before=BEFORE,
        candidate_sha256=digest(CANDIDATE),
    )

    assert current[0] == BEFORE


def test_rollback_refuses_to_overwrite_a_concurrent_writer() -> None:
    foreign = CANDIDATE + b"# concurrent writer\n"
    writes: list[bytes] = []

    with pytest.raises(cutover.ConcurrentMutationError):
        cutover.rollback_if_owned(
            read=lambda: foreign,
            install=writes.append,
            before=BEFORE,
            candidate_sha256=digest(CANDIDATE),
        )

    assert writes == []


def test_launchd_parser_requires_the_exact_owner_and_healthy_exit() -> None:
    output = """
gui/501/com.sapphire.alpha-telemetry-publisher = {
    path = /Users/aribs/Library/LaunchAgents/com.sapphire.alpha-telemetry-publisher.plist
    state = not running
    program = /Users/aribs/Code/.worktrees/sapphire-publisher-reviewed/telemetry/run_publisher.sh
    runs = 2362
    last exit code = 0
    run interval = 60 seconds
}
"""
    evidence = cutover.parse_launchctl_print(output)

    cutover.validate_launchd_evidence(evidence, minimum_runs=2362)
    assert evidence.state == "not running"
    assert evidence.interval_seconds == 60


def test_launchd_validation_rejects_wrong_program_or_failed_exit() -> None:
    baseline = cutover.LaunchdEvidence(
        path=cutover.EXPECTED_PLIST_PATH,
        program=cutover.EXPECTED_PROGRAM,
        state="not running",
        runs=2362,
        last_exit_code=0,
        interval_seconds=60,
    )

    with pytest.raises(cutover.PreconditionError):
        cutover.validate_launchd_evidence(
            baseline.__class__(**{**baseline.__dict__, "program": "/tmp/wrong"}),
            minimum_runs=2362,
        )
    with pytest.raises(cutover.PreconditionError):
        cutover.validate_launchd_evidence(
            baseline.__class__(**{**baseline.__dict__, "last_exit_code": 1}),
            minimum_runs=2362,
        )


def test_accepted_receipts_ignore_noise_and_require_strict_sequence_order() -> None:
    log = b"""WARN ignored
[]
{"accepted": true, "sequence": 100}
{"accepted": false, "sequence": 150}
not-json
{"accepted": true, "sequence": 200}
{"accepted": true, "sequence": 200}
{"accepted": true, "sequence": 300}
"""
    assert cutover.accepted_sequences(log) == [100, 200, 300]


def test_continuity_requires_four_new_receipts_three_run_increments_and_quiet_cron() -> (
    None
):
    good = cutover.ContinuityEvidence(
        runs_before=2362,
        runs_after=2366,
        accepted_sequences_after_cutover=(101, 102, 103, 104),
        final_receipt_age_seconds=30.0,
        launchd_last_exit_code=0,
        crontab_sha256=digest(CANDIDATE),
        expected_candidate_sha256=digest(CANDIDATE),
        cron_log_settled_size=123,
        cron_log_final_size=123,
    )
    cutover.validate_continuity(good)

    mutations = [
        {"runs_after": 2364},
        {"accepted_sequences_after_cutover": (101, 102, 103)},
        {"final_receipt_age_seconds": 121.0},
        {"launchd_last_exit_code": 1},
        {"crontab_sha256": digest(BEFORE)},
        {"cron_log_final_size": 124},
    ]
    for mutation in mutations:
        with pytest.raises(cutover.ContinuityError):
            cutover.validate_continuity(good.__class__(**{**good.__dict__, **mutation}))


def test_in_flight_grace_covers_the_legacy_ssh_and_push_timeout_budget() -> None:
    # merged_collector permits 60 seconds for Windows SSH and collector.push
    # permits 10 more for ingest. Keep margin for probes and process startup.
    assert cutover.IN_FLIGHT_GRACE_SECONDS >= 90


def test_runtime_source_has_no_signal_or_launchd_mutation_path() -> None:
    source = Path(cutover.__file__).read_text(encoding="utf-8")
    forbidden = (
        "os.kill(",
        "signal.",
        '"kickstart"',
        '"bootout"',
        '"bootstrap"',
        '"unload"',
    )
    assert all(token not in source for token in forbidden)
