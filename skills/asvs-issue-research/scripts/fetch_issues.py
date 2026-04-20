#!/usr/bin/env python3
"""
ASVS Issue Research Fetcher
Usage:
  python3 fetch_issues.py <requirement_id> [old_id]
  python3 fetch_issues.py --issue <issue_number>

Examples:
  python3 fetch_issues.py 1.2.4
  python3 fetch_issues.py 6.3.1 V6.3.1
  python3 fetch_issues.py --issue 1182
"""

import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

REPO = "OWASP/ASVS"
BASE = "https://api.github.com"
HEADERS = {
    "User-Agent": "ASVS-Research-Script/1.0",
    "Accept": "application/vnd.github+json",
}


def get(url, retries=3):
    """GET a URL with retry on rate limit."""
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                remaining = r.headers.get("X-RateLimit-Remaining", "?")
                print(f"  [API] GET {url[:90]}... (remaining: {remaining})", file=sys.stderr)
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 403:
                reset = e.headers.get("X-RateLimit-Reset")
                wait = max(int(reset) - int(time.time()) + 2, 10) if reset else 15
                print(f"  [RATE LIMIT] Sleeping {wait}s...", file=sys.stderr)
                time.sleep(wait)
            elif e.code == 422:
                print(f"  [SKIP] 422 Unprocessable: {url}", file=sys.stderr)
                return None
            else:
                raise
        except Exception as e:
            print(f"  [ERROR] {e} on attempt {attempt+1}", file=sys.stderr)
            time.sleep(3)
    return None


def search_issues(query, label=""):
    """Search issues/PRs, paginate through all results."""
    all_items = []
    page = 1
    while True:
        url = (
            f"{BASE}/search/issues"
            f"?q={urllib.parse.quote(query)}&sort=updated&order=desc"
            f"&per_page=30&page={page}"
        )
        data = get(url)
        if not data:
            break
        items = data.get("items", [])
        total = data.get("total_count", 0)
        print(f"  [{label}] Page {page}: {len(items)} results (total={total})", file=sys.stderr)
        all_items.extend(items)
        if len(items) < 30 or len(all_items) >= total:
            break
        page += 1
        time.sleep(6)  # Stay well under 10 req/min for search endpoint
    return all_items


def fetch_issue_detail(number):
    """Fetch full issue body."""
    return get(f"{BASE}/repos/{REPO}/issues/{number}")


def fetch_comments(number):
    """Fetch all comments for an issue."""
    all_comments = []
    page = 1
    while True:
        url = f"{BASE}/repos/{REPO}/issues/{number}/comments?per_page=50&page={page}"
        data = get(url)
        if not data:
            break
        all_comments.extend(data)
        if len(data) < 50:
            break
        page += 1
        time.sleep(1)
    return all_comments


def fetch_single_issue(number):
    """Fetch a single issue by number with full detail."""
    print(f"\nFetching issue #{number}...", file=sys.stderr)
    detail = fetch_issue_detail(number)
    if not detail:
        print(f"Could not fetch issue #{number}", file=sys.stderr)
        return None
    comments = fetch_comments(number)
    return build_issue_record(detail, comments)


def build_issue_record(detail, comments):
    """Build a clean record from API response."""
    return {
        "number": detail["number"],
        "title": detail["title"],
        "type": "pull_request" if "pull_request" in detail else "issue",
        "state": detail["state"],
        "author": detail["user"]["login"],
        "created_at": detail["created_at"][:10],
        "updated_at": detail["updated_at"][:10],
        "labels": [l["name"] for l in detail.get("labels", [])],
        "html_url": detail["html_url"],
        "body": detail.get("body") or "",
        "comment_count": detail.get("comments", 0),
        "comments": [
            {
                "author": c["user"]["login"],
                "date": c["updated_at"][:10],
                "body": c.get("body") or "",
            }
            for c in comments
        ],
    }


def deduplicate(items):
    """Remove duplicate issues by number, keep most recently fetched."""
    seen = {}
    for item in items:
        n = item["number"]
        if n not in seen:
            seen[n] = item
    return list(seen.values())


def main():
    import urllib.parse

    args = sys.argv[1:]

    # Single issue mode
    if args and args[0] == "--issue":
        if len(args) < 2:
            print("Usage: fetch_issues.py --issue <number>", file=sys.stderr)
            sys.exit(1)
        result = fetch_single_issue(int(args[1]))
        if result:
            print(json.dumps([result], indent=2))
        sys.exit(0)

    if not args:
        print("Usage: fetch_issues.py <requirement_id> [old_id]", file=sys.stderr)
        print("  e.g. fetch_issues.py 1.2.4", file=sys.stderr)
        sys.exit(1)

    req_id = args[0]
    old_id = args[1] if len(args) > 1 else None

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"ASVS Issue Research: {req_id}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    all_items = []

    # Search 1: exact ID in quotes
    print(f"\nSearch 1: \"{req_id}\" in OWASP/ASVS...", file=sys.stderr)
    q1 = f'"{req_id}" repo:{REPO}'
    items1 = search_issues(q1, label=f'"{req_id}"')
    all_items.extend(items1)
    time.sleep(6)

    # Search 2: V-prefixed variant
    v_id = f"V{req_id}" if not req_id.startswith("V") else req_id
    if v_id != req_id:
        print(f"\nSearch 2: \"{v_id}\" variant...", file=sys.stderr)
        q2 = f'"{v_id}" repo:{REPO}'
        items2 = search_issues(q2, label=f'"{v_id}"')
        all_items.extend(items2)
        time.sleep(6)

    # Search 3: old 4.0 ID if provided
    if old_id:
        print(f"\nSearch 3: old ID \"{old_id}\"...", file=sys.stderr)
        q3 = f'"{old_id}" repo:{REPO}'
        items3 = search_issues(q3, label=f'"{old_id}"')
        all_items.extend(items3)
        time.sleep(6)

    # Deduplicate
    unique = deduplicate(all_items)
    print(f"\nFound {len(unique)} unique issues/PRs. Fetching full details...", file=sys.stderr)

    # Fetch full detail for each
    results = []
    for i, item in enumerate(unique):
        number = item["number"]
        print(f"\n[{i+1}/{len(unique)}] Fetching #{number}: {item['title'][:60]}...", file=sys.stderr)
        detail = fetch_issue_detail(number)
        if not detail:
            continue
        time.sleep(1)
        comments = fetch_comments(number)
        results.append(build_issue_record(detail, comments))
        time.sleep(1)

    # Sort by updated_at descending
    results.sort(key=lambda x: x["updated_at"], reverse=True)

    # Tag each result with a recency bucket per Stage 3 of the skill
    today = datetime.utcnow()
    for r in results:
        try:
            updated = datetime.strptime(r["updated_at"], "%Y-%m-%d")
            days_old = (today - updated).days
        except Exception:
            days_old = 9999
        if days_old <= 180:
            r["recency_bucket"] = "high"  # last 6 months
        elif days_old <= 540:
            r["recency_bucket"] = "medium"  # 6-18 months
        elif days_old <= 1095:
            r["recency_bucket"] = "low"  # 18mo-3y
        else:
            r["recency_bucket"] = "archival"  # >3y
        r["days_since_update"] = days_old

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Complete. {len(results)} issues fetched.", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Print summary table to stderr for quick scan, grouped by recency bucket
    bucket_labels = {
        "high": "RECENT (<6mo) - high weight, current consensus",
        "medium": "MEDIUM (6-18mo) - likely still relevant",
        "low": "OLDER (18mo-3y) - historical context",
        "archival": "ARCHIVAL (>3y) - origin-of-wording only",
    }
    for bucket in ["high", "medium", "low", "archival"]:
        bucketed = [r for r in results if r["recency_bucket"] == bucket]
        if not bucketed:
            continue
        print(f"\n--- {bucket_labels[bucket]} ({len(bucketed)} items) ---", file=sys.stderr)
        print(f"{'#':>6}  {'Updated':10}  {'State':6}  {'Type':12}  Title", file=sys.stderr)
        for r in bucketed:
            print(
                f"#{r['number']:5}  {r['updated_at']:10}  {r['state']:6}  {r['type']:12}  {r['title'][:50]}",
                file=sys.stderr,
            )

    # Output full JSON to stdout
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
