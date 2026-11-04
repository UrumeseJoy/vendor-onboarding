"""Pure helper functions for validating Indian GSTIN checksums and US ABA routing numbers."""

GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_checksum(first14: str) -> str:
    """Return the official GSTIN check character for the first 14 characters."""
    total = 0
    for position, char in enumerate(first14.upper(), start=1):
        value = GSTIN_CHARSET.index(char)
        factor = 1 if position % 2 == 1 else 2  # odd positions x1, even positions x2
        product = value * factor
        total += product // 36 + product % 36
    check_value = (36 - total % 36) % 36
    return GSTIN_CHARSET[check_value]


def aba_routing_valid(routing: str) -> bool:
    """True if routing is 9 digits and passes the ABA checksum (3-7-1 weights, divisible by 10)."""
    if len(routing) != 9 or not routing.isdigit():
        return False
    d = [int(c) for c in routing]
    total = 3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + (d[2] + d[5] + d[8])
    return total % 10 == 0
