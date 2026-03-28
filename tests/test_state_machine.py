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


class TestGuards:
    def test_guard_allows_transition(self) -> None:
        sm = StateMachine(
            states=["pending", "confirmed"],
            initial="pending",
            transitions=[("pending", "confirmed", "confirm")],
        )
        sm.add_transition("pending", "confirmed", "confirm", guard=lambda ctx: ctx.get("authorized", False))
        sm.trigger("confirm", context={"authorized": True})
        assert sm.state == "confirmed"

    def test_guard_rejects_transition(self) -> None:
        sm = StateMachine(
            states=["pending", "confirmed"],
            initial="pending",
            transitions=[("pending", "confirmed", "confirm")],
        )
        sm.add_transition("pending", "confirmed", "confirm", guard=lambda ctx: ctx.get("authorized", False))
        with pytest.raises(InvalidTransitionError):
            sm.trigger("confirm", context={"authorized": False})
        assert sm.state == "pending"

    def test_guard_with_no_context_gets_empty_dict(self) -> None:
        received: list[dict] = []
        sm = StateMachine(
            states=["a", "b"],
            initial="a",
            transitions=[("a", "b", "go")],
        )
        sm.add_transition("a", "b", "go", guard=lambda ctx: (received.append(ctx) or True))  # type: ignore[arg-type]
        sm.trigger("go")
        assert received == [{}]

    def test_multiple_guards_all_must_pass(self) -> None:
        sm = StateMachine(
            states=["a", "b"],
            initial="a",
            transitions=[("a", "b", "go")],
        )
        sm.add_transition("a", "b", "go", guard=lambda ctx: True)
        sm.add_transition("a", "b", "go", guard=lambda ctx: False)
        with pytest.raises(InvalidTransitionError):
            sm.trigger("go")


class TestContext:
    def test_trigger_with_context(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm", context={"user": "alice"})
        assert sm.state == "confirmed"

    def test_trigger_without_context(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        assert sm.state == "confirmed"
