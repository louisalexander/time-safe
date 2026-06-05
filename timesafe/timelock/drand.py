from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

# Pinned quicknet (timelock-enabled, unchained, 3s period) — the tlock default.
QUICKNET_CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
DRAND_API = "https://api.drand.sh"


@dataclass(frozen=True)
class DrandInfo:
    genesis_time: int
    period: int
    chain_hash: str

    @classmethod
    def from_json(cls, data: dict) -> "DrandInfo":
        return cls(
            genesis_time=int(data["genesis_time"]),
            period=int(data["period"]),
            chain_hash=data.get("hash", QUICKNET_CHAIN_HASH),
        )


def round_at(info: DrandInfo, unlock_at: datetime) -> int:
    """The drand round a secret should be encrypted to so it unlocks at ~`unlock_at`.

    Uses drand's standard convention: current_round(t) = (t - genesis)//period + 1. Granularity is
    one period (~3s on quicknet), which is negligible for day/month-scale locks.
    """
    unlock_unix = int(unlock_at.astimezone(timezone.utc).timestamp())
    if unlock_unix <= info.genesis_time:
        return 1
    return (unlock_unix - info.genesis_time) // info.period + 1


def fetch_info(client: httpx.Client, chain_hash: str = QUICKNET_CHAIN_HASH) -> DrandInfo:
    resp = client.get(f"{DRAND_API}/{chain_hash}/info")
    resp.raise_for_status()
    return DrandInfo.from_json(resp.json())
