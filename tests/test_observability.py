from __future__ import annotations

import json
import logging

import pipeline.observability as obs


def _format(record: logging.LogRecord) -> dict:
    return json.loads(obs.JsonFormatter().format(record))


def test_formatter_emits_severity_and_message():
    rec = logging.LogRecord("t", logging.WARNING, __file__, 1, "hello %s", ("world",), None)
    out = _format(rec)
    assert out["severity"] == "WARNING"
    assert out["message"] == "hello world"
    assert out["logger"] == "t"


def test_formatter_maps_each_level():
    for level, name in [(logging.DEBUG, "DEBUG"), (logging.INFO, "INFO"),
                        (logging.WARNING, "WARNING"), (logging.ERROR, "ERROR"),
                        (logging.CRITICAL, "CRITICAL")]:
        rec = logging.LogRecord("t", level, __file__, 1, "m", (), None)
        assert _format(rec)["severity"] == name


def test_formatter_includes_traceback_on_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        rec = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    out = _format(rec)
    assert "Traceback" in out["message"] and "ValueError: boom" in out["message"]


def test_formatter_merges_extra_context_and_hides_reserved():
    rec = logging.LogRecord("t", logging.ERROR, __file__, 1, "m", (), None)
    rec.run_id = "r1"
    rec.user_id = "u1"
    out = _format(rec)
    assert out["run_id"] == "r1" and out["user_id"] == "u1"
    assert "args" not in out and "levelno" not in out and "msg" not in out


def test_formatter_is_valid_single_line_json():
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "line1\nline2", (), None)
    s = obs.JsonFormatter().format(rec)
    assert "\n" not in s.rstrip("\n").replace("\\n", "")
    json.loads(s)


def test_setup_logging_idempotent():
    root = logging.getLogger()
    saved, saved_flag = root.handlers[:], obs._CONFIGURED
    try:
        root.handlers.clear()
        obs._CONFIGURED = False
        obs.setup_logging()
        first = len(root.handlers)
        obs.setup_logging()
        assert first == 1 and len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, obs.JsonFormatter)
    finally:
        root.handlers[:] = saved
        obs._CONFIGURED = saved_flag


def test_log_exception_emits_error_with_context(caplog):
    with caplog.at_level(logging.ERROR):
        try:
            raise RuntimeError("kaboom")
        except RuntimeError as e:
            obs.log_exception(e, where="unit", run_id="r9")
    rec = [r for r in caplog.records if r.levelno == logging.ERROR][-1]
    assert getattr(rec, "where") == "unit" and getattr(rec, "run_id") == "r9"
    assert rec.exc_info is not None
