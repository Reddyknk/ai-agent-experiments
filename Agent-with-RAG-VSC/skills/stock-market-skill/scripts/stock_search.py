from __future__ import annotations

import json
from typing import Any


def get_top_market_moves(keyword: str = "gainers", limit: int = 5) -> list[dict[str, Any]]:
    sample = [
        {"symbol": "NVDA", "change_pct": 4.8, "price": 122.4},
        {"symbol": "META", "change_pct": 3.6, "price": 510.2},
        {"symbol": "MSFT", "change_pct": 2.9, "price": 431.1},
        {"symbol": "AAPL", "change_pct": -1.5, "price": 214.5},
        {"symbol": "TSLA", "change_pct": -2.7, "price": 203.6},
    ]
    if keyword.lower() == "losers":
        return sorted(sample, key=lambda item: item["change_pct"])[:limit]
    return sorted(sample, key=lambda item: item["change_pct"], reverse=True)[:limit]


if __name__ == "__main__":
    print(json.dumps(get_top_market_moves("gainers", 3), indent=2))
