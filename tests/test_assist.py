"""Sound/vision assist helpers. The YAMNet model test only runs where tensorflow-hub is installed (not CI)."""
import numpy as np
import pytest

from app import sound_assist as sa
from app import vision_assist as va


def test_alert_table_maps_key_classes():
    names = ["Speech", "Smoke detector, smoke alarm", "Doorbell", "Knock", "Siren", "Car alarm", "Music"]
    t = sa.alert_table(names)
    assert t[0] is None and t[6] is None
    assert t[1][0] == "SMOKE ALARM"
    assert t[2][0] == "DOORBELL"
    assert t[3][0] == "KNOCKING"
    assert t[4][0] == "SIREN"
    assert t[5][0] == "CAR ALARM"


def test_pick_alert_respects_threshold_and_ignores_unwatched_classes():
    names = ["Speech", "Doorbell", "Siren"]
    table = sa.alert_table(names)
    assert sa.pick_alert(np.array([0.9, 0.2, 0.1]), table, 0.3) is None       # loud speech only
    assert sa.pick_alert(np.array([0.9, 0.5, 0.1]), table, 0.3)[0] == "DOORBELL"
    assert sa.pick_alert(np.array([0.1, 0.25, 0.1]), table, 0.3) is None     # below threshold


def test_resample_to_16k_keeps_duration():
    x = np.zeros(48000, np.float32)
    assert len(sa.to_16k(x, 48000)) == 16000


def test_vision_direction():
    assert va.where(10, 300) == "on the left"
    assert va.where(150, 300) == "ahead"
    assert va.where(290, 300) == "on the right"


@pytest.mark.slow
def test_yamnet_hears_a_sine_tone():
    pytest.importorskip("tensorflow_hub")
    model, names = sa.load_yamnet()
    t = np.arange(sa.SR * 2) / sa.SR
    s = sa.classify(model, 0.5 * np.sin(2 * np.pi * 1000 * t))
    top = [names[i] for i in np.argsort(-s)[:3]]
    assert any("sine" in n.lower() or "beep" in n.lower() or "tone" in n.lower() for n in top), top
