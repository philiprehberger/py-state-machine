# Changelog

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
