"""Live SSVEP picker: decoder maths on synthetic signals (no headset, no data files)."""
import numpy as np

from app.ssvep_live import FS, TARGETS, Decider, Pipeline, canon, cca_scores, freqs_for

CH = ["Fp1", "Fp2", "F9", "F7", "F3", "Fz", "F4", "F8", "F10", "M1", "t7", "c3", "c4", "t8", "M2", "cz",
      "p7", "p3", "pz", "p4", "p8", "oz", "o1", "o2"]


def test_flicker_frequencies_match_recorder_at_60hz():
    f = freqs_for(60)
    assert abs(f["Bathroom"] - 12.0) < 1e-9 and abs(f["Kitchen"] - 60 / 7) < 1e-9
    assert abs(f["Bed"] - 7.5) < 1e-9 and abs(f["Door"] - 60 / 9) < 1e-9


def test_flicker_frequencies_hold_at_120hz():
    f60, f120 = freqs_for(60), freqs_for(120)
    assert all(abs(f60[t] - f120[t]) < 1e-9 for t in TARGETS)


def test_channel_names_are_normalised():
    assert canon(["oz", "O1", "cz", "p7"]) == ["Oz", "O1", "Cz", "P7"]


def test_cca_picks_the_flickering_target():
    rng = np.random.default_rng(0)
    freqs = freqs_for(60)
    t = np.arange(int(4 * FS)) / FS
    for target in TARGETS:
        f = freqs[target]
        X = rng.normal(0, 1, (8, t.size)) + 0.4 * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) \
            + 0.2 * np.sin(2 * np.pi * 2 * f * t)
        assert TARGETS[int(np.argmax(cca_scores(X, freqs)))] == target


def test_pipeline_runs_causally_in_chunks():
    rng = np.random.default_rng(1)
    X = rng.normal(0, 20, (2000, len(CH))) + 50000           # big DC offset like the eego stream
    p_whole = Pipeline(CH, ["Cz", "C4", "M2"])
    p_chunk = Pipeline(CH, ["Cz", "C4", "M2"])
    whole = p_whole.process(X)
    parts = np.concatenate([p_chunk.process(X[i:i + 25]) for i in range(0, 2000, 25)], axis=1)
    assert whole.shape == (8, 2000)
    assert np.allclose(whole, parts)                         # same result whether data arrives at once or live
    assert abs(whole[:, 500:].mean()) < 5                    # DC removed by the band-pass


def test_decider_needs_two_agreeing_windows():
    d = Decider()
    assert d.update("Kitchen") is None
    assert d.update("Bed") is None
    assert d.update("Bed") == "Bed"
    d.reset()
    assert d.update("Bed") is None
