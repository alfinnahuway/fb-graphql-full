# Facebook GraphQL Full Scraper

**100% GraphQL API. $0 cost. No Apify. No Selenium. No browser.**

Search posts + fetch comments + fetch replies — all via direct Facebook GraphQL API requests.

## How It Works

```
1. GraphQL search     → Keyword → post IDs ($0, ~1s)
2. GraphQL comments   → Fetch + paginate via end_cursor ($0, ~2s/post)
3. GraphQL replies    → Fetch + paginate via expansion_token ($0, ~1s/comment)
```

### Key Features

- **$0 total cost** — No Apify, no Selenium, no browser, no proxy
- **274 comments + 366 replies** from 5 posts in 5.5 min
- **GraphQL search** — Keyword search via `SearchCometResultsPaginatedResultsQuery`
- **Comment pagination** — Unlimited via `end_cursor`
- **Reply pagination** — Unlimited via `expansion_token`
- **Sort control** — `top` (by engagement) or `recent` (newest first)
- **Configurable depth** — 100, 200, or 9999 (full depth)

### Performance Comparison

| Method | Posts | Comments | Replies | Time | Cost |
|:-------|:------|:---------|:--------|:-----|:-----|
| Native Selenium | 5 | 3 | 96 | 5.3 min | $0 |
| GraphQL + Apify search | 5 | 160 | 333 | 3.2 min | ~$0.05 |
| **100% GraphQL** | **5** | **274** | **366** | **5.5 min** | **$0** |

## Requirements

- Python 3.10+
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

### 3. Configure

```bash
cp .env.example .env
# Edit .env if needed (defaults work out of the box)
```

### 4. Export cookies

1. Install **"Get cookies.txt LOCALLY"** extension in Chrome/Firefox
2. Log into Facebook
3. Export → Save as `fb_cookies.txt` in project root
4. Must include `c_user` and `xs` fields

### 5. Run

```bash
# 5 posts, 100 comments each
python fb_graphql_full.py --keyword "Kebakaran" --max-posts 5 --max-comments 100

# Sort by newest (for risk detection)
python fb_graphql_full.py --keyword "DPR RI" --sort recent --max-comments 200

# Full depth
python fb_graphql_full.py --keyword "Pilpres" --max-comments 9999
```

## Arguments

| Argument | Default | Description |
|:---------|:--------|:------------|
| `--keyword` | Required | Search keyword |
| `--max-posts` | 5 | Max posts from search |
| `--max-comments` | 100 | Max comments per post (9999 = full) |
| `--sort` | top | `top` or `recent` |
| `--output` | auto | Output file path |

## GraphQL doc_ids

| Purpose | doc_id | Friendly Name |
|:---------|:-------|:--------------|
| Search posts | 28158587817158906 | SearchCometResultsPaginatedResultsQuery |
| Fetch comments | 27806180149070312 | CommentsListComponentsPaginationQuery |
| Fetch replies | 26570577339199586 | Depth1CommentsListPaginationQuery |

## Response Paths

```
Search:
  data.serpResponse.results.edges[].rendering_strategy.view_model.click_model.story
    → post_id, feedback.id, owning_profile.name, creation_time

Comments:
  data.node.comment_rendering_instance_for_feed_location.comments.edges[]
    → 10 per page, page_info.end_cursor = next page

Replies:
  data.node.replies_connection.edges[]
    → 10 per page, page_info.end_cursor = next page
```

## Cookie Expiry

| Cookie | Duration | Purpose |
|:-------|:---------|:--------|
| `c_user` | ~2-3 hours | User ID |
| `xs` | ~2-3 hours | Session token |
| `datr` | ~2 years | Browser fingerprint |

> When you see `USER_ID: 0` → re-export cookies!

## Project Structure

```
fb-graphql-full/
├── fb_graphql_full.py    # Main pipeline (search + comments + replies)
├── config.py             # Config loader
├── .env.example          # Environment template
├── requirements.txt      # Dependencies (requests + dotenv only)
├── README.md
├── fb_cookies.txt        # Your FB cookies (gitignored)
└── output/               # Results
```

## Troubleshooting

### "Login failed — cookies may be expired"
Re-export cookies. Session cookies expire every 2-3 hours.

### "missing_required_variable_value"
Facebook rotated doc_ids. Capture new ones from browser DevTools → Network → graphql requests.

### Empty search results
Try different keywords. Facebook search may rate-limit if too many requests in short time.

## License

MIT
