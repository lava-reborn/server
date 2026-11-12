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

Core item/inventory/set code has no imports of this implementation. This
package registers extra templates, sets and strings through the generic core
interfaces at startup. The shared combat engine exposes explicit default methods.
Never persist the training avatar through the real character's store.

Copy ids are recorded in data/training_item_ids.json, not positions in a
sorted catalogue. Unavailable profiles/presets are archived, not discarded. Do not pickle runtime classes in checkpoints.
The baseline profile means old equations with range copies, not an exact snapshot
of all production item tables. Comparisons require matching participant profiles.

Keep lower layers independent of session/commands/api. Regression tests in
test_training_architecture enforce this boundary, alongside lifecycle, economy,
profile and shared-room tests. Client generators remain in tools/training_*_client.
"""
