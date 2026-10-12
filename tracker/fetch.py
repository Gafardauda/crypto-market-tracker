"""Fetch daily market data from the CoinGecko API and keep data/history.csv up to date."""

import os
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://api.coingecko.com/api/v3"
COLUMNS = ["date", "coin", "price_usd", "market_cap_usd", "volume_usd"]


def _get(path: str, params: dict) -> dict:
    """GET a CoinGecko endpoint, backing off politely when rate limited."""
    headers = {"accept": "application/json"}
    api_key = os.environ.get("COINGECKO_API_KEY")
    if api_key:
        headers["x-cg-demo-api-key"] = api_key

    for attempt in range(4):
        resp = requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp.json()
        time.sleep(20 * (attempt + 1))
    resp.raise_for_status()


def fetch_daily_history(coin_id: str, days: int, vs_currency: str = "usd") -> pd.DataFrame:
    """Return one row per day for the last `days` days.

    CoinGecko's daily series has one point at 00:00 UTC per day plus a live
    "right now" point. Only the 00:00 UTC points are kept so every row means
    the same thing: the market snapshot at the start of that UTC day.
    """
    data = _get(
        f"/coins/{coin_id}/market_chart",
        {"vs_currency": vs_currency, "days": days, "interval": "daily"},
    )
    fields = {"prices": "price_usd", "market_caps": "market_cap_usd", "total_volumes": "volume_usd"}
    frames = [pd.DataFrame(data[key], columns=["ts", col]).set_index("ts") for key, col in fields.items()]
    df = pd.concat(frames, axis=1).reset_index()

    ts = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df[ts == ts.dt.normalize()].copy()
    df["date"] = ts[df.index].dt.date
    df["coin"] = coin_id
    return df[COLUMNS]


def load_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def days_to_fetch(history: pd.DataFrame, coin_id: str, backfill_days: int, today: date) -> int:
    """Backfill a new coin, otherwise fetch just enough days to fill any gap."""
    dates = history.loc[history["coin"] == coin_id, "date"]
    if dates.empty:
        return backfill_days
    gap = (today - max(dates)).days
    return max(2, min(gap + 1, backfill_days))


def merge_history(history: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Combine old and new rows; new values win for any (date, coin) seen twice."""
    frames = [df for df in (history, new) if not df.empty]
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["date", "coin"], keep="last")
    return combined.sort_values(["coin", "date"]).reset_index(drop=True)


def update_history(path: Path, config: dict, today: date | None = None) -> pd.DataFrame:
    today = today or pd.Timestamp.now(tz="UTC").date()
    history = load_history(path)
    for i, coin in enumerate(config["coins"]):
        if i:
            time.sleep(3)  # stay well inside the free-tier rate limit
        days = days_to_fetch(history, coin["id"], config["backfill_days"], today)
        print(f"Fetching {coin['symbol']}: last {days} days")
        new = fetch_daily_history(coin["id"], days, config["vs_currency"])
        history = merge_history(history, new)

    path.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(path, index=False)
    return history
