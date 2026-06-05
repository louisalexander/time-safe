from datetime import datetime, timezone

import httpx
import respx

from timesafe.timelock.drand import (
    DRAND_API,
    QUICKNET_CHAIN_HASH,
    DrandInfo,
    fetch_info,
    round_at,
)


def test_round_at_basic():
    info = DrandInfo(genesis_time=0, period=3, chain_hash="x")
    t = datetime.fromtimestamp(12, tz=timezone.utc)
    assert round_at(info, t) == 5  # (12 - 0)//3 + 1


def test_round_at_before_genesis_is_one():
    info = DrandInfo(genesis_time=1000, period=3, chain_hash="x")
    t = datetime.fromtimestamp(500, tz=timezone.utc)
    assert round_at(info, t) == 1


def test_round_at_uses_utc_regardless_of_input_tz():
    info = DrandInfo(genesis_time=0, period=10, chain_hash="x")
    # 100 seconds after epoch, expressed in a +01:00 zone, is still unix=100.
    from datetime import timedelta

    t = datetime.fromtimestamp(100, tz=timezone(timedelta(hours=1)))
    assert round_at(info, t) == 11  # 100//10 + 1


@respx.mock
def test_fetch_info_parses_genesis_period_hash():
    respx.get(f"{DRAND_API}/{QUICKNET_CHAIN_HASH}/info").respond(
        json={"genesis_time": 1692803367, "period": 3, "hash": QUICKNET_CHAIN_HASH}
    )
    with httpx.Client() as client:
        info = fetch_info(client)
    assert info.genesis_time == 1692803367
    assert info.period == 3
    assert info.chain_hash == QUICKNET_CHAIN_HASH
