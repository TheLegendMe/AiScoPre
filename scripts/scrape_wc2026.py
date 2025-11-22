#!/usr/bin/env python3
"""Fetch publicly available 2026 World Cup content and odds in a compliant way.

The script is designed with the following guardrails:
1. Domains must be explicitly allow-listed via CLI flags.
2. robots.txt is fetched before crawling a URL; the script aborts if fetching is disallowed.
3. User-Agent identifies the project so site owners can reach out.
4. Rate limits between requests (configurable via --sleep).

By default the script runs in "offline" mode against data/sample_wc2026_source.html
so you can verify the parsing logic without hitting external websites.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional
from urllib import parse as urlparse
from urllib import robotparser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_HTML = ROOT / "data" / "sample_wc2026_source.html"
DEFAULT_OUTPUT = ROOT / "data" / "latest_wc2026_info.json"

USER_AGENT = "AiScoPreResearchBot/1.0 (+https://github.com/oym/AiScoPre)"
LOG = logging.getLogger("scraper")


class ComplianceError(RuntimeError):
    """Raised when a compliance rule (robots/allowlist) would be violated."""


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-url",
        help="URL to scrape. When omitted, the bundled sample HTML file is used.",
    )
    parser.add_argument(
        "--html-file",
        type=Path,
        help="Local HTML file to parse instead of downloading.",
    )
    parser.add_argument(
        "--allow-domain",
        action="append",
        dest="allow_domains",
        default=[],
        help="Allow a domain to be scraped (must match netloc, e.g. www.fifa.com).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write JSON output (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep between HTTP requests (for politeness).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and log data without writing output.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug logging."
    )
    return parser.parse_args(args=argv)


def ensure_domain_allowed(url: str, allowed_domains: List[str]) -> None:
    if not allowed_domains:
        raise ComplianceError(
            "No domain allow-list configured. Pass --allow-domain example.com "
            "to acknowledge you have permission to crawl the target site."
        )
    netloc = urlparse.urlparse(url).netloc
    if netloc not in allowed_domains:
        raise ComplianceError(
            f"Domain {netloc} is not in allow-list {allowed_domains}. "
            "Add it via --allow-domain."
        )


def check_robots(session: requests.Session, url: str) -> None:
    parsed = urlparse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    resp = session.get(robots_url, timeout=10)
    if resp.status_code >= 400:
        raise ComplianceError(
            f"Unable to fetch robots.txt from {robots_url} (status {resp.status_code})."
        )
    rp = robotparser.RobotFileParser()
    rp.parse(resp.text.splitlines())
    if not rp.can_fetch(USER_AGENT, url):
        raise ComplianceError(
            f"robots.txt for {parsed.netloc} disallows fetching {url} with agent {USER_AGENT}."
        )


def fetch_html(session: requests.Session, url: str, sleep_s: float) -> str:
    check_robots(session, url)
    LOG.info("Fetching %s", url)
    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    if sleep_s > 0:
        time.sleep(sleep_s)
    return resp.text


def parse_tournament_info(soup: BeautifulSoup) -> dict:
    section = soup.select_one("#tournament-meta")
    if not section:
        return {}
    info = {
        "name": section.get("data-tournament-name"),
    }
    for div in section.select("[data-field]"):
        key = div["data-field"]
        info[key] = " ".join(div.get_text(strip=True).split())
    if "hosts" in info:
        info["hosts"] = [part.strip() for part in info["hosts"].split(",")]
    if "cities" in info:
        info["cities"] = [part.strip() for part in info["cities"].split(",")]
    return info


def parse_odds(soup: BeautifulSoup) -> List[dict]:
    table = soup.select_one("table.odds-table")
    if not table:
        return []
    source_url = table.get("data-source-url")
    odds = []
    for row in table.select("tbody tr"):
        team_name_el = row.select_one(".team-name")
        odds_el = row.select_one(".decimal-odds")
        if not team_name_el or not odds_el:
            continue
        team_name = " ".join(team_name_el.get_text(strip=True).split())
        team_id = row.get("data-team-id") or team_name.upper().replace(" ", "_")
        try:
            decimal_odds = float(odds_el.get_text(strip=True))
        except ValueError:
            continue
        implied = round(1.0 / decimal_odds, 4) if decimal_odds > 0 else None
        odds.append(
            {
                "team_id": team_id,
                "team_name": team_name,
                "decimal_odds": decimal_odds,
                "implied_probability": implied,
                "source_url": source_url,
            }
        )
    return odds


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    html_text: str
    if args.html_file:
        html_text = args.html_file.read_text(encoding="utf-8")
        LOG.info("Loaded HTML from %s", args.html_file)
    elif args.source_url:
        ensure_domain_allowed(args.source_url, args.allow_domains)
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        html_text = fetch_html(session, args.source_url, args.sleep)
    else:
        html_text = SAMPLE_HTML.read_text(encoding="utf-8")
        LOG.info("Using bundled sample HTML %s", SAMPLE_HTML)

    soup = BeautifulSoup(html_text, "html.parser")
    tournament = parse_tournament_info(soup)
    odds = parse_odds(soup)
    payload = {
        "tournament": tournament,
        "odds_last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": args.source_url or str(args.html_file or SAMPLE_HTML),
        "odds": odds,
    }

    if args.dry_run:
        LOG.info("Dry-run payload:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOG.info("Wrote %s odds entries to %s", len(odds), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
