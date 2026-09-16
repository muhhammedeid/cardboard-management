"""Canonical Cardboard rounding rules (P05-UAT-FIX04).

One module, one policy: whole kilograms with HALF-UP, and money in whole EGP
multiples of 5. Every authoritative calculation in the app goes through these
helpers — Decimal-safe, no banker's rounding, no binary-float money.
"""

from decimal import ROUND_HALF_UP, Decimal


def round_half_up(value) -> int:
    """Nearest integer, ties away from zero (HALF-UP). 86.5 -> 87, -86.5 -> -87."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def round_kg(value) -> int:
    """Operational weight: whole kilograms via HALF-UP. 86.4 -> 86, 86.6 -> 87."""
    return round_half_up(value)


def round_money_to_5(value) -> int:
    """Operational money: nearest multiple of 5 EGP via HALF-UP.

    14257 -> 14255, 14258 -> 14260, 19558 -> 19560. Decimal-safe: the value is
    converted through its string form so a float like 19558.0 does not pick up
    binary-float error.
    """
    value = Decimal(str(value))
    rounded = (value / Decimal("5")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(rounded * Decimal("5"))
