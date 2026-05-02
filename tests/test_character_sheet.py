"""Character-sheet stage tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import character_sheet as cs_mod
from pipeline.character_sheet import generate_character_sheet
from pipeline.kie import KieClient


def _client() -> KieClient:
    return KieClient(api_key="k")


def test_generates_when_missing(monkeypatch, tmp_path: Path, fixtures_dir: Path):
    sample = (fixtures_dir / "pixel.png").read_bytes()
    monkeypatch.setattr(KieClient, "submit_flux_image_job",
                        lambda self, **kw: "flux_task_id")
    monkeypatch.setattr(KieClient, "wait_for_flux_image",
                        lambda self, jid, **kw: "https://cdn/cs.png")

    def fake_download(self, url, out):
        out.write_bytes(sample)

    monkeypatch.setattr(KieClient, "_download", fake_download)
    monkeypatch.setattr(cs_mod, "_SLEEP", lambda _s: None)

    out = tmp_path / "character_sheet.png"
    generate_character_sheet(
        client=_client(),
        out_path=out,
        global_setting="anthropomorphic fruit characters family",
        model="flux-1.1-pro",
        poll_interval_s=1, poll_timeout_s=10,
    )
    assert out.exists()
    assert out.stat().st_size > 0


def test_skips_when_already_present(monkeypatch, tmp_path: Path):
    """Idempotent: if file exists, don't call Flux again."""
    out = tmp_path / "cs.png"
    out.write_bytes(b"existing")
    called = {"n": 0}
    monkeypatch.setattr(KieClient, "submit_flux_image_job",
                        lambda self, **kw: called.__setitem__("n", called["n"] + 1) or "x")

    generate_character_sheet(
        client=_client(), out_path=out,
        global_setting="x", model="flux-1.1-pro",
        poll_interval_s=1, poll_timeout_s=10,
    )
    assert called["n"] == 0
