"""Teacher operations: slot capacity, payment and stats commit together."""
import copy

import progression
import storage


def apply(store, character, status, idx):
    if status not in (progression.UPD_LEARN, progression.UPD_FORGET):
        return progression.ERR_STATE, (0, 0)
    if not isinstance(idx, int) or not 0 <= idx < progression.SPECS:
        return progression.ERR_STATE, (0, 0)
    with storage.atomic(store.db):
        if not store.lock_quest_character(character.char_id):
            return progression.ERR_STATE, (0, 0)
        active = {row['idx'] for row in store.load_stats(character.char_id)
                  if row['kind'] == 'spec' and row['value'] >= 0}
        if active != {i for i, spec in enumerate(character.spec) if spec[0] >= 0}:
            return progression.ERR_STATE, (0, 0)
        trial = copy.deepcopy(character)
        trial.afro, trial.gold = store.money(character.char_id)
        trial.spec_slots = store.spec_slots(character.char_id)
        cost = trial.spec_cost()
        result = (trial.learn_spec(idx) if status == progression.UPD_LEARN
                  else trial.forget_spec(idx))
        if result != 0:
            return result, cost
        with store.booked_as('spec', idx):
            trial.save(store)
    # Publish the live state only after confirmed commit, preserving identity.
    character.__dict__.clear()
    character.__dict__.update(trial.__dict__)
    return 0, cost
