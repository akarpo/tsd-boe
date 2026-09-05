# Splitting two interleaved voices out of one diarization cluster (2026-09-01)

These are the session's working scripts, kept as the record of how cluster E
(Zendler + Melton, merged for the whole evening) was separated. They are not a
tool: paths to the scratchpad wav, the transcript JSON and the mp4 are hardcoded,
and the seeds are this meeting's timestamps. The method is written up in
`docs/TRANSCRIPTION.md` ("Two trustees, one cluster, interleaved all evening").

Order they ran in:

1. `grab_frames.py` — one 320-px frame per utterance ≥2.5 s in the trustee clusters
   (`ffmpeg -ss`), so a camera-on-speaker check is a thumbnail comparison.
2. `preset_labels.py` — k-means the thumbnails into camera presets and label the
   presets from a handful of full-size frames inspected by eye. Coarse; it
   confirmed the ECAPA seeds, it did not decide utterances.
3. `embed_ecapa.py` / `embed_short.py` — speechbrain ECAPA-TDNN
   (`spkrec-ecapa-voxceleb`) embeddings per utterance (≥1 s, then the sub-second
   interjections with 0.1 s padding). resemblyzer was tried first and rejected:
   every speaker centroid sat within cosine 0.9 of every other.
4. `ecapa_2way.py` — seeded two-way assignment of cluster E (Stephanie / Audra
   seeds = turns where the camera is on the speaker), with the other named
   clusters' centroids as sinks so DiPilato's and Philippart's turns come out too.
   Accept a sink only for turns ≥3 s with margin ≥0.15.
5. `refine.py` — kNN sanity checks on the ambiguous turns and a 4-s sliding window
   (hop 2 s) over every long turn; a run of one speaker followed by a run of the
   other marks a mid-utterance handoff, cut at the word boundary
   (`utterance_splits` in `../speakers.json`).

Environment: a Python 3.9 venv with `speechbrain`, `torch`, `soundfile`, `numpy`,
`scipy`, `Pillow`; the model downloads from Hugging Face without a token.
