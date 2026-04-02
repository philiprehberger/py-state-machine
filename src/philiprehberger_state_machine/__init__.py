"""Lightweight finite state machine with guards, callbacks, and visualization."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

__all__ = ["InvalidTransitionError", "StateMachine", "TransitionRecord"]


class InvalidTransitionError(Exception):
    """Raised when a transition is not valid for the current state and event."""

    def __init__(self, state: str, event: str) -> None:
        self.state = state
        self.event = event
        super().__init__(
            f"No transition for event '{event}' from state '{state}'"
        )


@dataclass(frozen=True)
class TransitionRecord:
    """Immutable record of a single state transition with timestamp."""

    from_state: str
    to_state: str
    event: str
    timestamp: float


class _TimeoutEntry:
    """Internal record for a timeout-based automatic transition."""

    __slots__ = ("state", "target", "seconds", "timer")

    def __init__(self, state: str, target: str, seconds: float) -> None:
        self.state = state
        self.target = target
        self.seconds = seconds
        self.timer: threading.Timer | None = None


class StateMachine:
    """Finite state machine with transition callbacks, guards, timeouts,
    visualization export, and snapshot/restore."""

    def __init__(
        self,
        states: list[str],
        initial: str,
        transitions: list[tuple[str, str, str]],
    ) -> None:
        if not states:
            raise ValueError("states must not be empty")
        if initial not in states:
            raise ValueError(f"Initial state '{initial}' is not in states")

        state_set = set(states)
        for from_state, to_state, event in transitions:
            if from_state != "*" and from_state not in state_set:
                raise ValueError(
                    f"Transition from_state '{from_state}' is not in states"
                )
            if to_state not in state_set:
                raise ValueError(
                    f"Transition to_state '{to_state}' is not in states"
                )

        self._states = list(states)
        self._initial = initial
        self._transitions = list(transitions)
        self._state = initial
        self._history: list[str] = []
        self._transition_history: list[TransitionRecord] = []
        self._on_enter: dict[str, list[Callable[[str, str], Any]]] = {}
        self._on_exit: dict[str, list[Callable[[str, str], Any]]] = {}
        self._guards: dict[tuple[str, str, str], list[Callable[[dict[str, Any]], bool]]] = {}
        self._timeouts: dict[str, _TimeoutEntry] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def add_transition(
        self,
        from_state: str,
        to_state: str,
        event: str,
        guard: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        """Add a transition with an optional guard condition.

        Use ``"*"`` as *from_state* to create a wildcard transition that
        matches any current state.

        Args:
            from_state: Source state, or ``"*"`` for wildcard.
            to_state: Destination state.
            event: Event name that triggers the transition.
            guard: Optional callable that receives context dict and returns
                   ``True`` to allow the transition. If it returns falsy,
                   ``InvalidTransitionError`` is raised.
        """
        state_set = set(self._states)
        if from_state != "*" and from_state not in state_set:
            raise ValueError(
                f"Transition from_state '{from_state}' is not in states"
            )
        if to_state not in state_set:
            raise ValueError(
                f"Transition to_state '{to_state}' is not in states"
            )
        key = (from_state, to_state, event)
        if key not in [(f, t, e) for f, t, e in self._transitions]:
            self._transitions.append(key)
        if guard is not None:
            self._guards.setdefault(key, []).append(guard)

    @property
    def state(self) -> str:
        """Return the current state."""
        return self._state

    @property
    def history(self) -> list[str]:
        """Return the list of past states."""
        return list(self._history)

    @property
    def transition_history(self) -> list[TransitionRecord]:
        """Return a list of all past transition records with timestamps."""
        return list(self._transition_history)

    def trigger(self, event: str, context: dict[str, Any] | None = None) -> None:
        """Execute a transition for the given event.

        Args:
            event: The event name to trigger.
            context: Optional dict passed to guards and callbacks. Defaults
                     to an empty dict.

        Raises ``InvalidTransitionError`` if no matching transition exists
        or if a guard rejects the transition.
        """
        ctx = context if context is not None else {}

        with self._lock:
            # Try exact state match first, fall back to wildcard
            wildcard_match: tuple[str, str, str] | None = None
            for from_state, to_state, evt in self._transitions:
                if evt != event:
                    continue
                if from_state == self._state:
                    key = (from_state, to_state, evt)
                    for guard in self._guards.get(key, []):
                        if not guard(ctx):
                            raise InvalidTransitionError(self._state, event)
                    self._perform_transition(self._state, to_state, event, from_state)
                    return
                if from_state == "*" and wildcard_match is None:
                    wildcard_match = (from_state, to_state, evt)

            if wildcard_match is not None:
                from_state, to_state, evt = wildcard_match
                key = (from_state, to_state, evt)
                for guard in self._guards.get(key, []):
                    if not guard(ctx):
                        raise InvalidTransitionError(self._state, event)
                self._perform_transition(self._state, to_state, event, from_state)
                return

            raise InvalidTransitionError(self._state, event)

    def _perform_transition(
        self,
        actual_from: str,
        to_state: str,
        event: str,
        transition_source: str | None = None,
    ) -> None:
        """Execute the transition side-effects (callbacks, history, timeouts).

        Must be called while ``self._lock`` is held.

        Args:
            actual_from: The real current state being exited.
            to_state: The destination state.
            event: The event that triggered the transition.
            transition_source: The ``from_state`` in the transition definition
                (may be ``"*"`` for wildcard). Defaults to *actual_from*.
        """
        old_state = actual_from

        # Cancel any active timeout for the old state
        self._cancel_timeout(old_state)

        # Fire on_exit callbacks for the old state
        for callback in self._on_exit.get(old_state, []):
            callback(old_state, event)

        self._history.append(old_state)
        self._transition_history.append(
            TransitionRecord(
                from_state=old_state,
                to_state=to_state,
                event=event,
                timestamp=time.time(),
            )
        )
        self._state = to_state

        # Fire on_enter callbacks for the new state
        for callback in self._on_enter.get(to_state, []):
            callback(to_state, event)

        # Start timeout timer for the new state if configured
        self._start_timeout(to_state)

    def can(self, event: str) -> bool:
        """Return whether *event* is a valid transition from the current state."""
        return any(
            (from_state == self._state or from_state == "*") and evt == event
            for from_state, _, evt in self._transitions
        )

    def on_enter(self, state: str, callback: Callable[[str, str], Any]) -> None:
        """Register a callback invoked when entering *state*.

        The callback receives ``(state, event)`` arguments.
        """
        self._on_enter.setdefault(state, []).append(callback)

    def on_exit(self, state: str, callback: Callable[[str, str], Any]) -> None:
        """Register a callback invoked when exiting *state*.

        The callback receives ``(state, event)`` arguments.
        """
        self._on_exit.setdefault(state, []).append(callback)

    def reset(self) -> None:
        """Reset to the initial state and clear history."""
        with self._lock:
            self._cancel_all_timeouts()
            self._state = self._initial
            self._history.clear()
            self._transition_history.clear()
            self._start_timeout(self._initial)

    # ------------------------------------------------------------------
    # Timeout-based automatic transitions
    # ------------------------------------------------------------------

    def add_timeout(self, state: str, target: str, seconds: float) -> None:
        """Define an automatic transition after *seconds* in *state*.

        When the machine enters *state*, a background timer starts. If the
        machine is still in *state* when the timer fires, it transitions to
        *target* with the synthetic event ``__timeout__``.

        A matching transition ``(state, target, "__timeout__")`` is added
        automatically if it does not already exist.

        Args:
            state: The state to attach the timeout to.
            target: The destination state when the timeout fires.
            seconds: Number of seconds before the automatic transition.
        """
        if state not in self._states:
            raise ValueError(f"State '{state}' is not in states")
        if target not in self._states:
            raise ValueError(f"Target state '{target}' is not in states")
        if seconds <= 0:
            raise ValueError("seconds must be positive")

        # Ensure a transition exists for the timeout event
        timeout_key = (state, target, "__timeout__")
        if timeout_key not in [(f, t, e) for f, t, e in self._transitions]:
            self._transitions.append(timeout_key)

        entry = _TimeoutEntry(state, target, seconds)
        self._timeouts[state] = entry

        # If the machine is already in the target state, start the timer now
        if self._state == state:
            self._start_timeout(state)

    def _start_timeout(self, state: str) -> None:
        """Start the timeout timer for *state* if one is configured."""
        entry = self._timeouts.get(state)
        if entry is None:
            return

        def _fire() -> None:
            with self._lock:
                if self._state == entry.state:
                    self._perform_transition(entry.state, entry.target, "__timeout__")

        timer = threading.Timer(entry.seconds, _fire)
        timer.daemon = True
        entry.timer = timer
        timer.start()

    def _cancel_timeout(self, state: str) -> None:
        """Cancel the active timeout timer for *state*, if any."""
        entry = self._timeouts.get(state)
        if entry is not None and entry.timer is not None:
            entry.timer.cancel()
            entry.timer = None

    def _cancel_all_timeouts(self) -> None:
        """Cancel all active timeout timers."""
        for entry in self._timeouts.values():
            if entry.timer is not None:
                entry.timer.cancel()
                entry.timer = None

    # ------------------------------------------------------------------
    # Snapshot / restore
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable dict capturing the current state and history.

        The snapshot can be passed to :meth:`restore` to return the machine
        to this exact point.
        """
        return {
            "state": self._state,
            "history": list(self._history),
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore the machine from a snapshot previously created by
        :meth:`snapshot`.

        Args:
            snapshot: A dict with ``"state"`` and ``"history"`` keys.

        Raises ``ValueError`` if the snapshot contains an invalid state.
        """
        state = snapshot["state"]
        history = snapshot["history"]

        state_set = set(self._states)
        if state not in state_set:
            raise ValueError(f"Snapshot state '{state}' is not in states")
        for h in history:
            if h not in state_set:
                raise ValueError(
                    f"Snapshot history contains invalid state '{h}'"
                )

        with self._lock:
            self._cancel_all_timeouts()
            self._state = state
            self._history = list(history)
            self._start_timeout(state)

    # ------------------------------------------------------------------
    # Visualization export
    # ------------------------------------------------------------------

    def to_dot(self) -> str:
        """Return a DOT (Graphviz) representation of the state machine.

        The output can be rendered with ``dot -Tpng file.dot -o file.png``
        or any Graphviz-compatible tool.
        """
        lines: list[str] = []
        lines.append("digraph StateMachine {")
        lines.append("    rankdir=LR;")
        lines.append("")

        # Mark initial state with a double circle
        for s in self._states:
            shape = "doublecircle" if s == self._initial else "circle"
            lines.append(f'    "{s}" [shape={shape}];')

        lines.append("")

        # Draw transitions
        for from_state, to_state, event in self._transitions:
            if from_state == "*":
                # Wildcard: draw an edge from every state
                for s in self._states:
                    if s != to_state:
                        lines.append(f'    "{s}" -> "{to_state}" [label="{event}"];')
            else:
                lines.append(f'    "{from_state}" -> "{to_state}" [label="{event}"];')

        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Return a Mermaid state diagram string.

        The output can be embedded in Markdown or rendered by any Mermaid
        compatible tool.
        """
        lines: list[str] = []
        lines.append("stateDiagram-v2")

        # Mark initial state
        lines.append(f"    [*] --> {self._initial}")

        # Draw transitions
        for from_state, to_state, event in self._transitions:
            if from_state == "*":
                # Wildcard: draw an edge from every state
                for s in self._states:
                    if s != to_state:
                        lines.append(f"    {s} --> {to_state} : {event}")
            else:
                lines.append(f"    {from_state} --> {to_state} : {event}")

        return "\n".join(lines)
