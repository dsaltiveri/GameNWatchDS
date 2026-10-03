#!/usr/bin/env python3
"""Read the GameNWatchDS catalog directly from the C descriptors."""

from dataclasses import dataclass
from pathlib import Path
import re



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
    registry = (root / "arm9/source/game_catalog.h").read_text(encoding="utf-8")
    names = re.findall(r"\bX\((\w+)\)", registry)
    if not names or len(names) != len(set(names)):
        raise RuntimeError("Catalog registry is empty or contains duplicate entries")
    for name in names:
        descriptor = source_dir / f"game_{name}.c"
        text = descriptor.read_text(encoding="utf-8")
        name_match = re.search(r'\.name\s*=\s*"([^"]+)"', text)
        path_match = re.search(r'\.rom_path\s*=\s*"(/gnw/gnw_([A-Za-z0-9_-]+)\.gnw)"',
                               text)
        if not name_match or not path_match:
            raise RuntimeError(
                f"Could not read name/rom_path from descriptor: {descriptor}")
        games.append(Game(path_match.group(2), name_match.group(1),
                          path_match.group(1), descriptor))

    for field in ("slug", "name", "rom_path"):
        values = [getattr(game, field).casefold() for game in games]
        if len(values) != len(set(values)):
            raise RuntimeError(f"Catalog contains duplicate {field} values")

    return tuple(sorted(games, key=lambda game: game.name.casefold()))


def gnw_path(root: Path, game: Game) -> Path:
    return root / "shrinker" / "output" / "gnw" / Path(game.rom_path).name

