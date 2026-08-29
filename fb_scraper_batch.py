"""
Facebook Scraper — Batch Runner
================================
Run scraper for multiple targets from YAML config.

Usage:
  python fb_scraper_batch.py --config targets.yaml
  python fb_scraper_batch.py --config targets.yaml --target anies_baswedan
  python fb_scraper_batch.py --config targets.yaml --dry-run
  python fb_scraper_batch.py --config targets.yaml --schedule 2x
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Installing pyyaml...")
    os.system(f"{sys.executable} -m pip install pyyaml")
    import yaml

# Add project dir to path
sys.path.insert(0, str(Path(__file__).parent))

from fb_graphql_full import FacebookGraphQLClient, run_pipeline
from config import FB_COOKIES_PATH, OUTPUT_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fb-batch")


def load_config(config_path):
    """Load YAML config and merge with defaults."""
    with open(config_path) as f:
        config = yaml.safe_load(f)

    defaults = config.get("defaults", {})
    targets = config.get("targets", [])

    # Merge defaults into each target's settings
    for target in targets:
        target_settings = target.get("settings", {})
        merged = {**defaults, **target_settings}
        target["settings"] = merged

    return config, targets


def run_target(client, target, output_dir):
    """Run scraper for a single target (all keywords)."""
    target_id = target["id"]
    target_name = target["name"]
    settings = target.get("settings", {})
    keywords = target.get("keywords", [])

    log.info(f"\n{'─'*60}")
    log.info(f"Target: {target_name} (id={target_id})")
    log.info(f"  Keywords: {keywords}")
    log.info(f"  Settings: max_posts={settings.get('max_posts')}, "
             f"max_comments={settings.get('max_comments')}, "
             f"sort={settings.get('sort')}")
    log.info(f"{'─'*60}")

    target_start = time.time()
    all_results = []

    for ki, keyword in enumerate(keywords):
        log.info(f"\n  Keyword {ki+1}/{len(keywords)}: '{keyword}'")

        # Run pipeline for this keyword
        kw_start = time.time()

        # Search posts
        posts = client.search_posts(
            keyword,
            max_posts=settings.get("max_posts", 30),
            since=settings.get("since"),
            until=settings.get("until"),
            location_id=None,  # location filter still client-side
        )

        # Location filter (client-side)
        location = settings.get("location")
        if location:
            loc_lower = location.lower()
            filtered = []
            for p in posts:
                msg = (p.get("message", "") or "").lower()
                author = (p.get("author", "") or "").lower()
                if loc_lower in msg or loc_lower in author:
                    filtered.append(p)
            posts = filtered
            log.info(f"  Location filter: {len(posts)} posts")

        # Fetch comments + replies for each post
        sort_mode = settings.get("sort", "top")
        max_comments = settings.get("max_comments", 100)
        total_comments = 0
        total_replies = 0

        for pi, post in enumerate(posts):
            if not post.get("post_id"):
                continue
            t0 = time.time()
            comments = client.fetch_comments(
                post["post_id"],
                max_comments=max_comments,
                sort_mode=sort_mode,
            )
            post["comments"] = comments
            pc = len(comments)
            pr = sum(len(c.get("replies", [])) for c in comments)
            total_comments += pc
            total_replies += pr
            elapsed = time.time() - t0
            log.info(f"    Post {pi+1}: {pc}c + {pr}r ({elapsed:.1f}s)")
            time.sleep(1)

        kw_elapsed = time.time() - kw_start
        log.info(f"  Keyword '{keyword}': {len(posts)} posts, "
                 f"{total_comments} comments + {total_replies} replies "
                 f"({kw_elapsed:.1f}s)")

        all_results.append({
            "keyword": keyword,
            "posts_found": len(posts),
            "total_comments": total_comments,
            "total_replies": total_replies,
            "elapsed_seconds": round(kw_elapsed, 1),
            "posts": posts,
        })

        # Delay between keywords
        delay = settings.get("delay_between_keywords", 3)
        if ki < len(keywords) - 1:
            log.info(f"  Waiting {delay}s before next keyword...")
            time.sleep(delay)

    target_elapsed = time.time() - target_start

    # Save target output
    result = {
        "target_id": target_id,
        "target_name": target_name,
        "category": target.get("category", ""),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(target_elapsed, 1),
        "keywords": keywords,
        "total_posts": sum(r["posts_found"] for r in all_results),
        "total_comments": sum(r["total_comments"] for r in all_results),
        "total_replies": sum(r["total_replies"] for r in all_results),
        "results": all_results,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = output_dir / f"{target_id}_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info(f"\n  Target complete: {result['total_posts']} posts, "
             f"{result['total_comments']} comments + {result['total_replies']} replies "
             f"in {target_elapsed:.1f}s")
    log.info(f"  Output: {output_file}")

    return result


def run_batch(config_path, target_filter=None, dry_run=False):
    """Run scraper for all targets in config."""
    config, targets = load_config(config_path)
    defaults = config.get("defaults", {})

    log.info("=" * 60)
    log.info("Facebook Scraper — Batch Run")
    log.info(f"  Config:        {config_path}")
    log.info(f"  Total targets:  {len(targets)}")
    if target_filter:
        log.info(f"  Filter:        {target_filter}")
    if dry_run:
        log.info("  Mode:          DRY RUN (no scraping)")
    log.info("=" * 60)

    # Filter targets if specified
    if target_filter:
        targets = [t for t in targets if t["id"] == target_filter]
        if not targets:
            log.error(f"Target '{target_filter}' not found in config!")
            return

    # Dry run — just show what would be scraped
    if dry_run:
        log.info("\n=== DRY RUN — Targets to scrape ===")
        total_keywords = 0
        for i, t in enumerate(targets):
            kw_count = len(t.get("keywords", []))
            total_keywords += kw_count
            log.info(f"  [{i+1}] {t['name']} (id={t['id']})")
            log.info(f"      Keywords: {t.get('keywords', [])}")
            log.info(f"      Settings: {t.get('settings', {})}")
        log.info(f"\n  Total: {len(targets)} targets, {total_keywords} keywords")
        return

    # Create output dir
    output_dir = OUTPUT_DIR / "batch"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Authenticate once
    client = FacebookGraphQLClient(FB_COOKIES_PATH)
    client.authenticate()

    # Run each target
    all_target_results = []
    batch_start = time.time()

    for i, target in enumerate(targets):
        log.info(f"\n{'='*60}")
        log.info(f"Target {i+1}/{len(targets)}: {target['name']}")
        log.info(f"{'='*60}")

        try:
            result = run_target(client, target, output_dir)
            all_target_results.append({
                "target_id": result["target_id"],
                "target_name": result["target_name"],
                "total_posts": result["total_posts"],
                "total_comments": result["total_comments"],
                "total_replies": result["total_replies"],
                "elapsed_seconds": result["elapsed_seconds"],
            })
        except Exception as e:
            log.error(f"  Target failed: {e}")
            all_target_results.append({
                "target_id": target["id"],
                "target_name": target["name"],
                "error": str(e),
            })

        # Delay between targets
        delay = defaults.get("delay_between_targets", 10)
        if i < len(targets) - 1:
            log.info(f"\n  Waiting {delay}s before next target...")
            time.sleep(delay)

    # Save batch summary
    batch_elapsed = time.time() - batch_start
    summary = {
        "batch_run_at": datetime.now(timezone.utc).isoformat(),
        "config_file": str(config_path),
        "total_targets": len(targets),
        "total_posts": sum(r.get("total_posts", 0) for r in all_target_results),
        "total_comments": sum(r.get("total_comments", 0) for r in all_target_results),
        "total_replies": sum(r.get("total_replies", 0) for r in all_target_results),
        "elapsed_seconds": round(batch_elapsed, 1),
        "targets": all_target_results,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    summary_file = output_dir / f"batch_summary_{timestamp}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log.info("\n" + "=" * 60)
    log.info("Batch complete!")
    log.info(f"  Total targets:   {summary['total_targets']}")
    log.info(f"  Total posts:     {summary['total_posts']}")
    log.info(f"  Total comments:  {summary['total_comments']}")
    log.info(f"  Total replies:   {summary['total_replies']}")
    log.info(f"  Total elapsed:   {batch_elapsed:.1f}s ({batch_elapsed/60:.1f} min)")
    log.info(f"  Summary:          {summary_file}")
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Facebook Scraper — Batch Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all targets
  python fb_scraper_batch.py --config targets.yaml

  # Run single target only
  python fb_scraper_batch.py --config targets.yaml --target anies_baswedan

  # Dry run (show what would be scraped)
  python fb_scraper_batch.py --config targets.yaml --dry-run

  # Schedule (2x/day = 12h interval)
  python fb_scraper_batch.py --config targets.yaml --schedule 2x
        """,
    )
    parser.add_argument("--config", required=True, help="YAML config file path")
    parser.add_argument("--target", default=None, help="Run specific target by ID")
    parser.add_argument("--dry-run", action="store_true", help="Show targets without scraping")
    parser.add_argument("--schedule", choices=["1x", "2x", "4x"], default=None,
                        help="Schedule frequency: 1x/day, 2x/day, 4x/day")
    args = parser.parse_args()

    if args.schedule:
        intervals = {"1x": 86400, "2x": 43200, "4x": 21600}
        interval = intervals[args.schedule]
        log.info(f"Scheduled mode: {args.schedule}/day (every {interval}s)")
        log.info("Press Ctrl+C to stop")
        try:
            while True:
                run_batch(args.config, args.target, args.dry_run)
                log.info(f"\nNext run in {interval}s...")
                time.sleep(interval)
        except KeyboardInterrupt:
            log.info("\nStopped by user.")
    else:
        run_batch(args.config, args.target, args.dry_run)


if __name__ == "__main__":
    main()
