"""Isolated in-game training range.

Integration: main Session imports only training.api (entry, resume, commands,
outgoing events, disconnect). Importing this package alone loads no resources.

Ownership and dependencies:
  api -> session: private store, lifecycle, checkpoints and room membership.
  session -> commands: validation/dispatch; operates on the supplied session.
  session -> avatar/arena: private Session subclass, fighters and rooms.
  catalog/supply/presets -> character/validation/settings: no session imports.
  party -> arena/geometry: shared rooms, without importing their coordinator.
  rules/profiles/formulas: selectable rule engines and bounded personal overrides.
  items/sets/effects: private copy identities and per-profile parameters.

Core item/inventory/set code intentionally uses the narrow items/sets/effects
adapters; names registers only labels. Those adapters must retain identity paths
for normal objects. The shared combat engine keeps its existing extension hooks.
Never persist the training avatar through the real character's store.

Saved profile JSON, copy ids, quest ids, wire commands and formula snapshots
remain stable across this refactor. Do not pickle runtime classes in checkpoints.
The baseline profile means old equations with range copies, not an exact snapshot
of all production item tables. Comparisons require matching participant profiles.

Keep lower layers independent of session/commands/api. Regression tests in
test_training_architecture enforce this boundary, alongside lifecycle, economy,
profile and shared-room tests. Client generators remain in tools/training_*_client.
"""
