"""Render the README charts as PNGs."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

from .analyze import annualized_volatility, indexed, to_wide

# Categorical colors are assigned by position in config.json, so a coin keeps
# its color no matter which charts it appears in. The first three slots are
# validated as colorblind-safe together; a 4th coin gets a 4th slot.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "font.size": 10,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_SECONDARY,
    "axes.titlecolor": INK,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "ytick.left": False,
    "legend.frameon": False,
    "legend.labelcolor": INK_SECONDARY,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
})


def format_usd(value: float) -> str:
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.4g}"


def _colors(coins: list[dict]) -> dict[str, str]:
    return {c["id"]: SERIES_COLORS[i % len(SERIES_COLORS)] for i, c in enumerate(coins)}


def performance_chart(prices: pd.DataFrame, coins: list[dict], path: Path, days: int = 365,
                      title: str | None = None) -> None:
    """Every coin rebased to 100, so a $80,000 coin and a $1 coin share one axis."""
    recent = indexed(prices.tail(days))
    colors = _colors(coins)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axhline(100, color=BASELINE, linewidth=1)
    for coin in coins:
        s = recent[coin["id"]].dropna()
        ax.plot(s.index, s, color=colors[coin["id"]], linewidth=2, label=coin["symbol"])
        ax.annotate(
            f"{coin['symbol']} {s.iloc[-1]:.0f}", (s.index[-1], s.iloc[-1]),
            xytext=(6, 0), textcoords="offset points", va="center", color=INK_SECONDARY, fontsize=9,
        )

    ax.set_title(title or f"Growth of $100 invested {len(recent)} days ago", pad=24)
    ax.text(0, 1.02, "Each coin rebased to 100 on the first day. Above 100 = gained value.",
            transform=ax.transAxes, color=INK_SECONDARY, fontsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    if len(recent) <= 14:  # short windows read better as "Mon 13" than "10-13"
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d"))
    ax.legend(loc="lower left", ncols=len(coins))
    ax.margins(x=0.01)
    fig.savefig(path)
    plt.close(fig)


def price_panels(prices: pd.DataFrame, coins: list[dict], path: Path, days: int = 365) -> None:
    """One small panel per coin: daily price plus its 30-day moving average."""
    colors = _colors(coins)
    fig, axes = plt.subplots(len(coins), 1, figsize=(10, 2.6 * len(coins)), sharex=True)
    for ax, coin in zip(axes, coins):
        full = prices[coin["id"]]
        s = full.tail(days)
        ma30 = full.rolling(30, min_periods=30).mean().tail(days)
        ax.plot(s.index, s, color=colors[coin["id"]], linewidth=2, label="Daily price")
        ax.plot(ma30.index, ma30, color=INK_SECONDARY, linewidth=1.2, linestyle="--", label="30-day average")
        ax.set_title(f"{coin['symbol']}  ·  {coin['name']}", fontsize=11)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: format_usd(v)))
        ax.margins(x=0.01)
    axes[0].legend(loc="upper right", ncols=2)
    fig.tight_layout(h_pad=1.5)
    fig.savefig(path)
    plt.close(fig)


def volatility_chart(prices: pd.DataFrame, coins: list[dict], path: Path) -> None:
    """How much each coin's price swings, annualized from the last 30 days."""
    colors = _colors(coins)
    vols = [annualized_volatility(prices[c["id"]], 30) for c in coins]
    labels = [c["symbol"] for c in coins]

    fig, ax = plt.subplots(figsize=(10, 0.7 * len(coins) + 1.4))
    ax.barh(labels, vols, color=[colors[c["id"]] for c in coins], height=0.5)
    for i, v in enumerate(vols):
        ax.text(v, i, f"  {v:.0f}%", va="center", color=INK_SECONDARY, fontsize=10)
    ax.invert_yaxis()
    ax.set_axisbelow(True)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.spines["left"].set_visible(True)
    ax.tick_params(axis="y", colors=INK, length=0)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlim(0, max(vols) * 1.15)
    ax.set_title("Volatility (last 30 days, annualized)", pad=24)
    ax.text(0, 1.04, "Higher = bigger, more unpredictable price swings.",
            transform=ax.transAxes, color=INK_SECONDARY, fontsize=9)
    fig.savefig(path)
    plt.close(fig)


def render_all(history: pd.DataFrame, coins: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    prices = to_wide(history, "price_usd")
    performance_chart(prices, coins, out_dir / "performance.png")
    price_panels(prices, coins, out_dir / "prices.png")
    volatility_chart(prices, coins, out_dir / "volatility.png")
