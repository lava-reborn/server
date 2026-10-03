"""How long the fight's own pauses last: the aim, the swing, the reload, the
first aid, a creature's attack, a corpse lying before it fades.

Each is the length the client draws its bar for (fire_times, strike_time,
reload_time, heal_time; mobs' attack_time) and the server holds the result
back for as long. A suite that plays a fight sits through every one of them
on the wall clock: Берт's course is some four hundred aims at 0.7 s, more
than six of its eleven minutes. LAVA_ACTION_SCALE shortens them all at once
for such a suite (0.05 is a twentieth); nothing that serves anybody sets it,
and at the default 1 every pause is the client's.

Only these. The timers a test reads as rules -- the exit timer
(LAVA_LEAVE_COMBAT), the respawn (LAVA_RESPAWN), the life of a bag on the
ground (LAVA_LOOT_LIFETIME), the boss hours -- keep their own settings, and
walking keeps the client's pace, which the room's positions follow.

The rest stay on the wall clock, each for its reason:
  combat.AI_TICK            the beat the creatures think on, not a bar the
                            client draws; shortening it only polls faster.
                            The AP come back on it too (AP_TICK, aspd), so a
                            scaled suite raises LAVA_AP_REGEN and waits a
                            beat when refused (test_halfa_training)
  encounters (the ambush)   timed by the walk over the map, so the client's
  server.py chase, legs,    pace: a scaled ambush would spring ahead of the
  passages; rooms heartbeat figure it is meant to catch
  barter, clans, auction,   a player's or the admin's patience, nothing a
  the admin poll            fight's suite sits through
"""
import os

SCALE = float(os.environ.get("LAVA_ACTION_SCALE", "1"))


def paced(seconds):
    """A pause of the fight as this server keeps it."""
    return seconds * SCALE
