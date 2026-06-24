from __future__ import annotations

import pytest

import pipeline.song_import as si
from pipeline.song_import import ImportFetchError, download_audio


def test_download_audio_returns_path(tmp_path, monkeypatch):
    # Fake yt-dlp: pretend it wrote the output file.
    out = tmp_path / "reference.m4a"
    def fake_run(url, out_template):
        out.write_bytes(b"\x00\x00")  # stand-in audio bytes
        return str(out)
    monkeypatch.setattr(si, "_ytdlp_download", fake_run)
    p = download_audio("https://www.youtube.com/watch?v=abc123", tmp_path)
    assert p.exists() and p.name == "reference.m4a"


def test_download_audio_raises_clear_error(tmp_path, monkeypatch):
    def boom(url, out_template):
        raise RuntimeError("Video unavailable")
    monkeypatch.setattr(si, "_ytdlp_download", boom)
    with pytest.raises(ImportFetchError):
        download_audio("https://youtu.be/abc123", tmp_path)


from pipeline.song_import import _ngram_overlap


def test_ngram_overlap_detects_near_copy():
    src = "alpha beta gamma delta epsilon zeta eta theta"
    # Same 8 words -> all 4-grams overlap -> 1.0
    assert _ngram_overlap(src, src) == 1.0


def test_ngram_overlap_distinct_is_low():
    src = "alpha beta gamma delta epsilon zeta eta theta"
    new = "one two three four five six seven eight"
    assert _ngram_overlap(new, src) == 0.0


def test_ngram_overlap_empty_is_zero():
    assert _ngram_overlap("", "anything here at all") == 0.0
    assert _ngram_overlap("too short", "x y z a b c", n=4) == 0.0


from pipeline.song_import import analyze_reference


class _FakeLLM:
    def __init__(self, payload):
        self._payload = payload
    def complete(self, prompt, system=None):
        import json
        return json.dumps(self._payload, ensure_ascii=False)


_DESC = {
    "genre": "Arabic pop ballad",
    "mood": "melancholic",
    "instrumentation": "oud, strings, light percussion",
    "language": "ar",
    "one_line_theme": "longing for a distant home",
    "section_structure": "Verse, Pre-Chorus, Chorus, Verse, Chorus, Bridge, Chorus",
}


def test_analyze_reference_returns_descriptors_and_transcript(tmp_path, monkeypatch):
    import pipeline.song_import as si
    audio = tmp_path / "reference.m4a"; audio.write_bytes(b"\x00")
    monkeypatch.setattr(si, "_detect_bpm", lambda p: 92.0)
    monkeypatch.setattr(si, "_transcribe", lambda p, language: "la la la one two three")
    desc, transcript = analyze_reference(audio, llm=_FakeLLM(_DESC), language="ar")
    assert desc["bpm"] == 92.0
    assert desc["one_line_theme"] == "longing for a distant home"
    assert transcript == "la la la one two three"


def test_analyze_reference_degrades_when_transcription_fails(tmp_path, monkeypatch):
    import pipeline.song_import as si
    audio = tmp_path / "reference.m4a"; audio.write_bytes(b"\x00")
    monkeypatch.setattr(si, "_detect_bpm", lambda p: 0.0)
    def boom(p, language):
        raise RuntimeError("whisper failed")
    monkeypatch.setattr(si, "_transcribe", boom)
    payload = dict(_DESC); payload["one_line_theme"] = None
    desc, transcript = analyze_reference(audio, llm=_FakeLLM(payload), language="ar")
    assert transcript == ""
    assert desc["one_line_theme"] is None


from pipeline.song_import import build_inspired_script, OVERLAP_THRESHOLD
import pipeline.song_import as si2
from pipeline.song_lyrics import SongScript


def _script(lyrics):
    return SongScript(title="t", lyrics=lyrics, style_prompt="pop, 90 BPM",
                      cover_prompt="c", language="ar",
                      art_direction="moonlit", scene_prompts=["a", "b"])


def test_build_inspired_script_passes_clean_output(monkeypatch):
    calls = {"n": 0}
    def fake_gen(**kw):
        calls["n"] += 1
        return _script("[Verse 1]\nfresh original words\n\n[Chorus]\nbrand new hook\n")
    monkeypatch.setattr(si2, "generate_song_script", fake_gen)
    s = build_inspired_script(
        llm=object(),
        analysis={"genre": "pop", "bpm": 90, "mood": "sad",
                  "instrumentation": "oud", "one_line_theme": "loss"},
        instruction="make it Gulf dialect",
        language="ar",
        transcript="totally different reference words here please",
    )
    assert "[Chorus]" in s.lyrics
    assert calls["n"] == 1   # no regeneration needed


def test_build_inspired_script_regenerates_on_near_copy(monkeypatch):
    src = "one two three four five six seven eight nine ten"
    outputs = [
        _script("one two three four five six seven eight nine ten"),  # near-copy
        _script("[Verse 1]\nwholly distinct alpha bravo charlie\n[Chorus]\ndelta echo\n"),
    ]
    calls = {"n": 0}
    def fake_gen(**kw):
        out = outputs[min(calls["n"], len(outputs) - 1)]
        calls["n"] += 1
        return out
    monkeypatch.setattr(si2, "generate_song_script", fake_gen)
    s = build_inspired_script(
        llm=object(),
        analysis={"genre": "pop", "bpm": 90, "mood": "sad",
                  "instrumentation": "oud", "one_line_theme": "loss"},
        instruction=None, language="ar", transcript=src,
    )
    assert calls["n"] == 2          # regenerated once after the near-copy
    assert "alpha bravo charlie" in s.lyrics


# --- faithful cover: keep the words --------------------------------------

class _TextLLM:
    """LLM stub whose complete() returns a fixed string (for sectioning)."""
    def __init__(self, text):
        self._text = text
    def complete(self, prompt, system=None):
        return self._text


def test_section_transcript_inserts_tags_and_strips_fences():
    from pipeline.song_import import section_transcript
    tagged = "[Verse 1]\nسطر اول\n[Chorus]\nلازمة"
    out = section_transcript(_TextLLM("```\n" + tagged + "\n```"),
                             "سطر اول لازمة", "ar")
    assert out == tagged


_COVER_ANALYSIS = {"genre": "pop", "bpm": 100, "mood": "warm",
                   "instrumentation": "oud", "one_line_theme": "home"}


def test_build_cover_script_keeps_the_words(monkeypatch):
    tagged = "[Verse 1]\noriginal line one two\n[Chorus]\nkeep these exact words"
    monkeypatch.setattr(si2, "section_transcript", lambda llm, t, lang: tagged)

    captured = {}
    def fake_gen(*, llm, theme, custom_lyrics, style_hint, language):
        captured["custom_lyrics"] = custom_lyrics
        return _script(custom_lyrics)   # custom_lyrics passthrough, like the real fn
    monkeypatch.setattr(si2, "generate_song_script", fake_gen)

    s = build_inspired_script  # noqa: F841  (ensure import side stays valid)
    from pipeline.song_import import build_cover_script
    out = build_cover_script(llm=object(), analysis=_COVER_ANALYSIS,
                             transcript="some sung words here",
                             instruction=None, language="ar")
    # The source words were kept verbatim (sectioned), not rewritten.
    assert captured["custom_lyrics"] == tagged
    assert out.lyrics == tagged


def test_build_cover_script_degrades_without_transcript(monkeypatch):
    from pipeline.song_import import build_cover_script
    called = {"inspired": 0, "section": 0}
    monkeypatch.setattr(si2, "section_transcript",
                        lambda *a, **k: called.__setitem__("section", called["section"] + 1) or "x")
    monkeypatch.setattr(si2, "build_inspired_script",
                        lambda **k: called.__setitem__("inspired", called["inspired"] + 1) or _script("[Chorus]\nz"))
    build_cover_script(llm=object(), analysis=_COVER_ANALYSIS,
                       transcript="   ", instruction=None, language="ar")
    assert called["inspired"] == 1 and called["section"] == 0


def test_build_cover_script_degrades_on_untaggable_lyrics(monkeypatch):
    from pipeline.song_import import build_cover_script
    # Sectioning returns lyrics with NO [Chorus] -> validate_section_tags fails
    # -> fall back to inspired words (melody still kept by the cover engine).
    monkeypatch.setattr(si2, "section_transcript",
                        lambda llm, t, lang: "just words no tags at all")
    used = {"inspired": 0}
    monkeypatch.setattr(si2, "build_inspired_script",
                        lambda **k: used.__setitem__("inspired", 1) or _script("[Chorus]\nz"))
    build_cover_script(llm=object(), analysis=_COVER_ANALYSIS,
                       transcript="real words", instruction=None, language="ar")
    assert used["inspired"] == 1


def test_ytdlp_opts_adds_proxy_when_env_set(monkeypatch):
    from pipeline.song_import import _ytdlp_opts
    monkeypatch.setenv("YTDLP_PROXY", "http://u:p@host:1080")
    opts = _ytdlp_opts("/tmp/out.m4a")
    assert opts["proxy"] == "http://u:p@host:1080"


def test_ytdlp_opts_no_proxy_when_unset(monkeypatch):
    from pipeline.song_import import _ytdlp_opts
    monkeypatch.delenv("YTDLP_PROXY", raising=False)
    opts = _ytdlp_opts("/tmp/out.m4a")
    assert "proxy" not in opts


def test_ytdlp_opts_cookiefile_only_when_provided():
    from pipeline.song_import import _ytdlp_opts
    assert _ytdlp_opts("/tmp/o.m4a", cookiefile="/tmp/c.txt")["cookiefile"] == "/tmp/c.txt"
    assert "cookiefile" not in _ytdlp_opts("/tmp/o.m4a")


def test_ytdlp_download_writes_cookies_to_tempfile(tmp_path, monkeypatch):
    # YTDLP_COOKIES body must be written to a temp cookiefile that exists at
    # download time, and proxy must be wired — without invoking real yt-dlp.
    import os
    import sys
    import types
    captured = {}

    class _FakeYDL:
        def __init__(self, opts):
            captured["opts"] = opts
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def download(self, urls):
            cf = captured["opts"].get("cookiefile")
            captured["cookiefile_existed"] = bool(cf) and os.path.exists(cf)
            captured["cookiefile_body"] = open(cf, encoding="utf-8").read() if cf else None

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=_FakeYDL))
    monkeypatch.setenv("YTDLP_PROXY", "socks5://h:1")
    monkeypatch.setenv("YTDLP_COOKIES", "# Netscape HTTP Cookie File\nsynthetic-cookie-line")
    si._ytdlp_download("https://youtu.be/x", str(tmp_path / "o.m4a"))
    assert captured["opts"]["proxy"] == "socks5://h:1"
    assert captured["cookiefile_existed"] is True
    assert "synthetic-cookie-line" in captured["cookiefile_body"]


# --- metadata fallback ------------------------------------------------------

class _MetaFakeLLM:
    def __init__(self, payload):
        self._payload = payload
    def complete(self, prompt, system=None):
        import json
        return json.dumps(self._payload, ensure_ascii=False)


_META_DESC = {
    "genre": "Arabic pop", "mood": "nostalgic", "instrumentation": "oud, strings",
    "language": "ar", "one_line_theme": "missing an old friend",
    "section_structure": "Verse, Chorus, Verse, Chorus",
}


def test_yt_video_id_parses_url_shapes():
    from pipeline.song_import import _yt_video_id
    assert _yt_video_id("https://www.youtube.com/watch?v=abc123def") == "abc123def"
    assert _yt_video_id("https://youtu.be/abc123def") == "abc123def"
    assert _yt_video_id("https://youtube.com/shorts/abc123def") == "abc123def"
    assert _yt_video_id("https://example.com/nope") is None


def test_fetch_youtube_metadata_needs_api_key(monkeypatch):
    from pipeline.song_import import fetch_youtube_metadata, ImportFetchError
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(ImportFetchError):
        fetch_youtube_metadata("https://youtu.be/abc123def")


def test_fetch_youtube_metadata_returns_title_desc(monkeypatch):
    from pipeline.song_import import fetch_youtube_metadata
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    monkeypatch.setattr(si, "_youtube_api_metadata",
                        lambda vid, key: {"title": "A Song", "description": "desc"})
    meta = fetch_youtube_metadata("https://youtu.be/abc123def")
    assert meta == {"title": "A Song", "description": "desc"}


def test_analyze_from_metadata_distills_descriptors_no_transcript():
    from pipeline.song_import import analyze_from_metadata
    desc, transcript = analyze_from_metadata(
        {"title": "A Song", "description": "about an old friend"},
        llm=_MetaFakeLLM(_META_DESC), language="ar")
    assert desc["one_line_theme"] == "missing an old friend"
    assert desc["bpm"] == 0.0
    assert transcript == ""   # metadata path never has a transcript


def test_analyze_youtube_uses_audio_when_download_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(si, "download_audio", lambda url, d: d / "reference.m4a")
    monkeypatch.setattr(si, "analyze_reference",
                        lambda audio, *, llm, language: ({"src": "audio"}, "transcript"))
    monkeypatch.setattr(si, "fetch_youtube_metadata",
                        lambda url: (_ for _ in ()).throw(AssertionError("should not fall back")))
    desc, transcript = si.analyze_youtube("https://youtu.be/abc123def", tmp_path,
                                          llm=object(), language="ar")
    assert desc == {"src": "audio"} and transcript == "transcript"


def test_analyze_youtube_falls_back_to_metadata_when_blocked(tmp_path, monkeypatch):
    from pipeline.song_import import ImportFetchError
    def blocked(url, d):
        raise ImportFetchError("blocked")
    monkeypatch.setattr(si, "download_audio", blocked)
    monkeypatch.setattr(si, "fetch_youtube_metadata",
                        lambda url: {"title": "A Song", "description": "d"})
    monkeypatch.setattr(si, "analyze_from_metadata",
                        lambda meta, *, llm, language: ({"src": "metadata"}, ""))
    desc, transcript = si.analyze_youtube("https://youtu.be/abc123def", tmp_path,
                                          llm=object(), language="ar")
    assert desc == {"src": "metadata"} and transcript == ""
