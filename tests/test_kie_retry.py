"""Tests for TransientKieError classification and submit_and_wait_with_retry."""
from __future__ import annotations
import pytest
from pipeline.kie import (
    KieError, TransientKieError,
    submit_and_wait_with_retry,
)


def test_transient_kie_error_subclasses_kie_error():
    """TransientKieError IS a KieError so existing except KieError still catches it."""
    e = TransientKieError("boom")
    assert isinstance(e, KieError)


def test_wait_for_video_classifies_high_traffic_as_transient():
    """The 'Request temporarily unavailable due to high traffic on Google models' pattern
    must surface as TransientKieError, not plain KieError."""
    from pipeline.kie import KieClient
    client = KieClient.__new__(KieClient)  # avoid __init__'s API key check
    client._base = "https://fake"

    poll_count = {"n": 0}
    def fake_poll(job_id):
        poll_count["n"] += 1
        return {
            "data": {
                "successFlag": 3,
                "errorCode": 400,
                "errorMessage": "Request temporarily unavailable due to high traffic on Google models. Please try again later.",
            }
        }
    client.poll_job = fake_poll
    with pytest.raises(TransientKieError):
        client.wait_for_video("job-x", poll_interval_s=0, timeout_s=5)


def test_wait_for_video_classifies_other_failures_as_non_transient():
    """successFlag=3 with a content-flag-style errorMessage stays as plain KieError."""
    from pipeline.kie import KieClient
    client = KieClient.__new__(KieClient)
    client._base = "https://fake"
    client.poll_job = lambda j: {
        "data": {
            "successFlag": 3,
            "errorCode": 400,
            "errorMessage": "content was flagged by safety filters",
        }
    }
    with pytest.raises(KieError) as exc_info:
        client.wait_for_video("job-y", poll_interval_s=0, timeout_s=5)
    assert not isinstance(exc_info.value, TransientKieError)


def test_submit_and_wait_with_retry_recovers_from_transient_failure(monkeypatch):
    """When the first submit→wait raises TransientKieError, retry up to
    max_attempts with exponential backoff and a bumped seed."""
    from pipeline.kie import KieClient

    monkeypatch.setattr("pipeline.kie._SLEEP", lambda s: None)  # skip backoff sleep

    client = KieClient.__new__(KieClient)
    client._base = "https://fake"

    submitted = []
    def fake_submit(**kwargs):
        submitted.append(dict(kwargs))
        return f"job-{len(submitted)}"
    client.submit_video_job = fake_submit

    waits = {"n": 0}
    def fake_wait(job_id, **kw):
        waits["n"] += 1
        if waits["n"] <= 2:  # first two attempts transient-fail
            raise TransientKieError(f"task {job_id} successFlag=3: high traffic")
        return f"http://fake/{job_id}.mp4"
    client.wait_for_video = fake_wait

    url = submit_and_wait_with_retry(
        client,
        submit_kwargs={"prompt": "p", "model": "veo3_fast",
                       "aspect_ratio": "9:16", "seed": 1234,
                       "duration_s": 8, "negative_prompt": ""},
        poll_interval_s=1, timeout_s=60,
        max_attempts=4, seed_bump=100_000,
    )
    assert url == "http://fake/job-3.mp4"
    # Three submit calls; seeds bumped on each retry
    assert len(submitted) == 3
    assert submitted[0]["seed"] == 1234
    assert submitted[1]["seed"] == 1234 + 100_000
    assert submitted[2]["seed"] == 1234 + 200_000


def test_submit_and_wait_with_retry_gives_up_after_max_attempts(monkeypatch):
    """Persistent transient error → raises TransientKieError after max_attempts."""
    from pipeline.kie import KieClient

    monkeypatch.setattr("pipeline.kie._SLEEP", lambda s: None)

    client = KieClient.__new__(KieClient)
    client._base = "https://fake"
    client.submit_video_job = lambda **kw: "job-1"
    def always_fails(*a, **kw):
        raise TransientKieError("task job-1 successFlag=3: high traffic")
    client.wait_for_video = always_fails

    with pytest.raises(TransientKieError):
        submit_and_wait_with_retry(
            client,
            submit_kwargs={"prompt": "p", "model": "veo3_fast",
                           "aspect_ratio": "9:16", "seed": 0,
                           "duration_s": 8, "negative_prompt": ""},
            poll_interval_s=1, timeout_s=60, max_attempts=3,
        )


def test_submit_and_wait_with_retry_does_not_retry_on_permanent_error(monkeypatch):
    """Non-transient KieError (e.g. content-flag, auth) raises immediately
    after one submit attempt — no retry."""
    from pipeline.kie import KieClient

    monkeypatch.setattr("pipeline.kie._SLEEP", lambda s: None)

    client = KieClient.__new__(KieClient)
    client._base = "https://fake"
    submit_count = {"n": 0}
    def fake_submit(**kw):
        submit_count["n"] += 1
        return "job-1"
    client.submit_video_job = fake_submit
    client.wait_for_video = lambda j, **k: (_ for _ in ()).throw(
        KieError("task job-1 successFlag=3: content was flagged by safety filters")
    )

    with pytest.raises(KieError):
        submit_and_wait_with_retry(
            client,
            submit_kwargs={"prompt": "p", "model": "veo3_fast",
                           "aspect_ratio": "9:16", "seed": 0,
                           "duration_s": 8, "negative_prompt": ""},
            poll_interval_s=1, timeout_s=60, max_attempts=4,
        )
    assert submit_count["n"] == 1   # no retries
