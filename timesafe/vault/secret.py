from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Secret:
    """A timelock-encrypted secret's metadata. The ciphertext lives separately (vault/secrets/<id>.tle)."""

    id: str
    name: str
    unlock_at: datetime
    drand_round: int
    drand_chain: str
    created_at: datetime
    delivery_email: str | None = None

    @classmethod
    def create(
        cls,
        name: str,
        unlock_at: datetime,
        drand_round: int,
        drand_chain: str,
        delivery_email: str | None = None,
    ) -> "Secret":
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            unlock_at=unlock_at,
            drand_round=drand_round,
            drand_chain=drand_chain,
            created_at=_now(),
            delivery_email=delivery_email,
        )

    def is_ready(self, now: datetime | None = None) -> bool:
        return (now or _now()) >= self.unlock_at

    def to_meta_json(self) -> str:
        return json.dumps(
            {
                "id": self.id,
                "name": self.name,
                "unlock_at": self.unlock_at.astimezone(timezone.utc).isoformat(),
                "drand_round": self.drand_round,
                "drand_chain": self.drand_chain,
                "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
                "delivery_email": self.delivery_email,
            },
            indent=2,
        )

    @classmethod
    def from_meta_json(cls, data: str | bytes) -> "Secret":
        if isinstance(data, bytes):
            data = data.decode()
        d = json.loads(data)
        return cls(
            id=d["id"],
            name=d["name"],
            unlock_at=datetime.fromisoformat(d["unlock_at"]),
            drand_round=int(d["drand_round"]),
            drand_chain=d["drand_chain"],
            created_at=datetime.fromisoformat(d["created_at"]),
            delivery_email=d.get("delivery_email"),
        )
