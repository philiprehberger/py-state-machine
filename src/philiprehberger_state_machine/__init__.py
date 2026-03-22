"""Lightweight finite state machine with guards and callbacks."""

from __future__ import annotations

__all__ = ["InvalidTransitionError", "StateMachine"]


class InvalidTransitionError(Exception):
    """Raised when a transition is not valid for the current state and event."""

    def __init__(self, state: str, event: str) -> None:
        self.state = state
        self.event = event
        super().__init__(
            f"No transition for event '{event}' from state '{state}'"
        )


class StateMachine:
    """Finite state machine with transition callbacks and history tracking."""

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
            if from_state not in state_set:
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
        self._on_enter: dict[str, list[object]] = {}
        self._on_exit: dict[str, list[object]] = {}

    @property
    def state(self) -> str:
        """Return the current state."""
        return self._state

    @property
    def history(self) -> list[str]:
        """Return the list of past states."""
        return list(self._history)

    def trigger(self, event: str) -> None:
        """Execute a transition for the given event.

        Raises ``InvalidTransitionError`` if no matching transition exists.
        """
        for from_state, to_state, evt in self._transitions:
            if from_state == self._state and evt == event:
                old_state = self._state

                # Fire on_exit callbacks for the old state
                for callback in self._on_exit.get(old_state, []):
                    callback(old_state, event)  # type: ignore[operator]

                self._history.append(old_state)
                self._state = to_state

                # Fire on_enter callbacks for the new state
                for callback in self._on_enter.get(to_state, []):
                    callback(to_state, event)  # type: ignore[operator]

                return

        raise InvalidTransitionError(self._state, event)

    def can(self, event: str) -> bool:
        """Return whether *event* is a valid transition from the current state."""
        return any(
            from_state == self._state and evt == event
            for from_state, _, evt in self._transitions
        )

    def on_enter(self, state: str, callback: object) -> None:
        """Register a callback invoked when entering *state*.

        The callback receives ``(state, event)`` arguments.
        """
        self._on_enter.setdefault(state, []).append(callback)

    def on_exit(self, state: str, callback: object) -> None:
        """Register a callback invoked when exiting *state*.

        The callback receives ``(state, event)`` arguments.
        """
        self._on_exit.setdefault(state, []).append(callback)

    def reset(self) -> None:
        """Reset to the initial state and clear history."""
        self._state = self._initial
        self._history.clear()
