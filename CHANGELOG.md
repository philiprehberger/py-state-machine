# Changelog

## 0.5.0 (2026-04-27)

- Add `on_transition(callback)` global hook firing after every successful transition with `(from_state, to_state, event, context)`
- Add `remove_transition_listener(callback)` for symmetry
- `on_transition` returns an unsubscribe closure

## 0.4.0 (2026-04-01)

- Add transition history with timestamps via `transition_history` property and `TransitionRecord` dataclass
- Add wildcard transitions using `"*"` as source state to match any current state
- Expand wildcard transitions in DOT and Mermaid visualization exports

## 0.3.1 (2026-03-31)

- Standardize README to 3-badge format with emoji Support section
- Update CI checkout action to v5 for Node.js 24 compatibility

## 0.3.0 (2026-03-28)

- Add state machine visualization export (DOT and Mermaid formats)
- Add timeout-based automatic transitions
- Add snapshot/restore for state serialization
- Bring package into full compliance with guides

## 0.2.0 (2026-03-27)

- Add guard conditions to transitions via `add_transition()` with optional `guard` parameter
- Add `context` parameter to `trigger()` for passing data to guards and callbacks
- Add `.github/` issue templates, PR template, and Dependabot config
- Update README with full badge set and Support section

## 0.1.0 (2026-03-21)

- Initial release
- Finite state machine with named states and event-driven transitions
- Transition validation and `InvalidTransitionError`
- Enter/exit callbacks per state
- State history tracking
- Reset to initial state
