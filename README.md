# philiprehberger-state-machine

[![Tests](https://github.com/philiprehberger/py-state-machine/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-state-machine/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-state-machine.svg)](https://pypi.org/project/philiprehberger-state-machine/)
[![License](https://img.shields.io/github/license/philiprehberger/py-state-machine)](LICENSE)
[![Sponsor](https://img.shields.io/badge/sponsor-GitHub%20Sponsors-ec6cb9)](https://github.com/sponsors/philiprehberger)

Lightweight finite state machine with guards and callbacks.

## Installation

```bash
pip install philiprehberger-state-machine
```

## Usage

```python
from philiprehberger_state_machine import StateMachine

sm = StateMachine(
    states=["pending", "confirmed", "shipped", "delivered"],
    initial="pending",
    transitions=[
        ("pending", "confirmed", "confirm"),
        ("confirmed", "shipped", "ship"),
        ("shipped", "delivered", "deliver"),
    ],
)

sm.trigger("confirm")
print(sm.state)  # "confirmed"
```

### Checking Available Transitions

```python
from philiprehberger_state_machine import StateMachine

sm = StateMachine(
    states=["pending", "confirmed", "shipped"],
    initial="pending",
    transitions=[
        ("pending", "confirmed", "confirm"),
        ("confirmed", "shipped", "ship"),
    ],
)

sm.can("confirm")  # True
sm.can("ship")     # False
```

### Callbacks

```python
from philiprehberger_state_machine import StateMachine

sm = StateMachine(
    states=["pending", "confirmed", "shipped"],
    initial="pending",
    transitions=[
        ("pending", "confirmed", "confirm"),
        ("confirmed", "shipped", "ship"),
    ],
)

sm.on_enter("confirmed", lambda state, event: print(f"Entered {state} via {event}"))
sm.on_exit("pending", lambda state, event: print(f"Left {state} via {event}"))

sm.trigger("confirm")
# Left pending via confirm
# Entered confirmed via confirm
```

### History and Reset

```python
from philiprehberger_state_machine import StateMachine

sm = StateMachine(
    states=["pending", "confirmed", "shipped"],
    initial="pending",
    transitions=[
        ("pending", "confirmed", "confirm"),
        ("confirmed", "shipped", "ship"),
    ],
)

sm.trigger("confirm")
sm.trigger("ship")
print(sm.history)  # ["pending", "confirmed"]

sm.reset()
print(sm.state)    # "pending"
print(sm.history)  # []
```

## API

| Function / Class | Description |
|------------------|-------------|
| `StateMachine(states, initial, transitions)` | Create a state machine with given states, initial state, and transitions |
| `StateMachine.state` | Current state (read-only property) |
| `StateMachine.history` | List of past states (read-only property) |
| `StateMachine.trigger(event)` | Execute a transition or raise `InvalidTransitionError` |
| `StateMachine.can(event)` | Return whether the event is valid from the current state |
| `StateMachine.on_enter(state, callback)` | Register a callback for entering a state |
| `StateMachine.on_exit(state, callback)` | Register a callback for exiting a state |
| `StateMachine.reset()` | Reset to initial state and clear history |
| `InvalidTransitionError` | Raised on invalid transitions; has `.state` and `.event` attributes |

## Development

```bash
pip install -e .
python -m pytest tests/ -v
```

## License

MIT
