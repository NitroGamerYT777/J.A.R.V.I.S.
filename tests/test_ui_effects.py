from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from jarvis.ui.effects import MotionClock, approach, blend


def test_color_blending_is_bounded_and_exact():
    assert blend("#000000", "#ffffff", .5) == "#808080"
    assert blend("#123456", "#ffffff", -1) == "#123456"
    assert blend("#123456", "#abcdef", 2) == "#abcdef"


def test_easing_does_not_overshoot_and_is_frame_rate_independent():
    assert 0 < approach(0, 1, .033) < 1
    assert 0 < approach(1, 0, .033) < 1
    assert approach(0, 1, .066) == pytest.approx(approach(approach(0, 1, .033), 1, .033))
    assert approach(.9999, 1, .033) == 1


def clock_and_root():
    root = Mock()
    root.winfo_viewable.return_value = True
    root.after.return_value = "timer"
    return MotionClock(root), root


def test_one_timer_is_shared_for_many_listeners():
    clock, root = clock_and_root()
    for _ in range(40):
        clock.subscribe(Mock(), Mock())
    assert root.after.call_count == 1
    assert len(clock.listeners) == 40


def test_destroyed_widget_is_removed_and_hidden_widgets_do_not_animate():
    clock, _ = clock_and_root()
    widget, callback = Mock(), Mock()
    widget.winfo_viewable.return_value = False
    clock.subscribe(widget, callback)
    clock._tick()
    callback.assert_not_called()
    on_destroy = widget.bind.call_args.args[1]
    on_destroy(SimpleNamespace(widget=widget))
    assert not clock.listeners


def test_reduced_motion_freezes_time_but_allows_static_hover_feedback():
    clock, _ = clock_and_root()
    callback = Mock()
    clock.subscribe(Mock(), callback)
    clock.set_enabled(False)
    before = clock.elapsed
    clock._tick()
    assert clock.elapsed == before
    assert callback.call_args.args[2] is False


def test_minimized_root_suspends_chrome_and_close_cancels_timer():
    clock, root = clock_and_root()
    callback = Mock()
    clock.subscribe(Mock(), callback)
    root.winfo_viewable.return_value = False
    clock._tick()
    callback.assert_not_called()
    clock.close()
    assert clock.closed
    assert not clock.listeners
    root.after_cancel.assert_called_once_with("timer")


def test_one_bad_effect_does_not_break_other_widgets():
    clock, root = clock_and_root()
    callback = Mock()
    clock.subscribe(Mock(), Mock(side_effect=RuntimeError("effect failed")))
    clock.subscribe(Mock(), callback)
    clock._tick()
    callback.assert_called_once()
    root.report_callback_exception.assert_called_once()
