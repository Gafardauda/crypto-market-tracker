from datetime import date

import numpy as np
import pandas as pd
import pytest

from tracker.analyze import annualized_volatility, indexed, pct_change_over
from tracker.fetch import days_to_fetch, merge_history
from tracker.readme import stats_markdown, update_readme


def daily(values, start="2026-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"), dtype=float)


def rows(coin, start, prices):
    dates = pd.date_range(start, periods=len(prices), freq="D").date
    return pd.DataFrame({"date": dates, "coin": coin, "price_usd": prices,
                         "market_cap_usd": 1.0, "volume_usd": 1.0})


def test_pct_change_over():
    s = daily([100, 110, 120, 150])
    assert pct_change_over(s, 1) == pytest.approx(25.0)
    assert pct_change_over(s, 3) == pytest.approx(50.0)
    assert np.isnan(pct_change_over(s, 30))  # not enough history yet


def test_volatility_is_zero_for_steady_growth():
    s = daily(100 * 1.01 ** np.arange(40))
    assert annualized_volatility(s, 30) == pytest.approx(0, abs=1e-9)


def test_indexed_starts_at_100():
    df = pd.DataFrame({"a": [50.0, 100.0], "b": [np.nan, 2.0]})
    out = indexed(df)
    assert out["a"].tolist() == [100, 200]
    assert out["b"].iloc[1] == 100


def test_merge_prefers_new_rows():
    old = rows("bitcoin", "2026-01-01", [1, 2, 3])
    new = rows("bitcoin", "2026-01-03", [30, 40])
    merged = merge_history(old, new)
    assert merged["price_usd"].tolist() == [1, 2, 30, 40]


def test_days_to_fetch():
    history = rows("bitcoin", "2026-01-01", [1, 2, 3])  # last date: Jan 3
    assert days_to_fetch(history, "ethereum", 365, date(2026, 1, 4)) == 365  # new coin: backfill
    assert days_to_fetch(history, "bitcoin", 365, date(2026, 1, 4)) == 2
    assert days_to_fetch(history, "bitcoin", 365, date(2026, 1, 13)) == 11  # catches up after a gap


def test_update_readme_replaces_only_stats_block(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("intro\n<!-- STATS:START -->\nold\n<!-- STATS:END -->\noutro\n", encoding="utf-8")
    stats = pd.DataFrame([{"symbol": "BTC", "name": "Bitcoin", "price": 84000.0, "chg_1d": 1.0,
                           "chg_7d": -2.0, "chg_30d": np.nan, "chg_365d": 5.0, "vol_30d": 40.0,
                           "market_cap": 1.6e12}])
    update_readme(readme, stats, "2026-01-01")
    text = readme.read_text(encoding="utf-8")
    assert text.startswith("intro\n") and text.endswith("outro\n")
    assert "old" not in text
    assert "$84,000" in text and "$1.60T" in text
    assert stats_markdown(stats, "2026-01-01") in text
