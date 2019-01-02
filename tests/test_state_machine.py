"""Tests for philiprehberger_state_machine."""

from __future__ import annotations

import pytest

from philiprehberger_state_machine import InvalidTransitionError, StateMachine


def _make_order_machine() -> StateMachine:
    """Create a simple order-flow state machine for testing."""
    return StateMachine(
        states=["pending", "confirmed", "shipped", "delivered", "cancelled"],
        initial="pending",
        transitions=[
            ("pending", "confirmed", "confirm"),
            ("confirmed", "shipped", "ship"),
            ("shipped", "delivered", "deliver"),
            ("pending", "cancelled", "cancel"),
            ("confirmed", "cancelled", "cancel"),
        ],
    )


class TestBasicTransition:
    def test_initial_state(self) -> None:
        sm = _make_order_machine()
        assert sm.state == "pending"

    def test_single_transition(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        assert sm.state == "confirmed"

    def test_chained_transitions(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        sm.trigger("ship")
        sm.trigger("deliver")
        assert sm.state == "delivered"


class TestInvalidTransition:
    def test_raises_on_invalid_event(self) -> None:
        sm = _make_order_machine()
        with pytest.raises(InvalidTransitionError) as exc_info:
            sm.trigger("ship")
        assert exc_info.value.state == "pending"
        assert exc_info.value.event == "ship"

    def test_raises_on_unknown_event(self) -> None:
        sm = _make_order_machine()
        with pytest.raises(InvalidTransitionError):
            sm.trigger("nonexistent")


class TestCan:
    def test_can_returns_true(self) -> None:
        sm = _make_order_machine()
        assert sm.can("confirm") is True

    def test_can_returns_false(self) -> None:
        sm = _make_order_machine()
        assert sm.can("ship") is False

    def test_can_updates_after_transition(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        assert sm.can("ship") is True
        assert sm.can("confirm") is False


class TestHistory:
    def test_history_starts_empty(self) -> None:
        sm = _make_order_machine()
        assert sm.history == []

    def test_history_tracks_past_states(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        sm.trigger("ship")
        assert sm.history == ["pending", "confirmed"]

    def test_history_returns_copy(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        history = sm.history
        history.append("fake")
        assert sm.history == ["pending"]


class TestCallbacks:
    def test_on_enter_fires(self) -> None:
        sm = _make_order_machine()
        calls: list[tuple[str, str]] = []
        sm.on_enter("confirmed", lambda state, event: calls.append((state, event)))
        sm.trigger("confirm")
        assert calls == [("confirmed", "confirm")]

    def test_on_exit_fires(self) -> None:
        sm = _make_order_machine()
        calls: list[tuple[str, str]] = []
        sm.on_exit("pending", lambda state, event: calls.append((state, event)))
        sm.trigger("confirm")
        assert calls == [("pending", "confirm")]

    def test_multiple_callbacks(self) -> None:
        sm = _make_order_machine()
        calls: list[str] = []
        sm.on_enter("confirmed", lambda s, e: calls.append("first"))
        sm.on_enter("confirmed", lambda s, e: calls.append("second"))
        sm.trigger("confirm")
        assert calls == ["first", "second"]


class TestReset:
    def test_reset_restores_initial_state(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        sm.trigger("ship")
        sm.reset()
        assert sm.state == "pending"

    def test_reset_clears_history(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        sm.reset()
        assert sm.history == []
