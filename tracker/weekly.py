"""Write the weekly LinkedIn post draft and chart.

    python -m tracker.weekly                  # writes posts/latest.md and charts/weekly.png
    python -m tracker.weekly --issue-body SHA # prints the GitHub issue body for that commit
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd

from .analyze import annualized_volatility, pct_change_over, to_wide
from .charts import format_usd, performance_chart
from .fetch import load_history

ROOT = Path(__file__).resolve().parent.parent
POST_PATH = ROOT / "posts" / "latest.md"
CHART_PATH = ROOT / "charts" / "weekly.png"
HASHTAGS = "#DataAnalytics #Python #Crypto #DataVisualization #GitHubActions"


def weekly_stats(prices: pd.DataFrame, coins: list[dict]) -> pd.DataFrame:
    rows = []
    for coin in coins:
        s = prices[coin["id"]].dropna()
        # The snapshot dated D is taken at 00:00 UTC, so it closes out day D-1.
        daily = (s.pct_change() * 100).tail(7)
        daily.index = daily.index - pd.Timedelta(days=1)
        big_day = daily.abs().idxmax()
        rows.append({
            "symbol": coin["symbol"],
            "name": coin["name"],
            "price": s.iloc[-1],
            "chg_7d": pct_change_over(s, 7),
            "vol_30d": annualized_volatility(s, 30),
            "big_move": daily[big_day],
            "big_move_day": big_day,
        })
    return pd.DataFrame(rows)


def _dot(value: float) -> str:
    return "🟢" if value > 0 else "🔴" if value < 0 else "⚪"


def headline(stats: pd.DataFrame) -> str:
    ranked = stats.sort_values("chg_7d", ascending=False)
    best, worst = ranked.iloc[0], ranked.iloc[-1]
    if (stats["chg_7d"] > 0).all():
        return f"A green week across the board, led by {best.symbol} ({best.chg_7d:+.1f}%)."
    if (stats["chg_7d"] < 0).all():
        return f"A red week across the board. {best.symbol} held up best ({best.chg_7d:+.1f}%)."
    return f"A mixed week: {best.symbol} led ({best.chg_7d:+.1f}%) while {worst.symbol} lagged ({worst.chg_7d:+.1f}%)."


def build_post(stats: pd.DataFrame, week_end: pd.Timestamp, repo_url: str) -> str:
    biggest = stats.loc[stats["big_move"].abs().idxmax()]
    calmest = stats.loc[stats["vol_30d"].idxmin()]
    ranked = stats.sort_values("chg_7d", ascending=False)

    lines = [
        f"📈 My crypto tracker: week ending {week_end:%a %d %b}",
        "",
        headline(stats),
        "",
        *[f"{_dot(r.chg_7d)} {r.symbol}: {r.chg_7d:+.1f}% ({format_usd(r.price)})" for r in ranked.itertuples()],
        "",
        f"⚡ Biggest single-day move: {biggest.symbol} {biggest.big_move:+.1f}% on {biggest.big_move_day:%A}.",
        f"📊 Calmest coin over the last 30 days: {calmest.symbol} ({calmest.vol_30d:.0f}% annualized volatility).",
        "",
        "✍️ [Add one sentence of your own here. What surprised you this week?]",
        "",
        "My Python pipeline collects this data automatically every day with GitHub Actions.",
        "🪙 Want a coin added to the tracker? Tell me in the comments!",
        "",
        f"Live charts 👉 {repo_url}",
        "",
        HASHTAGS,
    ]
    return "\n".join(lines)


def build_issue_body(post: str, owner: str, image_url: str) -> str:
    return "\n".join([
        f"@{owner} your weekly LinkedIn post is ready 👋",
        "",
        "**To post it:**",
        "1. Copy the text below (copy button at the top-right of the box).",
        "2. Replace the ✍️ line with a sentence of your own.",
        "3. Save the chart below (right-click → Save image) and attach it to the post.",
        "4. Close this issue once it's posted ✅",
        "",
        "```text",
        post,
        "```",
        "",
        f"![Weekly performance chart]({image_url})",
    ])


def main(argv: list[str]) -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "Gafardauda/crypto-market-tracker")

    if argv[:1] == ["--issue-body"]:
        sha = argv[1]
        owner = os.environ.get("GITHUB_REPOSITORY_OWNER", repo.split("/")[0])
        image_url = f"https://github.com/{repo}/blob/{sha}/charts/weekly.png?raw=true"
        print(build_issue_body(POST_PATH.read_text(encoding="utf-8"), owner, image_url))
        return

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    prices = to_wide(load_history(ROOT / "data" / "history.csv"), "price_usd")
    week_end = prices.index[-1] - pd.Timedelta(days=1)

    stats = weekly_stats(prices, config["coins"])
    post = build_post(stats, week_end, f"https://github.com/{repo}")
    POST_PATH.parent.mkdir(parents=True, exist_ok=True)
    POST_PATH.write_text(post + "\n", encoding="utf-8")
    daily_closes = prices.set_axis(prices.index - pd.Timedelta(days=1))  # label by the day each snapshot closes
    performance_chart(daily_closes, config["coins"], CHART_PATH, days=8,
                      title=f"Growth of $100 over the week ending {week_end:%a %d %b}")

    title = f"📬 Weekly LinkedIn post: week ending {week_end:%d %b %Y}"
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"title={title}\n")
    print(title, post, sep="\n\n")


if __name__ == "__main__":
    main(sys.argv[1:])
