#!/usr/bin/env python3
"""
Sync external odds to SportsPredict Probability Cup.

Default source is Polymarket (free) + The Odds API when configured.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from client import SportsPredictClient
from sources import (
    APIFootballSource,
    FBRefSource,
    FootballDataOrgSource,
    ManualOddsSource,
    PolymarketSource,
    TheOddsAPISource,
    build_best_source,
)
from sync_engine import run_sync, save_predictions


def build_source(args: argparse.Namespace):
    if args.source == "manual":
        path = Path(args.manual_file)
        if not path.exists():
            raise SystemExit(
                f"Manual odds file not found: {path}\n"
                "See data/odds.example.json for format."
            )
        return ManualOddsSource(path)

    if args.source == "polymarket":
        return PolymarketSource()

    if args.source == "odds_api":
        api_key = os.environ.get("THE_ODDS_API_KEY")
        if not api_key:
            raise SystemExit("THE_ODDS_API_KEY not set in .env")
        bookmakers_raw = os.environ.get("ODDS_BOOKMAKERS", "").strip()
        bookmakers = [b.strip() for b in bookmakers_raw.split(",") if b.strip()] or None
        return TheOddsAPISource(
            api_key=api_key,
            sport_key=os.environ.get("ODDS_SPORT_KEY", "soccer_fifa_world_cup"),
            regions=os.environ.get("ODDS_REGIONS", "uk,eu"),
            bookmakers=bookmakers,
        )

    if args.source == "football_data":
        api_key = os.environ.get("FOOTBALL_DATA_ORG_KEY")  # optional
        return FootballDataOrgSource(api_key=api_key)

    if args.source == "api_football":
        api_key = os.environ.get("API_FOOTBALL_KEY")
        if not api_key:
            raise SystemExit("API_FOOTBALL_KEY not set in .env")
        return APIFootballSource(api_key=api_key)

    # auto / best
    manual = args.manual_file if Path(args.manual_file).exists() else None
    return build_best_source(
        manual_file=manual,
        api_football_key=os.environ.get("API_FOOTBALL_KEY"),
        football_data_org_key=os.environ.get("FOOTBALL_DATA_ORG_KEY"),
        odds_api_key=os.environ.get("THE_ODDS_API_KEY"),
        odds_sport_key=os.environ.get("ODDS_SPORT_KEY", "soccer_fifa_world_cup"),
        odds_regions=os.environ.get("ODDS_REGIONS", "uk,eu"),
        odds_bookmakers=[
            b.strip()
            for b in os.environ.get("ODDS_BOOKMAKERS", "").split(",")
            if b.strip()
        ]
        or None,
    )


def main() -> None:
    # Ensure UTF-8 output on Windows (handles accented player names like Mbappé, Modrić)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    elif sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    
    load_dotenv()

    parser = argparse.ArgumentParser(description="Copy external odds to SportsPredict")
    parser.add_argument("--dry-run", action="store_true", help="Preview without submitting")
    parser.add_argument("--update", action="store_true", help="Update existing predictions")
    parser.add_argument(
        "--source",
        choices=("auto", "polymarket", "odds_api", "api_football", "football_data", "manual"),
        default="auto",
        help="Odds source (default: auto = Polymarket + football-data.org + FBRef)",
    )
    parser.add_argument(
        "--manual-file",
        default="data/odds.json",
        help="Optional manual odds overlay (merged in auto mode if file exists)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show skipped markets")
    parser.add_argument("--save", "-s", action="store_true", help="Save predictions to data/predictions/")
    args = parser.parse_args()

    sp_key = os.environ.get("SPORTSPREDICT_API_KEY")
    if not sp_key and not args.dry_run:
        raise SystemExit(
            "SPORTSPREDICT_API_KEY not set. Copy .env.example to .env and add your bot key."
        )

    print("Fetching external odds...")
    source = build_source(args)
    if args.source == "auto":
        print("Sources:")

    if args.dry_run and not sp_key:
        odds = source.fetch_match_odds()
        print(f"Loaded {len(odds)} fixtures (no SportsPredict key — skipping market fetch)")
        for row in odds[:5]:
            print(
                f"  {row.home_team} vs {row.away_team}: "
                f"home={row.home_win} away={row.away_win} draw={row.draw} "
                f"btts={row.btts_yes} totals={row.totals}"
            )
        return

    client = SportsPredictClient(sp_key or "dry-run")
    result = run_sync(
        source,
        client,
        dry_run=args.dry_run,
        update=args.update,
        verbose=args.verbose,
    )

    if result.preview:
        for line in result.preview:
            print(f"  {line}")

    print(
        f"\n{'Would submit' if args.dry_run else 'Submitted'}: "
        f"{result.submitted} new, {result.updated} updates, "
        f"{result.skipped} skipped"
        + (f", {result.failed} failed" if result.failed else "")
    )

    if args.save or not args.dry_run:
        label = "dry_run" if args.dry_run else "submitted"
        path = save_predictions(result, label=label)
        print(f"Predictions saved to {path}")

    # Remind about model* predictions that will improve closer to kickoff
    polymarket_pending = sum(
        1 for r in result.records
        if r.source in ("polymarket*",) and r.action not in ("unsubmitted",)
    )
    if polymarket_pending > 0:
        print(
            f"\n{polymarket_pending} prediction(s) tagged [polymarket*] are using the "
            f"statistical model because Polymarket hasn't opened those markets yet.\n"
            f"Run  python sync_odds.py --update  again 1-2 hours before kickoff to "
            f"replace them with live Polymarket prices."
        )

    if args.dry_run:
        print("Dry run — nothing submitted.")


if __name__ == "__main__":
    main()
