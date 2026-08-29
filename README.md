# Facebook GraphQL Full Scraper

**100% GraphQL API. $0 cost. No Apify. No Selenium. No browser.**

Search posts + fetch comments + fetch replies + batch processing — all via direct Facebook GraphQL API requests.

## What It Works

```
1. GraphQL search     → Keyword → post IDs ($0, ~1s, multi-page pagination)
2. GraphQL comments   → Fetch + paginate via end_cursor ($0, ~2s/post)
3. GraphQL replies    → Fetch + paginate via expansion_token ($0, ~1s/comment)
4. Batch runner       → Multiple targets from YAML config ($0, scalable)
```

### Key Features

- **$0 total cost** — No Apify, no Selenium, no browser, no proxy
- **Multi-page search** — 20-60+ posts per keyword via pagination
- **Server-side date filter** — `--since` / `--until` (YYYY-MM-DD)
- **Location filter** — `--location` (client-side keyword match)
- **Sort control** — `top` (by engagement) or `recent` (newest first)
- **Configurable depth** — 100, 200, or 9999 (full depth)
- **Reaction breakdown** — like, love, haha, wow, sad, angry, care per comment
- **Reply count** — `replies_fields.total_count` per comment
- **Hashtags & mentions** — Parsed from post message text
- **Author metadata** — `author_id`, `author_url` per post & comment
- **Batch processing** — 66+ targets from YAML config

### Performance Comparison

| Method | Posts | Comments | Replies | Time | Cost |
|:-------|:------|:---------|:--------|:-----|:-----|
| Native Selenium | 5 | 3 | 96 | 5.3 min | $0 |
| GraphQL + Apify search | 5 | 160 | 333 | 3.2 min | ~$0.05 |
| **100% GraphQL (single)** | **20** | **823** | **868** | **8.5 min** | **$0** |
| **100% GraphQL (batch)** | **32** | **870** | **634** | **10.5 min** | **$0** |

## Requirements

- Python 3.10+
- `requests`, `python-dotenv`, `pyyaml`
- Facebook cookies (exported from logged-in browser session)
  - Must include `c_user` and `xs` (session cookies)
  - Cookies expire every ~2-3 hours — re-export when needed

## Quick Start

### 1. Clone

```bash
git clone https://github.com/alfinnahuway/fb-graphql-full.git
cd fb-graphql-full
```

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Export cookies

1. Install **"Get cookies.txt LOCALLY"** extension in Chrome/Firefox
2. Log into Facebook
3. Export → Save as `fb_cookies.txt` in project root
4. Must include `c_user` and `xs` fields

### 4. Run — Single Keyword

```bash
# 20 posts, 100 comments each
python fb_graphql_full.py --keyword "Kebakaran" --max-posts 20 --max-comments 100

# Sort by newest (for risk detection)
python fb_graphql_full.py --keyword "DPR RI" --sort recent --max-comments 200

# Full depth
python fb_graphql_full.py --keyword "Pilpres" --max-comments 9999

# Filter by date range + location
python fb_graphql_full.py --keyword "Kalimantan" --since 2026-08-25 --until 2026-08-29 --location "Kalimantan" --sort recent --max-posts 20 --max-comments 50
```

### 5. Run — Batch (Multiple Targets)

```bash
# Dry run (preview all targets)
python fb_scraper_batch.py --config targets.yaml --dry-run

# Run all targets (66 parlimen)
python fb_scraper_batch.py --config targets.yaml

# Run single target
python fb_scraper_batch.py --config targets.yaml --target anies_baswedan

# Scheduled 2x/day
python fb_scraper_batch.py --config targets.yaml --schedule 2x
```

## Arguments — Single Run

| Argument | Default | Description |
|:---------|:--------|:------------|
| `--keyword` | Required | Search keyword |
| `--max-posts` | 5 | Max posts from search (multi-page) |
| `--max-comments` | 100 | Max comments per post (9999 = full) |
| `--sort` | top | `top` or `recent` |
| `--since` | None | Filter posts from date (YYYY-MM-DD) |
| `--until` | None | Filter posts until date (YYYY-MM-DD) |
| `--location` | None | Filter by location keyword |
| `--output` | auto | Output file path |

## Batch Config Format (targets.yaml)

```yaml
defaults:
  max_posts: 30
  max_comments: 100
  sort: top
  delay_between_keywords: 3
  delay_between_targets: 10

targets:
  - id: anies_baswedan
    name: "Anies Baswedan"
    category: "tokoh_publik"
    accounts:
      - "aniesbaswedan"
    keywords:
      - "Anies Baswedan"
      - "Pilkada Jakarta 2026"
    settings:
      max_posts: 30
      max_comments: 100
      sort: recent
      since: "2026-08-25"
      until: "2026-08-29"
```

## Output JSON Format

### Post

```json
{
  "post_id": "2284445269057441",
  "author": "Jaya Ulung",
  "author_id": "100024759698861",
  "author_url": "https://www.facebook.com/100024759698861",
  "url": "https://www.facebook.com/100024759698861/posts/2284445269057441",
  "permalink_url": "https://www.facebook.com/jaya.ulungajay/posts/pfbid...",
  "message": "Telah terjadi kebakaran pondok pesantren...",
  "hashtags": ["kebakaran", "kebakaranpondokpesantren"],
  "mentions": [],
  "timestamp": 1787924585,
  "feedback_id": "ZmVlZGJhY2s6...",
  "comments": [...]
}
```

### Comment

```json
{
  "name": "Iton",
  "author_id": "100001025595243",
  "author_url": "https://www.facebook.com/100001025595243",
  "text": "Infomu Ra jelas njalok di tabob i OPO pie",
  "likes_count": "9",
  "reactions": {
    "like": 7,
    "love": 2
  },
  "reply_count": 5,
  "timestamp": 1787925000,
  "comment_id": "Y29tbWVudD...",
  "feedback_id": "ZmVlZGJhY2s6...",
  "expansion_token": "...",
  "replies": [...]
}
```

### Reaction Types

| Node ID | Reaction |
|:--------|:---------|
| 1635855486666999 | like |
| 1678524932434102 | love |
| 478547315744583 | haha |
| 656520638348042 | wow |
| 616785628324312 | sad |
| 908950955142546 | angry |
| 1152124759564958 | care |

## GraphQL doc_ids

| Purpose | doc_id | Friendly Name |
|:---------|:-------|:--------------|
| Search posts | 28158587817158906 | SearchCometResultsPaginatedResultsQuery |
| Fetch comments | 27806180149070312 | CommentsListComponentsPaginationQuery |
| Fetch replies | 26570577339199586 | Depth1CommentsListPaginationQuery |

### Date Filter Format (Server-Side)

```json
{
  "name": "creation_time",
  "args": "{\"start_year\":\"2026\",\"start_month\":\"2026-8\",\"start_day\":\"2026-8-25\",\"end_year\":\"2026\",\"end_month\":\"2026-8\",\"end_day\":\"2026-8-29\"}"
}
```

- `filters` = array of JSON-encoded **strings** (not objects)
- `args` = stringified JSON (not number/object)
- Month/day **NOT zero-padded** (YYYY-M-D format)

## Response Paths

```
Search:
  data.serpResponse.results.edges[].rendering_strategy.view_model.click_model.story
    → post_id, feedback.id, owning_profile.name, creation_time, permalink_url

Comments:
  data.node.comment_rendering_instance_for_feed_location.comments.edges[]
    → 10 per page, page_info.end_cursor = next page
    → feedback.reactors.count_reduced = total reactions
    → feedback.top_reactions.edges[].reaction_count = per-type breakdown
    → feedback.replies_fields.total_count = reply count

Replies:
  data.node.replies_connection.edges[]
    → 10 per page, page_info.end_cursor = next page
```

## Project Structure

```
fb-graphql-full/
├── fb_graphql_full.py    # Main pipeline (search + comments + replies)
├── fb_scraper_batch.py   # Batch runner (multiple targets from YAML)
├── targets.yaml          # Config file (66 parlimen template)
├── config.py             # Config loader
├── .env.example          # Environment template
├── requirements.txt      # Dependencies (requests + dotenv + pyyaml)
├── README.md
├── fb_cookies.txt        # Your FB cookies (gitignored)
└── output/
    ├── batch/            # Batch output (per-target + summary)
    └── *.json            # Single run output
```

## Cookie Expiry

| Cookie | Duration | Purpose |
|:-------|:---------|:--------|
| `c_user` | ~2-3 hours | User ID |
| `xs` | ~2-3 hours | Session token |
| `datr` | ~2 years | Browser fingerprint |

> When you see `USER_ID: 0` → re-export cookies!

## Troubleshooting

### "Login failed — cookies may be expired"
Re-export cookies. Session cookies expire every 2-3 hours.

### "missing_required_variable_value"
Facebook rotated doc_ids. Capture new ones from browser DevTools → Network → graphql requests.

### Empty search results
Try different keywords. Facebook search may rate-limit if too many requests in short time.

### "noncoercible_variable_value"
Filter format wrong. `filters` must be array of **strings** (JSON-encoded), `args` must be stringified JSON.

## License

MIT
