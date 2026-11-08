"""Two-ball chair kinematics: both BOLTs must agree for every command (they drive in tandem)."""
from app.chair_drive import ball_commands, yaw_rate_deg

M = 50


def test_forward_both_balls_same():
    assert ball_commands(1, 0, 0, 0, M) == [(0, M), (0, M)]


def test_reverse_uses_negative_speed_not_heading_flip():
    assert ball_commands(-1, 0, 0, 0, M) == [(0, -M), (0, -M)]


def test_turn_left_left_ball_back_right_ball_forward():
    (hl, sl), (hr, sr) = ball_commands(0, 0, 1, 0, M)
    assert (hl, hr) == (0, 0)
    assert sl == -M and sr == M


def test_turn_right_is_mirror():
    (_, sl), (_, sr) = ball_commands(0, 0, -1, 0, M)
    assert sl == M and sr == -M


def test_slide_right_and_left():
    assert ball_commands(0, 1, 0, 0, M) == [(90, M), (90, M)]
    assert ball_commands(0, -1, 0, 0, M) == [(270, M), (270, M)]


def test_stop_keeps_heading_zero_speed():
    assert [s for _, s in ball_commands(0, 0, 0, 37, M)] == [0, 0]


def test_heading_follows_chair_after_turn():
    # after the chair has turned 30 deg clockwise, "forward" must be 30 deg in the balls' world frame
    assert ball_commands(1, 0, 0, 30, M) == [(30, M), (30, M)]


def test_speed_never_exceeds_cap():
    for v, u, w in [(1, 1, 0), (1, 0, 1), (-1, -1, -1)]:
        assert all(abs(s) <= M for _, s in ball_commands(v, u, w, 0, M))


def test_left_turn_reduces_heading():
    assert yaw_rate_deg(1, M) < 0 < yaw_rate_deg(-1, M)
