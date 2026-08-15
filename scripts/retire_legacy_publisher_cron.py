#!/usr/bin/env python3
"""Retire one exact legacy cron publisher while preserving launchd ownership.

The default command is read-only. The mutation path requires an explicit
confirmation phrase, two byte-for-byte crontab comparisons, a post-install
verification, and a five-minute continuity observation. It never starts,
stops, or signals a process and never invokes the publisher itself.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, NoReturn


LABEL = "com.sapphire.alpha-telemetry-publisher"
EXPECTED_PLIST_PATH = (
    "/Users/aribs/Library/LaunchAgents/com.sapphire.alpha-telemetry-publisher.plist"
)
EXPECTED_PROGRAM = (
    "/Users/aribs/Code/.worktrees/sapphire-publisher-reviewed/telemetry/"
    "run_publisher.sh"
)
EXPECTED_CHECKOUT = "/Users/aribs/Code/.worktrees/sapphire-publisher-reviewed"
EXPECTED_CHECKOUT_COMMIT = "d0e0ece340f386cc9d7ec3065e728a90ca98f9dd"
EXPECTED_PLIST_SHA256 = (
    "adf6c2a22da7f96058ec84512eec72d8544207b5a2c6335a76650a9b345f580e"
)
EXPECTED_RUNNER_SHA256 = (
    "f58b4167468eafbbb1021a3197dfce8cb1945c7ef0dca67fc05ead3560813143"
)
EXPECTED_COLLECTOR_PATH = (
    "/Users/aribs/Code/.worktrees/sapphire-publisher-reviewed/telemetry/"
    "merged_collector.py"
)
EXPECTED_COLLECTOR_SHA256 = (
    "4bfe4a4ae5cd156a088370804571f68c8619b3f1f4a70f8ac18d82d2698ed2ee"
)
EXPECTED_LOG_PATH = "/Users/aribs/autonomy-status/logs/alpha-telemetry-publisher.log"
LEGACY_LOG_PATH = "/Users/aribs/autonomy-status/logs/alpha-telemetry-publisher.cron.log"
LEGACY_LINE = (
    b"*/2 * * * * /Users/aribs/Code/sapphire-alpha-dashboard/telemetry/"
    b"run_publisher.sh >> /Users/aribs/autonomy-status/logs/"
    b"alpha-telemetry-publisher.cron.log 2>&1\n"
)
EXPECTED_BEFORE_SHA256 = (
    "2d7033d7c11f4d8d1f192e1739491c4b38c9a342d8ea9a05d4e85f639607cd5c"
)
EXPECTED_CANDIDATE_SHA256 = (
    "081975f7e09c9d9d93c46396dc80198ddb28094dbcede2a8bbefe9648df3d883"
)
MINIMUM_SEALED_RUNS = 2362
EXPECTED_INTERVAL_SECONDS = 60
IN_FLIGHT_GRACE_SECONDS = 90
CONTINUITY_SECONDS = 300
CONTINUITY_POLL_SECONDS = 5
MINIMUM_NEW_RUNS = 3
MINIMUM_NEW_RECEIPTS = 4
MAX_FINAL_RECEIPT_AGE_SECONDS = 120.0
CONFIRMATION = "RETIRE_EXACT_LEGACY_PUBLISHER_CRON"
DEFAULT_EVIDENCE_ROOT = Path(
    "/Users/aribs/ops-state/rebuild-20260801/mac-publisher-retirement-r1/runs"
)
DEFAULT_LOCK = Path(
    "/Users/aribs/ops-state/locks/sapphire-publisher-crontab-cutover.lock"
)


class CutoverError(RuntimeError):
    """Base class for a fail-closed cutover refusal."""


class PreconditionError(CutoverError):
    """The sealed owner or source state no longer matches."""


class ConcurrentMutationError(CutoverError):
    """Another writer changed the crontab during the transaction."""


class ContinuityError(CutoverError):
    """The launchd owner did not prove continuity after retirement."""


@dataclasses.dataclass(frozen=True)
class CrontabCasResult:
    before_sha256: str
    candidate_sha256: str


@dataclasses.dataclass(frozen=True)
class LaunchdEvidence:
    path: str
    program: str
    state: str
    runs: int
    last_exit_code: int
    interval_seconds: int


@dataclasses.dataclass(frozen=True)
class ContinuityEvidence:
    runs_before: int
    runs_after: int
    accepted_sequences_after_cutover: tuple[int, ...]
    final_receipt_age_seconds: float
    launchd_last_exit_code: int
    crontab_sha256: str
    expected_candidate_sha256: str
    cron_log_settled_size: int
    cron_log_final_size: int


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def derive_candidate(current: bytes, legacy_line: bytes = LEGACY_LINE) -> bytes:
    count = current.count(legacy_line)
    if count != 1:
        raise PreconditionError(
            f"expected exactly one legacy cron owner, observed {count}"
        )
    return current.replace(legacy_line, b"", 1)


def compare_and_swap_crontab(
    *,
    read: Callable[[], bytes],
    install: Callable[[bytes], None],
    expected_before_sha256: str = EXPECTED_BEFORE_SHA256,
    expected_candidate_sha256: str = EXPECTED_CANDIDATE_SHA256,
    legacy_line: bytes = LEGACY_LINE,
) -> CrontabCasResult:
    before = read()
    before_sha256 = sha256_bytes(before)
    if before_sha256 != expected_before_sha256:
        raise PreconditionError(
            "crontab owner CAS refused: "
            f"expected {expected_before_sha256}, observed {before_sha256}"
        )

    candidate = derive_candidate(before, legacy_line)
    candidate_sha256 = sha256_bytes(candidate)
    if candidate_sha256 != expected_candidate_sha256:
        raise PreconditionError(
            "derived candidate does not match the sealed candidate: "
            f"expected {expected_candidate_sha256}, observed {candidate_sha256}"
        )

    second_read = read()
    if second_read != before:
        raise PreconditionError("crontab changed between capture and install")

    install(candidate)
    installed = read()
    if installed != candidate:
        raise ConcurrentMutationError(
            "installed crontab is neither the exact transaction candidate nor safe "
            "to overwrite; manual reconciliation is required"
        )

    return CrontabCasResult(before_sha256, candidate_sha256)


def rollback_if_owned(
    *,
    read: Callable[[], bytes],
    install: Callable[[bytes], None],
    before: bytes,
    candidate_sha256: str = EXPECTED_CANDIDATE_SHA256,
) -> None:
    current = read()
    current_sha256 = sha256_bytes(current)
    if current_sha256 != candidate_sha256:
        raise ConcurrentMutationError(
            "automatic rollback refused because the crontab is no longer the exact "
            f"candidate: expected {candidate_sha256}, observed {current_sha256}"
        )
    install(before)
    restored = read()
    if restored != before:
        raise ConcurrentMutationError(
            "rollback write did not restore the exact snapshot"
        )


def _field(output: str, name: str) -> str:
    match = re.search(rf"^\s*{re.escape(name)}\s*=\s*(.*?)\s*$", output, re.MULTILINE)
    if not match:
        raise PreconditionError(f"launchctl output is missing {name!r}")
    return match.group(1)


def parse_launchctl_print(output: str) -> LaunchdEvidence:
    return LaunchdEvidence(
        path=_field(output, "path"),
        program=_field(output, "program"),
        state=_field(output, "state"),
        runs=int(_field(output, "runs")),
        last_exit_code=int(_field(output, "last exit code")),
        interval_seconds=int(_field(output, "run interval").removesuffix(" seconds")),
    )


def validate_launchd_evidence(
    evidence: LaunchdEvidence, *, minimum_runs: int = MINIMUM_SEALED_RUNS
) -> None:
    expected = {
        "path": EXPECTED_PLIST_PATH,
        "program": EXPECTED_PROGRAM,
        "last_exit_code": 0,
        "interval_seconds": EXPECTED_INTERVAL_SECONDS,
    }
    for name, value in expected.items():
        if getattr(evidence, name) != value:
            raise PreconditionError(
                f"launchd {name} drifted: expected {value!r}, "
                f"observed {getattr(evidence, name)!r}"
            )
    if evidence.state not in {"running", "not running"}:
        raise PreconditionError(f"unexpected launchd state {evidence.state!r}")
    if evidence.runs < minimum_runs:
        raise PreconditionError(
            f"launchd runs regressed: expected at least {minimum_runs}, "
            f"observed {evidence.runs}"
        )


def accepted_sequences(log_bytes: bytes) -> list[int]:
    result: list[int] = []
    for raw_line in log_bytes.splitlines():
        try:
            value = json.loads(raw_line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(value, dict):
            continue
        sequence = value.get("sequence")
        if value.get("accepted") is not True or not isinstance(sequence, int):
            continue
        if not result or sequence > result[-1]:
            result.append(sequence)
    return result


def validate_continuity(evidence: ContinuityEvidence) -> None:
    failures: list[str] = []
    if evidence.runs_after - evidence.runs_before < MINIMUM_NEW_RUNS:
        failures.append("fewer than three new launchd runs")
    if len(evidence.accepted_sequences_after_cutover) < MINIMUM_NEW_RECEIPTS:
        failures.append("fewer than four accepted post-cutover receipts")
    if evidence.final_receipt_age_seconds > MAX_FINAL_RECEIPT_AGE_SECONDS:
        failures.append("final accepted receipt is older than 120 seconds")
    if evidence.launchd_last_exit_code != 0:
        failures.append("launchd last exit code is nonzero")
    if evidence.crontab_sha256 != evidence.expected_candidate_sha256:
        failures.append("crontab no longer matches the exact candidate")
    if evidence.cron_log_final_size != evidence.cron_log_settled_size:
        failures.append("legacy cron log changed after the in-flight grace period")
    if failures:
        raise ContinuityError("; ".join(failures))


def _run(
    argv: list[str], *, input_bytes: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    process = subprocess.run(
        argv,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="replace").strip()
        raise CutoverError(f"command failed ({argv!r}): {stderr}")
    return process


def read_crontab() -> bytes:
    return _run(["crontab", "-l"]).stdout


def install_crontab(value: bytes) -> None:
    _run(["crontab", "-"], input_bytes=value)


def read_launchd() -> LaunchdEvidence:
    output = _run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"]).stdout.decode(
        "utf-8", errors="strict"
    )
    return parse_launchctl_print(output)


def _require_file_hash(path: str, expected: str) -> None:
    observed = sha256_file(path)
    if observed != expected:
        raise PreconditionError(
            f"file drifted: {path}: expected {expected}, observed {observed}"
        )


def _validate_plist() -> None:
    _require_file_hash(EXPECTED_PLIST_PATH, EXPECTED_PLIST_SHA256)
    with Path(EXPECTED_PLIST_PATH).open("rb") as handle:
        value = plistlib.load(handle)
    checks = {
        "Label": LABEL,
        "ProgramArguments": [EXPECTED_PROGRAM],
        "StartInterval": EXPECTED_INTERVAL_SECONDS,
        "RunAtLoad": True,
        "StandardOutPath": EXPECTED_LOG_PATH,
        "StandardErrorPath": (
            "/Users/aribs/autonomy-status/logs/alpha-telemetry-publisher.err"
        ),
    }
    for key, expected in checks.items():
        if value.get(key) != expected:
            raise PreconditionError(
                f"installed plist {key} drifted: expected {expected!r}, "
                f"observed {value.get(key)!r}"
            )


def _validate_checkout() -> None:
    observed = _run(["git", "-C", EXPECTED_CHECKOUT, "rev-parse", "HEAD"]).stdout
    commit = observed.decode("ascii").strip()
    if commit != EXPECTED_CHECKOUT_COMMIT:
        raise PreconditionError(
            f"publisher checkout drifted: expected {EXPECTED_CHECKOUT_COMMIT}, "
            f"observed {commit}"
        )
    status = _run(["git", "-C", EXPECTED_CHECKOUT, "status", "--porcelain"]).stdout
    if status:
        raise PreconditionError("publisher checkout is dirty")
    _require_file_hash(EXPECTED_PROGRAM, EXPECTED_RUNNER_SHA256)
    _require_file_hash(EXPECTED_COLLECTOR_PATH, EXPECTED_COLLECTOR_SHA256)


def collect_preflight() -> dict[str, object]:
    current = read_crontab()
    before_sha256 = sha256_bytes(current)
    if before_sha256 != EXPECTED_BEFORE_SHA256:
        raise PreconditionError(
            f"crontab drifted: expected {EXPECTED_BEFORE_SHA256}, observed {before_sha256}"
        )
    candidate = derive_candidate(current)
    candidate_sha256 = sha256_bytes(candidate)
    if candidate_sha256 != EXPECTED_CANDIDATE_SHA256:
        raise PreconditionError(
            "candidate drifted: "
            f"expected {EXPECTED_CANDIDATE_SHA256}, observed {candidate_sha256}"
        )
    _validate_plist()
    _validate_checkout()
    launchd = read_launchd()
    validate_launchd_evidence(launchd)
    sequences = accepted_sequences(Path(EXPECTED_LOG_PATH).read_bytes())
    if len(sequences) < 3:
        raise PreconditionError("fewer than three accepted launchd receipts exist")
    receipt_age = time.time() - (sequences[-1] / 1_000_000_000)
    if receipt_age < 0 or receipt_age > MAX_FINAL_RECEIPT_AGE_SECONDS:
        raise PreconditionError(
            f"latest accepted launchd receipt age is {receipt_age:.3f}s"
        )
    legacy_log = Path(LEGACY_LOG_PATH).read_bytes()
    return {
        "status": "PRECHECK_PASS",
        "mutationPerformed": False,
        "crontabBeforeSha256": before_sha256,
        "crontabCandidateSha256": candidate_sha256,
        "legacyOwnerCount": current.count(LEGACY_LINE),
        "launchd": dataclasses.asdict(launchd),
        "launchdPlistSha256": EXPECTED_PLIST_SHA256,
        "publisherCheckoutCommit": EXPECTED_CHECKOUT_COMMIT,
        "publisherRunnerSha256": EXPECTED_RUNNER_SHA256,
        "publisherCollectorSha256": EXPECTED_COLLECTOR_SHA256,
        "latestAcceptedSequence": sequences[-1],
        "latestAcceptedReceiptAgeSeconds": round(receipt_age, 3),
        "legacyCronHttp422Count": legacy_log.count(b"HTTP Error 422"),
        "continuityWindowSeconds": CONTINUITY_SECONDS,
        "inFlightGraceSeconds": IN_FLIGHT_GRACE_SECONDS,
        "rollback": "restore exact before snapshot only if current crontab still equals candidate",
    }


def _atomic_write(path: Path, value: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _write_json(path: Path, value: object) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write(path, encoded)


def _receipt_age(sequences: list[int]) -> float:
    if not sequences:
        return float("inf")
    return max(0.0, time.time() - (sequences[-1] / 1_000_000_000))


def apply_cutover(evidence_root: Path, lock_path: Path) -> dict[str, object]:
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        lock_path.mkdir(parents=False, exist_ok=False)
    except FileExistsError as exc:
        raise PreconditionError(f"cutover lock already exists: {lock_path}") from exc

    transaction_dir: Path | None = None
    installed = False
    before = b""
    try:
        preflight = collect_preflight()
        transaction_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        transaction_dir = evidence_root / transaction_id
        transaction_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        before = read_crontab()
        candidate = derive_candidate(before)
        _atomic_write(transaction_dir / "crontab.before", before)
        _atomic_write(transaction_dir / "crontab.candidate", candidate)
        _write_json(transaction_dir / "preflight.json", preflight)

        launchd_before = read_launchd()
        start_sequence = time.time_ns()
        cas = compare_and_swap_crontab(read=read_crontab, install=install_crontab)
        installed = True

        time.sleep(IN_FLIGHT_GRACE_SECONDS)
        settled_size = Path(LEGACY_LOG_PATH).stat().st_size
        deadline = time.monotonic() + CONTINUITY_SECONDS
        while time.monotonic() < deadline:
            if sha256_bytes(read_crontab()) != EXPECTED_CANDIDATE_SHA256:
                raise ContinuityError("crontab drifted during continuity observation")
            time.sleep(
                min(CONTINUITY_POLL_SECONDS, max(0.0, deadline - time.monotonic()))
            )

        launchd_after = read_launchd()
        validate_launchd_evidence(launchd_after, minimum_runs=launchd_before.runs)
        sequences = accepted_sequences(Path(EXPECTED_LOG_PATH).read_bytes())
        new_sequences = tuple(value for value in sequences if value > start_sequence)
        continuity = ContinuityEvidence(
            runs_before=launchd_before.runs,
            runs_after=launchd_after.runs,
            accepted_sequences_after_cutover=new_sequences,
            final_receipt_age_seconds=_receipt_age(sequences),
            launchd_last_exit_code=launchd_after.last_exit_code,
            crontab_sha256=sha256_bytes(read_crontab()),
            expected_candidate_sha256=EXPECTED_CANDIDATE_SHA256,
            cron_log_settled_size=settled_size,
            cron_log_final_size=Path(LEGACY_LOG_PATH).stat().st_size,
        )
        validate_continuity(continuity)
        result = {
            "status": "CUTOVER_PASS",
            "mutationPerformed": True,
            "rolledBack": False,
            "transactionDirectory": str(transaction_dir),
            "cas": dataclasses.asdict(cas),
            "continuity": dataclasses.asdict(continuity),
        }
        _write_json(transaction_dir / "result.json", result)
        return result
    except Exception as exc:
        rollback_status = "not_needed"
        rollback_error: str | None = None
        if installed:
            try:
                rollback_if_owned(
                    read=read_crontab,
                    install=install_crontab,
                    before=before,
                )
                rollback_status = "restored_exact_before"
            except Exception as rollback_exc:  # preserve the primary failure too
                rollback_status = "manual_reconciliation_required"
                rollback_error = str(rollback_exc)
        failure = {
            "status": "CUTOVER_FAIL",
            "errorType": type(exc).__name__,
            "error": str(exc),
            "rollbackStatus": rollback_status,
            "rollbackError": rollback_error,
        }
        if transaction_dir is not None:
            _write_json(transaction_dir / "failure.json", failure)
        raise CutoverError(json.dumps(failure, sort_keys=True)) from exc
    finally:
        try:
            lock_path.rmdir()
        except OSError:
            pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "preflight", help="read-only exact owner and continuity check"
    )
    apply_parser = subparsers.add_parser(
        "apply", help="retire the exact cron line and observe launchd continuity"
    )
    apply_parser.add_argument("--confirm", required=True)
    apply_parser.add_argument(
        "--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT
    )
    apply_parser.add_argument("--lock-path", type=Path, default=DEFAULT_LOCK)
    return parser


def _fail(message: str) -> NoReturn:
    print(
        json.dumps({"status": "REFUSED", "error": message}, sort_keys=True),
        file=sys.stderr,
    )
    raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "preflight":
            print(json.dumps(collect_preflight(), indent=2, sort_keys=True))
            return 0
        if args.confirm != CONFIRMATION:
            _fail(f"exact confirmation required: {CONFIRMATION}")
        result = apply_cutover(args.evidence_root, args.lock_path)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except CutoverError as exc:
        _fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
