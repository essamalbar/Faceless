from __future__ import annotations

from pathlib import Path

from pipeline import agent_memory as am


def test_load_empty(tmp_path):
    m = am.load_memory(tmp_path, "art_x")
    assert m["decisions"] == [] and m["preferences_summary"] == "" and m["artist_id"] == "art_x"


def test_record_decision_appends_atomically(tmp_path):
    am.record_decision(tmp_path, "art_x", run_id="r1", decision="approved", self_score=0.8)
    am.record_decision(tmp_path, "art_x", run_id="r2", decision="rejected", reason="too sad")
    m = am.load_memory(tmp_path, "art_x")
    assert [d["decision"] for d in m["decisions"]] == ["approved", "rejected"]
    assert m["decisions"][1]["reason"] == "too sad"
    assert m["decisions"][0]["self_score"] == 0.8
    assert am.memory_path(tmp_path, "art_x").exists()


def test_distill_uses_llm_and_stores_summary(tmp_path):
    am.record_decision(tmp_path, "art_x", run_id="r1", decision="rejected", reason="abstract lyrics")

    class FakeLLM:
        def complete(self, prompt, system=None):
            return "Prefers concrete imagery over abstract."

    out = am.distill_preferences(tmp_path, "art_x", FakeLLM())
    assert "concrete" in out.lower()
    assert am.load_memory(tmp_path, "art_x")["preferences_summary"] == out


def test_distill_no_decisions_skips_llm(tmp_path):
    class BoomLLM:
        def complete(self, prompt, system=None):
            raise AssertionError("must not call LLM with no decisions")

    assert am.distill_preferences(tmp_path, "art_x", BoomLLM()) == ""
