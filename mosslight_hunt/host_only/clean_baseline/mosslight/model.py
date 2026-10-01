"""Data model and validated, portable save format for Mosslight."""
from __future__ import annotations

from dataclasses import dataclass, field
import copy
import json
from pathlib import Path

SPECIES = ("moss", "fern", "clover", "glowcap")
ACTIONS = ("water", "compost", "plant_moss", "plant_fern", "plant_clover", "plant_glowcap", "clear")
SAVE_VERSION = 2


@dataclass
class Cell:
    moisture: int
    nutrients: int
    shade: int
    species: str | None = None
    age: int = 0
    vitality: int = 0

    def to_dict(self) -> dict:
        return vars(self).copy()


@dataclass
class World:
    seed: int
    width: int
    height: int
    day: int = 0
    cells: list[Cell] = field(default_factory=list)
    journal: list[dict] = field(default_factory=list)
    weather: str = "clear"
    revision: int = 0

    workbench: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.workbench:
            from .state import defaults
            self.workbench = defaults(len(self.cells))

    def index(self, x: int, y: int) -> int:
        if not isinstance(x, int) or isinstance(x, bool) or not isinstance(y, int) or isinstance(y, bool):
            raise ValueError("Coordinates must be integers")
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError("Coordinates outside the terrarium")
        return y * self.width + x

    def cell(self, x: int, y: int) -> Cell:
        return self.cells[self.index(x, y)]

    def to_dict(self) -> dict:
        return {
            "version": SAVE_VERSION, "seed": self.seed, "width": self.width,
            "height": self.height, "day": self.day, "weather": self.weather,
            "revision": self.revision, "cells": [cell.to_dict() for cell in self.cells],
            "journal": copy.deepcopy(self.journal), "workbench": copy.deepcopy(self.workbench),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "World":
        if not isinstance(data, dict) or type(data.get("version")) is not int or data.get("version") not in (1, SAVE_VERSION):
            raise ValueError("Unsupported Mosslight save version")
        try:
            seed, width, height, day = (data[k] for k in ("seed", "width", "height", "day"))
            if any(type(v) is not int for v in (seed, width, height, day)):
                raise ValueError("Seed, dimensions, and day must be integers")
            if not (4 <= width <= 40 and 4 <= height <= 30 and 0 <= day <= 1_000_000):
                raise ValueError("Invalid terrarium dimensions or day")
            raw_cells = data["cells"]
            if not isinstance(raw_cells, list) or len(raw_cells) != width * height:
                raise ValueError("Incorrect cell count")
            cells = []
            for raw in raw_cells:
                if not isinstance(raw, dict):
                    raise ValueError("Cell must be an object")
                values = [raw[k] for k in ("moisture", "nutrients", "shade", "age", "vitality")]
                if any(type(v) is not int for v in values):
                    raise ValueError("Cell values must be integers")
                if any(not 0 <= v <= 100 for v in values[:3]) or not 0 <= values[4] <= 100 or values[3] < 0:
                    raise ValueError("Cell value outside valid range")
                species = raw.get("species")
                if species is not None and species not in SPECIES:
                    raise ValueError("Unknown species")
                if species is None and (values[3] or values[4]):
                    raise ValueError("Empty cell cannot have age or vitality")
                cells.append(Cell(values[0], values[1], values[2], species, values[3], values[4]))
            journal = data.get("journal", [])
            if not isinstance(journal, list) or len(journal) > 200 or any(
                not isinstance(e, dict) or type(e.get("day")) is not int or not isinstance(e.get("text"), str)
                or len(e["text"]) > 240 for e in journal
            ):
                raise ValueError("Invalid journal")
            weather = data.get("weather", "clear")
            if weather not in ("clear", "drizzle", "rain", "storm"):
                raise ValueError("Invalid weather")
            revision = data.get("revision", 0)
            if type(revision) is not int or revision < 0:
                raise ValueError("Invalid revision")
            world = cls(seed, width, height, day, cells, copy.deepcopy(journal), weather, revision)
            if data["version"] == 2:
                from .state import validate
                world.workbench = validate(world, data.get("workbench", {}))
            return world
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError("Malformed Mosslight save") from exc


def load(path: str | Path) -> World:
    return World.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def save(world: World, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(world.to_dict(), indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
