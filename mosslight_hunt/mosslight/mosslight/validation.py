"""Small strict validators shared by saves, commands, and exchange formats."""
from __future__ import annotations


def integer(value, name, minimum=0, maximum=1_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


def text(value, name, maximum=240, *, blank=False):
    if not isinstance(value, str) or len(value) > maximum or (not blank and not value.strip()):
        raise ValueError(f"{name} must be text of 1–{maximum} characters")
    return value.strip()


def choice(value, values, name):
    if not isinstance(value, str) or value not in values:
        raise ValueError(f"Unknown {name}: {value!r}")
    return value


def boolean(value, name):
    if type(value) is not bool:
        raise ValueError(f"{name} must be true or false")
    return value


def sequence(value, name, maximum=1000):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{name} must be a list with at most {maximum} items")
    return value


def mapping(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def tags(value):
    sequence(value, "Tags", 12)
    result = []
    for tag in value:
        tag = text(tag, "Tag", 32).casefold()
        if tag not in result:
            result.append(tag)
    return sorted(result)


def coordinates(world, value):
    sequence(value, "Coordinates", 1200)
    result = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Each coordinate must be [x, y]")
        world.index(*point)
        if tuple(point) not in result:
            result.append(tuple(point))
    if not result:
        raise ValueError("Select at least one tile")
    return result
