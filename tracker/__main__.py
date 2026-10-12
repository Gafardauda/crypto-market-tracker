"""Run the full daily update: python -m tracker"""

import json
from pathlib import Path

from .analyze import summary
from .charts import render_all
from .fetch import update_history
from .readme import update_readme

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    history = update_history(ROOT / "data" / "history.csv", config)

    stats = summary(history, config["coins"])
    as_of = str(max(history["date"]))
    render_all(history, config["coins"], ROOT / "charts")
    update_readme(ROOT / "README.md", stats, as_of)

    print(f"Updated through {as_of}: {len(history)} rows")
    print(stats.to_string(index=False))


if __name__ == "__main__":
    main()
