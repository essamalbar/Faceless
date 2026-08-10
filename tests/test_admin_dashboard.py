from __future__ import annotations

from pipeline.api import (
    _cancel_run_impl,
    _cancel_song_impl,
    _delete_run_impl,
    _delete_song_impl,
)


def test_impls_importable():
    for fn in (_cancel_run_impl, _cancel_song_impl,
               _delete_run_impl, _delete_song_impl):
        assert callable(fn)
