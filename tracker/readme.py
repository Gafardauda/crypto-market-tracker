"""Rewrite the auto-generated stats section of README.md."""

import re
from pathlib import Path

import pandas as pd

from .charts import format_usd

START = "<!-- STATS:START -->"
END = "<!-- STATS:END -->"


def _pct(value: float) -> str:
    if pd.isna(value):
        return "–"
    arrow = "▲" if value > 0 else "▼" if value < 0 else ""
    return f"{arrow} {value:+.1f}%".strip()


def _big_usd(value: float) -> str:
    for size, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if value >= size:
            return f"${value / size:.2f}{suffix}"
    return f"${value:,.0f}"


def stats_markdown(stats: pd.DataFrame, as_of: str) -> str:
    lines = [
        f"_Snapshot as of **{as_of} 00:00 UTC**. Updated automatically every day._",
        "",
        "| Coin | Price | 1 day | 7 days | 30 days | 1 year | Volatility (30d) | Market cap |",
        "|:--|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for r in stats.itertuples():
        vol = "–" if pd.isna(r.vol_30d) else f"{r.vol_30d:.0f}%"
        lines.append(
            f"| **{r.symbol}** {r.name} | {format_usd(r.price)} | {_pct(r.chg_1d)} | {_pct(r.chg_7d)} | "
            f"{_pct(r.chg_30d)} | {_pct(r.chg_365d)} | {vol} | {_big_usd(r.market_cap)} |"
        )
    return "\n".join(lines)


def update_readme(path: Path, stats: pd.DataFrame, as_of: str) -> None:
    text = path.read_text(encoding="utf-8")
    block = f"{START}\n{stats_markdown(stats, as_of)}\n{END}"
    new_text, count = re.subn(f"{re.escape(START)}.*?{re.escape(END)}", lambda _: block, text, flags=re.S)
    if count != 1:
        raise ValueError(f"README.md must contain exactly one {START} ... {END} block")
    path.write_text(new_text, encoding="utf-8")
