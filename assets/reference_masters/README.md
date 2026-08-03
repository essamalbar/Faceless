# Reference masters (Matchering)

Drop ONE professionally-mastered, **owned or royalty-free (CC0)** reference
track per genre family here, named `<genre_key>.wav`, where `<genre_key>` is a
key from `pipeline/song_style.py:GENRE_RECIPES` (e.g. `arabic_pop.wav`,
`khaleeji.wav`, `arabic_ballad.wav`, `pop.wav`, ...).

Matchering matches each Suno take's spectral balance + loudness to the
reference. If a genre has no reference here, mastering falls back to the free
ffmpeg tonal chain automatically (`pipeline/mastering.py`).

Do NOT commit copyrighted commercial tracks.
