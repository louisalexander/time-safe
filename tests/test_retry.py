"""The bounded retry layer for idempotent GitHub reads.

The CLI's stated purpose is unattended cron and systemd use, where a one-off 5xx becoming a failed
break-glass check is worse than a few seconds of waiting. These tests pin both halves of that: what
counts as transient, and the ceiling on how long a retry may ever cost.
"""

import httpx
import pytest

from timesafe.github import retry


def _status_error(status: int, headers: dict | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.github.com/repos/o/r/contents/x")
    response = httpx.Response(status, headers=headers or {}, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


class _Recorder:
    def __init__(self):
        self.slept: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.slept.append(seconds)


def _flaky(*outcomes):
    """A callable that yields each outcome in turn, raising the ones that are exceptions."""
    calls = []

    def fn(*args, **kwargs):
        outcome = outcomes[len(calls)]
        calls.append(args)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    fn.calls = calls
    return fn


# ── what is transient ────────────────────────────────────────────────────────
@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_a_5xx_is_retryable(status):
    assert retry.is_retryable(_status_error(status)) is True


def test_a_429_is_retryable():
    assert retry.is_retryable(_status_error(429)) is True


def test_a_403_with_retry_after_is_retryable():
    # GitHub's secondary rate limit answers 403 and tells you how long to wait.
    assert retry.is_retryable(_status_error(403, {"Retry-After": "2"})) is True


def test_a_plain_403_is_not_retryable():
    # A token missing a scope is 403 forever; retrying it just costs every run ten seconds.
    assert retry.is_retryable(_status_error(403)) is False


@pytest.mark.parametrize("status", [400, 401, 404, 409, 422])
def test_a_definite_client_error_is_not_retryable(status):
    assert retry.is_retryable(_status_error(status)) is False


def test_a_transport_failure_is_retryable():
    request = httpx.Request("GET", "https://api.github.com/x")
    assert retry.is_retryable(httpx.ConnectError("reset", request=request)) is True
    assert retry.is_retryable(httpx.ReadTimeout("slow", request=request)) is True


def test_an_unrelated_exception_is_not_retryable():
    assert retry.is_retryable(ValueError("nope")) is False


# ── the wrapper ──────────────────────────────────────────────────────────────
def test_a_transient_failure_is_retried_and_the_result_returned():
    sleep = _Recorder()
    fn = _flaky(_status_error(503), "ok")

    assert retry.retrying(fn, sleep=sleep)() == "ok"
    assert len(fn.calls) == 2
    assert len(sleep.slept) == 1


def test_a_definite_failure_is_raised_on_the_first_attempt():
    sleep = _Recorder()
    fn = _flaky(_status_error(404), "never reached")

    with pytest.raises(httpx.HTTPStatusError):
        retry.retrying(fn, sleep=sleep)()

    assert len(fn.calls) == 1
    assert sleep.slept == []


def test_attempts_are_bounded_and_the_last_error_is_raised():
    sleep = _Recorder()
    fn = _flaky(*[_status_error(500) for _ in range(retry.ATTEMPTS)])

    with pytest.raises(httpx.HTTPStatusError):
        retry.retrying(fn, sleep=sleep)()

    assert len(fn.calls) == retry.ATTEMPTS
    assert len(sleep.slept) == retry.ATTEMPTS - 1


def test_the_total_wait_never_exceeds_the_documented_ceiling():
    """A cron job must never hang. Whatever the schedule is, its worst case is capped."""
    sleep = _Recorder()
    fn = _flaky(*[_status_error(500) for _ in range(retry.ATTEMPTS)])

    with pytest.raises(httpx.HTTPStatusError):
        retry.retrying(fn, sleep=sleep)()

    assert sum(sleep.slept) <= retry.MAX_TOTAL_DELAY


def test_the_backoff_is_exponential():
    sleep = _Recorder()
    fn = _flaky(*[_status_error(500) for _ in range(4)])

    with pytest.raises(httpx.HTTPStatusError):
        retry.retrying(fn, attempts=4, sleep=sleep)()

    assert sleep.slept == sorted(sleep.slept)
    assert sleep.slept[1] > sleep.slept[0]


def test_a_retry_after_header_is_honoured_over_the_default_schedule():
    sleep = _Recorder()
    fn = _flaky(_status_error(429, {"Retry-After": "2"}), "ok")

    assert retry.retrying(fn, sleep=sleep)() == "ok"
    assert sleep.slept == [2.0]


def test_a_retry_after_longer_than_the_budget_gives_up_rather_than_waiting():
    """A one-hour cooldown is not something an unattended run should sit through."""
    sleep = _Recorder()
    fn = _flaky(_status_error(429, {"Retry-After": "3600"}), "ok")

    with pytest.raises(httpx.HTTPStatusError):
        retry.retrying(fn, sleep=sleep)()

    assert sleep.slept == []


def test_a_malformed_retry_after_falls_back_to_the_default_schedule():
    sleep = _Recorder()
    fn = _flaky(_status_error(429, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), "ok")

    assert retry.retrying(fn, sleep=sleep)() == "ok"
    assert sleep.slept == [retry.BASE_DELAY]


def test_attempts_of_one_disables_retrying_entirely():
    sleep = _Recorder()
    fn = _flaky(_status_error(500), "never reached")

    with pytest.raises(httpx.HTTPStatusError):
        retry.retrying(fn, attempts=1, sleep=sleep)()

    assert len(fn.calls) == 1
    assert sleep.slept == []


def test_the_wrapper_passes_arguments_through_unchanged():
    fn = _flaky(_status_error(500), "ok")
    retry.retrying(fn, sleep=lambda s: None)("vault/secrets/x.meta")
    assert fn.calls[0] == ("vault/secrets/x.meta",)
