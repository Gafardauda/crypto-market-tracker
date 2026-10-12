"""Turn the raw history into the metrics shown in the README and charts."""

import numpy as np
import pandas as pd


def to_wide(history: pd.DataFrame, column: str = "price_usd") -> pd.DataFrame:
    """Pivot to one column per coin on a continuous daily index (gaps stay NaN)."""
    wide = history.pivot(index="date", columns="coin", values=column)
    wide.index = pd.to_datetime(wide.index)
    full_range = pd.date_range(wide.index.min(), wide.index.max(), freq="D")
    return wide.reindex(full_range)


def pct_change_over(prices: pd.Series, days: int) -> float:
    """Percent change between the latest price and the price `days` days earlier."""
    prices = prices.dropna()
    if prices.empty:
        return np.nan
    latest_date = prices.index[-1]
    past = prices.get(latest_date - pd.Timedelta(days=days))
    if past is None or pd.isna(past) or past == 0:
        return np.nan
    return (prices.iloc[-1] / past - 1) * 100


def annualized_volatility(prices: pd.Series, window: int = 30) -> float:
    """Standard deviation of daily log returns over `window` days, scaled to a year.

    Crypto trades every day, so a year is 365 periods (stocks use ~252).
    """
    returns = np.log(prices.dropna()).diff().dropna().tail(window)
    if len(returns) < 2:
        return np.nan
    return returns.std() * np.sqrt(365) * 100


def indexed(prices: pd.DataFrame) -> pd.DataFrame:
    """Rescale each coin so its first value is 100, making very different prices comparable."""
    return prices.apply(lambda s: s / s.dropna().iloc[0] * 100)


def summary(history: pd.DataFrame, coins: list[dict]) -> pd.DataFrame:
    prices = to_wide(history, "price_usd")
    caps = to_wide(history, "market_cap_usd")
    rows = []
    for coin in coins:
        s = prices[coin["id"]]
        rows.append({
            "symbol": coin["symbol"],
            "name": coin["name"],
            "price": s.dropna().iloc[-1],
            "chg_1d": pct_change_over(s, 1),
            "chg_7d": pct_change_over(s, 7),
            "chg_30d": pct_change_over(s, 30),
            "chg_365d": pct_change_over(s, 365),
            "vol_30d": annualized_volatility(s, 30),
            "market_cap": caps[coin["id"]].dropna().iloc[-1],
        })
    return pd.DataFrame(rows)
