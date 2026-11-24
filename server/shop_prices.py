"""Whole-currency unit prices for discounted base consumables."""
import math


def discounted_unit(unit, modifier=.9):
    """At least one unit off; a minimum-price item remains one, never free."""
    return max(1, min(math.ceil(unit * modifier), math.ceil(unit) - 1))
