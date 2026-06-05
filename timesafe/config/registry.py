from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_PATH = Path.home() / ".timesafe" / "vaults.json"


@dataclass
class VaultRef:
    """A pointer to a vault: a label and the GitHub repo that backs it. No credentials."""

    name: str
    repo: str  # "owner/repo"


class VaultRegistry:
    """The on-disk list of known vaults — the ONLY local persistence of vault state."""

    def __init__(self, vaults: list[VaultRef]) -> None:
        self._vaults = vaults

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "VaultRegistry":
        p = Path(path)
        if not p.exists():
            return cls([])
        data = json.loads(p.read_text())
        return cls([VaultRef(**item) for item in data])

    def save(self, path: Path = DEFAULT_PATH) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([asdict(v) for v in self._vaults], indent=2))

    @property
    def vaults(self) -> list[VaultRef]:
        return list(self._vaults)

    def contains(self, repo: str) -> bool:
        return any(v.repo == repo for v in self._vaults)

    def add(self, ref: VaultRef) -> None:
        if not self.contains(ref.repo):
            self._vaults.append(ref)

    def remove(self, repo: str) -> None:
        self._vaults = [v for v in self._vaults if v.repo != repo]
