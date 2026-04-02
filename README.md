# philiprehberger-state-machine

[![Tests](https://github.com/philiprehberger/py-state-machine/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-state-machine/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-state-machine.svg)](https://pypi.org/project/philiprehberger-state-machine/)
[![Last updated](https://img.shields.io/github/last-commit/philiprehberger/py-state-machine)](https://github.com/philiprehberger/py-state-machine/commits/main)

Lightweight finite state machine with guards, callbacks, and visualization.

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

### Guard Conditions

Guards are optional callables that receive a context dict and must return `True` to allow the transition. If a guard returns falsy, `InvalidTransitionError` is raised.

```python
from philiprehberger_state_machine import StateMachine

sm = StateMachine(
    states=["draft", "published"],
    initial="draft",
    transitions=[],
)

sm.add_transition("draft", "published", "publish", guard=lambda ctx: ctx.get("has_title", False))

sm.trigger("publish", context={"has_title": True})   # succeeds
print(sm.state)  # "published"
```

### Transition Context

Pass a context dict to `trigger()` to share data with guards and callbacks.

```python
sm.trigger("confirm", context={"user": "alice", "approved": True})
```

If no context is provided, an empty dict is passed to guards.

### Wildcard Transitions

Use `"*"` as the source state to define a transition that can fire from any state.

```python
from philiprehberger_state_machine import StateMachine

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
print(sm.state)  # "running"

sm.trigger("fail")
print(sm.state)  # "error"
```

Wildcard transitions are checked after exact state matches, so a specific transition always takes priority.

### Transition History

Track all past transitions with timestamps using `transition_history`.

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

for record in sm.transition_history:
    print(f"{record.from_state} -> {record.to_state} via {record.event} at {record.timestamp}")
# pending -> confirmed via confirm at 1711929600.123
# confirmed -> shipped via ship at 1711929600.456
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

### Timeout-Based Automatic Transitions

Define transitions that fire automatically after a state has been active for a given number of seconds.

```python
from philiprehberger_state_machine import StateMachine
import time

sm = StateMachine(
    states=["idle", "processing", "timeout_state"],
    initial="idle",
    transitions=[("idle", "processing", "start")],
)

sm.add_timeout("processing", "timeout_state", seconds=5.0)

sm.trigger("start")
print(sm.state)  # "processing"

time.sleep(6)
print(sm.state)  # "timeout_state"
```

### Snapshot and Restore

Capture and restore the machine's state and history for serialization or checkpointing.

```python
from philiprehberger_state_machine import StateMachine

sm = StateMachine(
    states=["a", "b", "c"],
    initial="a",
    transitions=[("a", "b", "go"), ("b", "c", "go")],
)

sm.trigger("go")
snap = sm.snapshot()
print(snap)  # {"state": "b", "history": ["a"]}

sm.trigger("go")
print(sm.state)  # "c"

sm.restore(snap)
print(sm.state)  # "b"
```

### Visualization Export

Export the state machine as a DOT (Graphviz) or Mermaid diagram string.

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

print(sm.to_dot())
# digraph StateMachine {
#     rankdir=LR;
#
#     "pending" [shape=doublecircle];
#     "confirmed" [shape=circle];
#     "shipped" [shape=circle];
#
#     "pending" -> "confirmed" [label="confirm"];
#     "confirmed" -> "shipped" [label="ship"];
# }

print(sm.to_mermaid())
# stateDiagram-v2
#     [*] --> pending
#     pending --> confirmed : confirm
#     confirmed --> shipped : ship
```

## API

| Function / Class | Description |
|------------------|-------------|
| `StateMachine(states, initial, transitions)` | Create a state machine with given states, initial state, and transitions |
| `StateMachine.state` | Current state (read-only property) |
| `StateMachine.history` | List of past states (read-only property) |
| `StateMachine.transition_history` | List of `TransitionRecord` objects with timestamps (read-only property) |
| `StateMachine.trigger(event, context=None)` | Execute a transition or raise `InvalidTransitionError`. Pass optional context dict to guards. |
| `StateMachine.can(event)` | Return whether the event is valid from the current state |
| `StateMachine.add_transition(from_state, to_state, event, guard=None)` | Add a transition with an optional guard callable. Use `"*"` as from_state for wildcard. |
| `StateMachine.on_enter(state, callback)` | Register a callback for entering a state |
| `StateMachine.on_exit(state, callback)` | Register a callback for exiting a state |
| `StateMachine.reset()` | Reset to initial state and clear history |
| `StateMachine.add_timeout(state, target, seconds)` | Define an automatic transition after *seconds* in *state* |
| `StateMachine.snapshot()` | Return a serializable dict of current state and history |
| `StateMachine.restore(snapshot)` | Restore the machine from a snapshot dict |
| `StateMachine.to_dot()` | Return a DOT/Graphviz string of the state machine |
| `StateMachine.to_mermaid()` | Return a Mermaid state diagram string |
| `TransitionRecord` | Frozen dataclass with `from_state`, `to_state`, `event`, and `timestamp` fields |
| `InvalidTransitionError` | Raised on invalid transitions; has `.state` and `.event` attributes |

## Development

```bash
pip install -e .
python -m pytest tests/ -v
```

## Support

If you find this project useful:

⭐ [Star the repo](https://github.com/philiprehberger/py-state-machine)

🐛 [Report issues](https://github.com/philiprehberger/py-state-machine/issues?q=is%3Aissue+is%3Aopen+label%3Abug)

💡 [Suggest features](https://github.com/philiprehberger/py-state-machine/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)

❤️ [Sponsor development](https://github.com/sponsors/philiprehberger)

🌐 [All Open Source Projects](https://philiprehberger.com/open-source-packages)

💻 [GitHub Profile](https://github.com/philiprehberger)

🔗 [LinkedIn Profile](https://www.linkedin.com/in/philiprehberger)

## License

[MIT](LICENSE)
