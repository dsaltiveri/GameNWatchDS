#!/usr/bin/env python3
"""Read the GameNWatchDS catalog directly from the C descriptors."""

from dataclasses import dataclass
from pathlib import Path
import re


EXPECTED_GAME_COUNT = 56


@dataclass(frozen=True)
class Game:
    slug: str
    name: str
    rom_path: str
    descriptor: Path


def load_catalog(root: Path) -> tuple[Game, ...]:
    """Return the menu catalog in the same case-insensitive name order."""
    games = []
    source_dir = root / "arm9" / "source" / "games"
    for descriptor in sorted(source_dir.glob("game_*.c")):
        text = descriptor.read_text(encoding="utf-8")
        name_match = re.search(r'\.name\s*=\s*"([^"]+)"', text)
        path_match = re.search(r'\.rom_path\s*=\s*"(/gnw/gnw_([A-Za-z0-9_-]+)\.gnw)"',
                               text)
        if not name_match or not path_match:
            raise RuntimeError(
                f"Could not read name/rom_path from descriptor: {descriptor}")
        games.append(Game(path_match.group(2), name_match.group(1),
                          path_match.group(1), descriptor))

    if len(games) != EXPECTED_GAME_COUNT:
        raise RuntimeError(
            f"Catalog has {len(games)} entries; expected {EXPECTED_GAME_COUNT}")
    for field in ("slug", "name", "rom_path"):
        values = [getattr(game, field).casefold() for game in games]
        if len(values) != len(set(values)):
            raise RuntimeError(f"Catalog contains duplicate {field} values")

    return tuple(sorted(games, key=lambda game: game.name.casefold()))


def gnw_path(root: Path, game: Game) -> Path:
    return root / "shrinker" / "output" / "gnw" / Path(game.rom_path).name
