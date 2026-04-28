"""Tests for philiprehberger_state_machine."""

from __future__ import annotations

import time

import pytest

from philiprehberger_state_machine import (
    InvalidTransitionError,
    StateMachine,
    TransitionRecord,
)


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


class TestTransitionHistory:
    def test_transition_history_starts_empty(self) -> None:
        sm = _make_order_machine()
        assert sm.transition_history == []

    def test_transition_history_records_transitions(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        sm.trigger("ship")
        records = sm.transition_history
        assert len(records) == 2

        assert records[0].from_state == "pending"
        assert records[0].to_state == "confirmed"
        assert records[0].event == "confirm"

        assert records[1].from_state == "confirmed"
        assert records[1].to_state == "shipped"
        assert records[1].event == "ship"

    def test_transition_history_has_timestamps(self) -> None:
        sm = _make_order_machine()
        before = time.time()
        sm.trigger("confirm")
        after = time.time()

        records = sm.transition_history
        assert len(records) == 1
        assert before <= records[0].timestamp <= after

    def test_transition_history_timestamps_are_monotonic(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        sm.trigger("ship")
        records = sm.transition_history
        assert records[0].timestamp <= records[1].timestamp

    def test_transition_history_returns_copy(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        history = sm.transition_history
        assert len(history) == 1
        history.append(TransitionRecord("x", "y", "z", 0.0))
        assert len(sm.transition_history) == 1

    def test_transition_record_is_frozen(self) -> None:
        record = TransitionRecord("a", "b", "go", 1234.0)
        with pytest.raises(AttributeError):
            record.from_state = "c"  # type: ignore[misc]

    def test_transition_history_cleared_on_reset(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        assert len(sm.transition_history) == 1
        sm.reset()
        assert sm.transition_history == []


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

    def test_exit_fires_before_enter(self) -> None:
        sm = _make_order_machine()
        calls: list[str] = []
        sm.on_exit("pending", lambda s, e: calls.append("exit"))
        sm.on_enter("confirmed", lambda s, e: calls.append("enter"))
        sm.trigger("confirm")
        assert calls == ["exit", "enter"]


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

    def test_reset_clears_transition_history(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        sm.reset()
        assert sm.transition_history == []


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


class TestWildcardTransitions:
    def test_wildcard_transition_from_any_state(self) -> None:
        sm = StateMachine(
            states=["idle", "running", "paused", "error"],
            initial="idle",
            transitions=[
                ("idle", "running", "start"),
                ("running", "paused", "pause"),
                ("*", "error", "fail"),
            ],
        )
        # Fail from idle
        sm.trigger("fail")
        assert sm.state == "error"

    def test_wildcard_from_non_initial_state(self) -> None:
        sm = StateMachine(
            states=["idle", "running", "paused", "error"],
            initial="idle",
            transitions=[
                ("idle", "running", "start"),
                ("running", "paused", "pause"),
                ("*", "error", "fail"),
            ],
        )
        sm.trigger("start")
        assert sm.state == "running"
        sm.trigger("fail")
        assert sm.state == "error"

    def test_wildcard_can_returns_true(self) -> None:
        sm = StateMachine(
            states=["a", "b", "error"],
            initial="a",
            transitions=[
                ("a", "b", "go"),
                ("*", "error", "fail"),
            ],
        )
        assert sm.can("fail") is True
        sm.trigger("go")
        assert sm.can("fail") is True

    def test_wildcard_with_add_transition(self) -> None:
        sm = StateMachine(
            states=["a", "b", "reset_state"],
            initial="a",
            transitions=[("a", "b", "go")],
        )
        sm.add_transition("*", "reset_state", "emergency")
        sm.trigger("go")
        assert sm.state == "b"
        sm.trigger("emergency")
        assert sm.state == "reset_state"

    def test_wildcard_records_actual_from_state(self) -> None:
        sm = StateMachine(
            states=["a", "b", "error"],
            initial="a",
            transitions=[
                ("a", "b", "go"),
                ("*", "error", "fail"),
            ],
        )
        sm.trigger("go")
        sm.trigger("fail")
        records = sm.transition_history
        assert records[1].from_state == "b"
        assert records[1].to_state == "error"

    def test_wildcard_fires_callbacks(self) -> None:
        sm = StateMachine(
            states=["a", "b", "error"],
            initial="a",
            transitions=[
                ("a", "b", "go"),
                ("*", "error", "fail"),
            ],
        )
        calls: list[tuple[str, str]] = []
        sm.on_exit("b", lambda s, e: calls.append(("exit", s)))
        sm.on_enter("error", lambda s, e: calls.append(("enter", s)))
        sm.trigger("go")
        sm.trigger("fail")
        assert calls == [("exit", "b"), ("enter", "error")]

    def test_wildcard_with_guard(self) -> None:
        sm = StateMachine(
            states=["a", "b", "error"],
            initial="a",
            transitions=[("a", "b", "go")],
        )
        sm.add_transition("*", "error", "fail", guard=lambda ctx: ctx.get("critical", False))
        sm.trigger("go")
        with pytest.raises(InvalidTransitionError):
            sm.trigger("fail", context={"critical": False})
        assert sm.state == "b"
        sm.trigger("fail", context={"critical": True})
        assert sm.state == "error"

    def test_exact_match_preferred_over_wildcard(self) -> None:
        """Exact state match should be tried before wildcard."""
        sm = StateMachine(
            states=["a", "b", "c"],
            initial="a",
            transitions=[
                ("a", "b", "go"),
                ("*", "c", "go"),
            ],
        )
        sm.trigger("go")
        # Exact match (a -> b) should win over wildcard (* -> c)
        assert sm.state == "b"

    def test_exact_match_preferred_even_when_wildcard_first(self) -> None:
        """Exact match wins regardless of definition order."""
        sm = StateMachine(
            states=["a", "b", "c"],
            initial="a",
            transitions=[
                ("*", "c", "go"),
                ("a", "b", "go"),
            ],
        )
        sm.trigger("go")
        assert sm.state == "b"

    def test_wildcard_in_constructor_validation(self) -> None:
        """Wildcard source should not fail validation."""
        sm = StateMachine(
            states=["a", "b"],
            initial="a",
            transitions=[("*", "b", "reset")],
        )
        sm.trigger("reset")
        assert sm.state == "b"

    def test_wildcard_in_dot_export(self) -> None:
        sm = StateMachine(
            states=["a", "b", "error"],
            initial="a",
            transitions=[
                ("a", "b", "go"),
                ("*", "error", "fail"),
            ],
        )
        dot = sm.to_dot()
        # Wildcard should expand to edges from all non-target states
        assert '"a" -> "error" [label="fail"]' in dot
        assert '"b" -> "error" [label="fail"]' in dot

    def test_wildcard_in_mermaid_export(self) -> None:
        sm = StateMachine(
            states=["a", "b", "error"],
            initial="a",
            transitions=[
                ("a", "b", "go"),
                ("*", "error", "fail"),
            ],
        )
        mermaid = sm.to_mermaid()
        assert "a --> error : fail" in mermaid
        assert "b --> error : fail" in mermaid


class TestVisualization:
    def test_to_dot_output(self) -> None:
        sm = StateMachine(
            states=["a", "b"],
            initial="a",
            transitions=[("a", "b", "go")],
        )
        dot = sm.to_dot()
        assert "digraph StateMachine" in dot
        assert '"a" [shape=doublecircle]' in dot
        assert '"b" [shape=circle]' in dot
        assert '"a" -> "b" [label="go"]' in dot

    def test_to_mermaid_output(self) -> None:
        sm = StateMachine(
            states=["a", "b"],
            initial="a",
            transitions=[("a", "b", "go")],
        )
        mermaid = sm.to_mermaid()
        assert "stateDiagram-v2" in mermaid
        assert "[*] --> a" in mermaid
        assert "a --> b : go" in mermaid


class TestSnapshot:
    def test_snapshot_captures_state_and_history(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        snap = sm.snapshot()
        assert snap == {"state": "confirmed", "history": ["pending"]}

    def test_restore_from_snapshot(self) -> None:
        sm = _make_order_machine()
        sm.trigger("confirm")
        snap = sm.snapshot()
        sm.trigger("ship")
        sm.restore(snap)
        assert sm.state == "confirmed"
        assert sm.history == ["pending"]

    def test_restore_invalid_state_raises(self) -> None:
        sm = _make_order_machine()
        with pytest.raises(ValueError, match="not in states"):
            sm.restore({"state": "nonexistent", "history": []})


class TestOnTransition:
    def test_listener_receives_from_to_event_context(self) -> None:
        sm = _make_order_machine()
        calls: list[tuple[str, str, str | None, dict | None]] = []
        sm.on_transition(lambda fr, to, ev, ctx: calls.append((fr, to, ev, ctx)))
        sm.trigger("confirm", context={"user": "alice"})
        assert calls == [("pending", "confirmed", "confirm", {"user": "alice"})]

    def test_listener_receives_none_context_when_omitted(self) -> None:
        sm = _make_order_machine()
        calls: list[tuple[str, str, str | None, dict | None]] = []
        sm.on_transition(lambda fr, to, ev, ctx: calls.append((fr, to, ev, ctx)))
        sm.trigger("confirm")
        assert calls == [("pending", "confirmed", "confirm", None)]

    def test_multiple_listeners_fire_in_registration_order(self) -> None:
        sm = _make_order_machine()
        order: list[str] = []
        sm.on_transition(lambda fr, to, ev, ctx: order.append("first"))
        sm.on_transition(lambda fr, to, ev, ctx: order.append("second"))
        sm.on_transition(lambda fr, to, ev, ctx: order.append("third"))
        sm.trigger("confirm")
        assert order == ["first", "second", "third"]

    def test_unsubscribe_closure_removes_listener(self) -> None:
        sm = _make_order_machine()
        calls_a: list[str] = []
        calls_b: list[str] = []
        unsubscribe_a = sm.on_transition(
            lambda fr, to, ev, ctx: calls_a.append(to)
        )
        sm.on_transition(lambda fr, to, ev, ctx: calls_b.append(to))

        sm.trigger("confirm")
        assert calls_a == ["confirmed"]
        assert calls_b == ["confirmed"]

        unsubscribe_a()
        sm.trigger("ship")
        # Only listener B should still be active
        assert calls_a == ["confirmed"]
        assert calls_b == ["confirmed", "shipped"]

    def test_unsubscribe_closure_idempotent(self) -> None:
        sm = _make_order_machine()
        unsubscribe = sm.on_transition(lambda fr, to, ev, ctx: None)
        unsubscribe()
        # Calling again should not raise
        unsubscribe()

    def test_remove_transition_listener_returns_true_when_removed(self) -> None:
        sm = _make_order_machine()

        def listener(fr: str, to: str, ev: str | None, ctx: dict | None) -> None:
            pass

        sm.on_transition(listener)
        assert sm.remove_transition_listener(listener) is True

    def test_remove_transition_listener_returns_false_when_absent(self) -> None:
        sm = _make_order_machine()

        def listener(fr: str, to: str, ev: str | None, ctx: dict | None) -> None:
            pass

        assert sm.remove_transition_listener(listener) is False

    def test_remove_transition_listener_only_removes_that_listener(self) -> None:
        sm = _make_order_machine()
        calls_a: list[str] = []
        calls_b: list[str] = []

        def listener_a(fr: str, to: str, ev: str | None, ctx: dict | None) -> None:
            calls_a.append(to)

        def listener_b(fr: str, to: str, ev: str | None, ctx: dict | None) -> None:
            calls_b.append(to)

        sm.on_transition(listener_a)
        sm.on_transition(listener_b)

        sm.remove_transition_listener(listener_a)

        sm.trigger("confirm")
        assert calls_a == []
        assert calls_b == ["confirmed"]

    def test_listener_fires_after_on_enter_and_on_exit(self) -> None:
        sm = _make_order_machine()
        events: list[str] = []
        sm.on_exit("pending", lambda s, e: events.append("exit"))
        sm.on_enter("confirmed", lambda s, e: events.append("enter"))
        sm.on_transition(lambda fr, to, ev, ctx: events.append("transition"))
        sm.trigger("confirm")
        assert events == ["exit", "enter", "transition"]

    def test_listener_does_not_fire_when_guard_rejects(self) -> None:
        sm = StateMachine(
            states=["pending", "confirmed"],
            initial="pending",
            transitions=[("pending", "confirmed", "confirm")],
        )
        sm.add_transition(
            "pending",
            "confirmed",
            "confirm",
            guard=lambda ctx: ctx.get("authorized", False),
        )
        calls: list[tuple[str, str]] = []
        sm.on_transition(lambda fr, to, ev, ctx: calls.append((fr, to)))

        with pytest.raises(InvalidTransitionError):
            sm.trigger("confirm", context={"authorized": False})

        assert calls == []
        assert sm.state == "pending"

        # Sanity: when the guard passes, the listener does fire
        sm.trigger("confirm", context={"authorized": True})
        assert calls == [("pending", "confirmed")]

    def test_listener_does_not_fire_on_unknown_event(self) -> None:
        sm = _make_order_machine()
        calls: list[str] = []
        sm.on_transition(lambda fr, to, ev, ctx: calls.append(to))
        with pytest.raises(InvalidTransitionError):
            sm.trigger("nonexistent")
        assert calls == []

    def test_listener_fires_on_wildcard_transition(self) -> None:
        sm = StateMachine(
            states=["a", "b", "error"],
            initial="a",
            transitions=[
                ("a", "b", "go"),
                ("*", "error", "fail"),
            ],
        )
        calls: list[tuple[str, str, str | None]] = []
        sm.on_transition(lambda fr, to, ev, ctx: calls.append((fr, to, ev)))
        sm.trigger("go")
        sm.trigger("fail")
        assert calls == [("a", "b", "go"), ("b", "error", "fail")]

    def test_snapshot_does_not_capture_listeners(self) -> None:
        """Listeners are runtime-only — snapshot/restore preserves the
        current listener registrations (not the snapshot's listener set)."""
        sm = _make_order_machine()
        calls: list[str] = []
        sm.on_transition(lambda fr, to, ev, ctx: calls.append(to))
        snap = sm.snapshot()
        # The snapshot dict is a plain {state, history} pair only
        assert set(snap.keys()) == {"state", "history"}

        # Registering more listeners after snapshot, then restore, should not
        # roll back the listener set
        calls_b: list[str] = []
        sm.on_transition(lambda fr, to, ev, ctx: calls_b.append(to))
        sm.restore(snap)

        sm.trigger("confirm")
        # Both listeners (registered before AND after snapshot) still fire
        assert calls == ["confirmed"]
        assert calls_b == ["confirmed"]


class TestConstructorValidation:
    def test_empty_states_raises(self) -> None:
        with pytest.raises(ValueError, match="states must not be empty"):
            StateMachine(states=[], initial="a", transitions=[])

    def test_invalid_initial_raises(self) -> None:
        with pytest.raises(ValueError, match="not in states"):
            StateMachine(states=["a"], initial="b", transitions=[])

    def test_invalid_from_state_raises(self) -> None:
        with pytest.raises(ValueError, match="from_state"):
            StateMachine(
                states=["a", "b"],
                initial="a",
                transitions=[("nonexistent", "b", "go")],
            )

    def test_invalid_to_state_raises(self) -> None:
        with pytest.raises(ValueError, match="to_state"):
            StateMachine(
                states=["a", "b"],
                initial="a",
                transitions=[("a", "nonexistent", "go")],
            )
