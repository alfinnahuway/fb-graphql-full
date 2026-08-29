"""
Facebook GraphQL Full Scraper — 100% GraphQL, $0, No Apify, No Selenium
======================================================================
All-in-one pipeline:
  1. GraphQL search posts by keyword ($0)
  2. GraphQL fetch comments + pagination ($0)
  3. GraphQL fetch replies + pagination ($0)

Speed: ~3-5 seconds per post for 100 comments + replies
Cost: $0 (pure requests, no external services)

Usage:
  python fb_graphql_full.py --keyword "Kebakaran" --max-posts 5 --max-comments 100
  python fb_graphql_full.py --keyword "DPR RI" --sort recent --max-comments 200
  python fb_graphql_full.py --keyword "Pilpres" --max-comments 9999
"""

import argparse
import base64
import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fb-graphql-full")


class FacebookGraphQLClient:
    """Authenticated Facebook GraphQL client using cookies."""

    GRAPHQL_URL = "https://www.facebook.com/api/graphql/"
    SEARCH_DOC_ID = "28158587817158906"
    COMMENTS_DOC_ID = "27806180149070312"
    REPLIES_DOC_ID = "26570577339199586"

    # Relay providers required by search query (captured from real FB traffic)
    RELAY_PROVIDERS = {
        "__relay_internal__pv__GHLShouldChangeAdIdFieldNamerelayprovider": True,
        "__relay_internal__pv__GHLShouldChangeSponsoredDataFieldNamerelayprovider": True,
        "__relay_internal__pv__CometFeedStory_enable_reactor_facepilerelayprovider": False,
        "__relay_internal__pv__CometFeedStory_enable_social_bubblesrelayprovider": False,
        "__relay_internal__pv__CometFeedStory_enable_post_permalink_white_space_clickrelayprovider": False,
        "__relay_internal__pv__CometUFICommentActionLinksRewriteEnabledrelayprovider": True,
        "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
        "__relay_internal__pv__IsWorkUserrelayprovider": False,
        "__relay_internal__pv__TestPilotShouldIncludeDemoAdUseCaserelayprovider": False,
        "__relay_internal__pv__FBReels_deprecate_short_form_video_context_gkrelayprovider": True,
        "__relay_internal__pv__FBReels_enable_view_dubbed_audio_type_gkrelayprovider": True,
        "__relay_internal__pv__CometFeedShareMedia_shouldPrefetchShareImagerelayprovider": False,
        "__relay_internal__pv__CometImmersivePhotoCanUserDisable3DMotionrelayprovider": False,
        "__relay_internal__pv__WorkCometIsEmployeeGKProviderrelayprovider": False,
        "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
        "__relay_internal__pv__FBReelsMediaFooter_comet_enable_reels_ads_gkrelayprovider": True,
        "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False,
        "__relay_internal__pv__CometUFICommentAutoTranslationTyperelayprovider": "AUTO_TRANSLATE",
        "__relay_internal__pv__CometUFIShareActionMigrationrelayprovider": True,
        "__relay_internal__pv__CometUFISingleLineUFIrelayprovider": True,
        "__relay_internal__pv__relay_provider_comet_ufi_ssr_seo_deferrelayprovider": True,
        "__relay_internal__pv__CometUFI_dedicated_comment_routable_dialog_gkrelayprovider": True,
        "__relay_internal__pv__ReelsIFUCard_reelsIFULikeCountrelayprovider": False,
        "__relay_internal__pv__FBReelsIFUTileContent_reelsIFUPlayOnHoverrelayprovider": True,
        "__relay_internal__pv__GroupsCometGYSJFeedItemHeightrelayprovider": 206,
        "__relay_internal__pv__StoriesShouldEnablePhotosensitiveContentWarningrelayprovider": False,
        "__relay_internal__pv__ShouldEnableBakedInTextStoriesrelayprovider": False,
        "__relay_internal__pv__StoriesShouldIncludeFbNotesrelayprovider": True,
    }

    # Comments query relay providers
    COMMENTS_RELAY = {
        "__relay_internal__pv__CometUFICommentAutoTranslationTyperelayprovider": "AUTO_TRANSLATE",
        "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
        "__relay_internal__pv__CometUFICommentActionLinksRewriteEnabledrelayprovider": True,
        "__relay_internal__pv__IsWorkUserrelayprovider": False,
    }

    def __init__(self, cookies_path):
        self.cookies = {}
        self.session = requests.Session()
        self.fb_dtsg = ""
        self.lsd = ""
        self.user_id = ""
        self._load_cookies(cookies_path)

    def _load_cookies(self, path):
        cookies_path = Path(path)
        if not cookies_path.exists():
            log.error(f"Cookies file not found: {path}")
            sys.exit(1)
        with open(cookies_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    self.cookies[parts[5]] = parts[6]
        self.user_id = self.cookies.get("c_user", "0")
        log.info(f"Loaded {len(self.cookies)} cookies | c_user={self.user_id}")

    def authenticate(self):
        self.session.cookies.update(self.cookies)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Upgrade-Insecure-Requests": "1",
        })

        r = self.session.get("https://www.facebook.com/", timeout=15)
        log.info(f"Homepage: {r.status_code}, {len(r.text)} chars")

        for pattern in [r'"DTSGInitialData",\[\],\{"token":"([^"]+)"', r'"dtsg":\{"token":"([^"]+)"']:
            match = re.search(pattern, r.text)
            if match:
                self.fb_dtsg = match.group(1)
                break

        lsd_match = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', r.text)
        if lsd_match:
            self.lsd = lsd_match.group(1)

        user_match = re.search(r'"USER_ID":"(\d+)"', r.text)
        if user_match and user_match.group(1) != "0":
            log.info(f"✓ Logged in as USER_ID: {user_match.group(1)}")
        else:
            log.error("✗ Login failed — cookies may be expired!")
            sys.exit(1)

        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-ASBD-ID": "198477",
            "Origin": "https://www.facebook.com",
            "Referer": "https://www.facebook.com/",
        })
        log.info(f"  fb_dtsg: {self.fb_dtsg[:30]}...")

    def _graphql(self, doc_id, variables, friendly_name):
        payload = {
            "av": self.user_id,
            "__user": self.user_id,
            "__a": "1",
            "fb_dtsg": self.fb_dtsg,
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": friendly_name,
            "server_timestamps": "true",
            "doc_id": doc_id,
            "variables": json.dumps(variables),
        }
        self.session.headers["X-FB-Friendly-Name"] = friendly_name
        r = self.session.post(self.GRAPHQL_URL, data=payload, timeout=30)
        text = r.text.strip()
        if text.startswith("for (;;);"):
            text = text[len("for (;;);"):]
        try:
            return json.loads(text.split("\n")[0].strip())
        except:
            return None

    # ─── Search ──────────────────────────────────────────────────

    def search_posts(self, keyword, max_posts=20):
        log.info(f"Searching Facebook for '{keyword}' (max {max_posts})...")
        all_posts = []
        cursor = None
        page = 0

        while len(all_posts) < max_posts:
            page += 1
            variables = {
                "allow_streaming": False,
                "args": {
                    "callsite": "COMET_GLOBAL_SEARCH",
                    "config": {
                        "exact_match": False,
                        "high_confidence_config": None,
                        "intercept_config": None,
                        "sts_disambiguation": None,
                        "watch_config": None,
                    },
                    "context": {"bsid": str(uuid.uuid4()), "tsid": None},
                    "experience": {
                        "client_defined_experiences": ["ADS_PARALLEL_FETCH"],
                        "encoded_server_defined_params": None,
                        "fbid": None,
                        "type": "POSTS_TAB",
                    },
                    "filters": [],
                    "text": keyword,
                },
                "count": min(max_posts - len(all_posts), 8),
                "cursor": cursor,
                "feedLocation": "SEARCH",
                "feedbackSource": 23,
                "fetch_filters": True,
                "focusCommentID": None,
                "locale": None,
                "privacySelectorRenderLocation": "COMET_STREAM",
                "referringStoryRenderLocation": None,
                "renderLocation": "search_results_page",
                "scale": 1,
                "stream_initial_count": 0,
                "useDefaultActor": False,
                **self.RELAY_PROVIDERS,
            }

            data = self._graphql(
                self.SEARCH_DOC_ID, variables,
                "SearchCometResultsPaginatedResultsQuery"
            )
            self.session.headers["Referer"] = f"https://www.facebook.com/search/posts?q={keyword}"

            if not data or "data" not in data or not data["data"]:
                break

            serp = data["data"].get("serpResponse", {})
            results = serp.get("results", {})
            edges = results.get("edges", [])

            if not edges:
                break

            for edge in edges:
                post = self._parse_search_result(edge)
                if post:
                    all_posts.append(post)

            log.info(f"  Page {page}: {len(edges)} posts (total: {len(all_posts)})")

            # Get next cursor
            page_info = results.get("page_info", {}) or {}
            cursor = page_info.get("end_cursor") or page_info.get("has_next_page") and page_info.get("end_cursor")
            if not cursor:
                # Try to extract cursor from synced data
                synced = serp.get("synced_result_sets_config", {})
                if synced:
                    cursor = json.dumps(synced.get("cursor", "")) if synced.get("cursor") else None
                if not cursor:
                    break
            time.sleep(1)

        return all_posts[:max_posts]

    def _parse_search_result(self, edge):
        try:
            vm = edge.get("rendering_strategy", {}).get("view_model", {})
            story = vm.get("click_model", {}).get("story", {})
            feedback = story.get("feedback", {}) or {}
            owner = feedback.get("owning_profile", {}) or {}

            # Get message from comet_sections
            comet = story.get("comet_sections", {}) or {}
            content = comet.get("content", {}) or {}
            story_msg = content.get("story", {}) or {}
            message = story_msg.get("message", {})
            msg_text = message.get("text", "") if message else ""

            # Decode feedback_id to get post_id if missing
            post_id = str(story.get("post_id", ""))
            if not post_id and feedback.get("id", ""):
                try:
                    decoded = base64.b64decode(feedback["id"]).decode()
                    # format: "feedback:{post_id}"
                    if ":" in decoded:
                        post_id = decoded.split(":")[-1]
                except:
                    pass

            # Build URL from author_id and post_id
            author_id = str(owner.get("id", ""))
            if post_id and author_id:
                url = f"https://www.facebook.com/{author_id}/posts/{post_id}"
            elif post_id:
                url = f"https://www.facebook.com/{post_id}"
            else:
                url = story.get("url", "")

            return {
                "post_id": post_id,
                "author": owner.get("name", ""),
                "author_id": author_id,
                "author_url": f"https://www.facebook.com/{author_id}" if author_id else "",
                "url": url,
                "feedback_id": feedback.get("id", ""),
                "message": msg_text,
                "timestamp": story.get("creation_time", None),
                "comments": [],
            }
        except:
            return None

    # ─── Comments ──────────────────────────────────────────────

    def fetch_comments(self, post_id, max_comments=100, sort_mode="top"):
        feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()
        view_option = "RECENT_ACTIVITY" if sort_mode == "recent" else "RANKED_THREADED"

        all_comments = []
        cursor = None
        page = 0

        while len(all_comments) < max_comments:
            page += 1
            variables = {
                "commentsAfterCount": -1,
                "commentsAfterCursor": cursor,
                "commentsBeforeCount": None,
                "commentsBeforeCursor": None,
                "commentsIntentToken": None,
                "feedLocation": "POST_PERMALINK_DIALOG",
                "focusCommentID": None,
                "scale": 2,
                "useDefaultActor": False,
                "id": feedback_id,
                "viewOption": view_option,
                **self.COMMENTS_RELAY,
            }

            data = self._graphql(
                self.COMMENTS_DOC_ID, variables,
                "CommentsListComponentsPaginationQuery"
            )

            if not data or "data" not in data or not data["data"]:
                break

            node = data["data"].get("node", {})
            if not node:
                break

            comments_block = node.get("comment_rendering_instance_for_feed_location", {})
            comments = comments_block.get("comments", {}) or {}
            edges = comments.get("edges", [])
            page_info = comments.get("page_info", {}) or {}

            if not edges:
                break

            for edge in edges:
                comment = self._parse_comment(edge.get("node", {}))
                if comment:
                    all_comments.append(comment)

            log.info(f"  Page {page}: {len(edges)} comments (total: {len(all_comments)})")

            cursor = page_info.get("end_cursor")
            if not cursor:
                break
            time.sleep(0.5)

        all_comments = all_comments[:max_comments]

        # Fetch replies
        for i, comment in enumerate(all_comments):
            fb_id = comment.get("feedback_id", "")
            exp_token = comment.get("expansion_token", "")
            if fb_id and exp_token:
                replies = self.fetch_replies(fb_id, exp_token, max_replies=50)
                comment["replies"] = replies
                if replies:
                    log.info(f"  Comment {i+1}: {len(replies)} replies")
            elif comment.get("replies"):
                log.info(f"  Comment {i+1}: {len(comment['replies'])} inline replies")

        return all_comments

    def fetch_replies(self, feedback_id, initial_expansion_token=None, max_replies=50):
        all_replies = []
        expansion_token = initial_expansion_token

        while len(all_replies) < max_replies:
            variables = {
                "clientKey": None,
                "expansionToken": expansion_token,
                "feedLocation": "POST_PERMALINK_DIALOG",
                "focusCommentID": None,
                "scale": 2,
                "useDefaultActor": False,
                "id": feedback_id,
                **self.COMMENTS_RELAY,
            }

            data = self._graphql(
                self.REPLIES_DOC_ID, variables,
                "Depth1CommentsListPaginationQuery"
            )

            if not data or "data" not in data or not data["data"]:
                break

            node = data["data"].get("node", {})
            if not node:
                break

            replies_block = node.get("replies_connection") or {}
            edges = replies_block.get("edges", [])
            page_info = replies_block.get("page_info", {}) or {}

            if not edges:
                break

            for edge in edges:
                reply = self._parse_comment(edge.get("node", {}))
                if reply:
                    all_replies.append(reply)

            expansion_token = page_info.get("end_cursor")
            if not expansion_token:
                break
            time.sleep(0.3)

        return all_replies[:max_replies]

    def _parse_comment(self, node):
        if not node:
            return None
        author = node.get("author", {}) or {}
        body = node.get("body", {}) or {}
        feedback = node.get("feedback", {}) or {}
        feedback_id = feedback.get("id", "")
        exp_info = feedback.get("expansion_info", {}) or {}
        exp_token = exp_info.get("expansion_token", "")

        replies_conn = feedback.get("replies_connection", {}) or {}
        inline_replies = []
        for redge in replies_conn.get("edges", []):
            reply = self._parse_comment(redge.get("node", {}))
            if reply:
                inline_replies.append(reply)

        return {
            "name": author.get("name", ""),
            "text": body.get("text", ""),
            "likes_count": feedback.get("reactors", {}).get("count_reduced", 0),
            "timestamp": node.get("created_time", ""),
            "comment_id": node.get("id", ""),
            "feedback_id": feedback_id,
            "expansion_token": exp_token,
            "replies": inline_replies,
        }


# ─── Pipeline ──────────────────────────────────────────────────

def run_pipeline(keyword, max_posts, max_comments, sort_mode="top", output_path=None):
    from config import FB_COOKIES_PATH, OUTPUT_DIR

    start = time.time()
    log.info("=" * 60)
    log.info("GraphQL Full Pipeline started (100% GraphQL, $0)")
    log.info(f"  Keyword:      {keyword}")
    log.info(f"  Max posts:    {max_posts}")
    log.info(f"  Max comments: {max_comments}")
    log.info(f"  Sort:         {sort_mode}")
    log.info("=" * 60)

    client = FacebookGraphQLClient(FB_COOKIES_PATH)
    client.authenticate()

    # Step 1: Search
    log.info(f"\n[Step 1] GraphQL search posts...")
    posts = client.search_posts(keyword, max_posts)
    log.info(f"  Found {len(posts)} posts")
    for i, p in enumerate(posts):
        log.info(f"  Post {i+1}: {p['author']} | post_id={p['post_id']}")

    # Step 2: Comments + Replies
    log.info(f"\n[Step 2] GraphQL fetch comments + replies...")
    total_comments = 0
    total_replies = 0

    for i, post in enumerate(posts):
        if not post.get("post_id"):
            continue
        t0 = time.time()
        comments = client.fetch_comments(
            post["post_id"], max_comments=max_comments, sort_mode=sort_mode
        )
        elapsed = time.time() - t0
        post["comments"] = comments
        pc = len(comments)
        pr = sum(len(c.get("replies", [])) for c in comments)
        total_comments += pc
        total_replies += pr
        log.info(f"  Post {i+1}: {pc} comments + {pr} replies ({elapsed:.1f}s)")
        time.sleep(1)

    log.info(f"\nTotal: {total_comments} comments + {total_replies} replies")

    elapsed = time.time() - start
    result = {
        "keyword": keyword,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "total_posts": len(posts),
        "total_comments": total_comments,
        "total_replies": total_replies,
        "sort_mode": sort_mode,
        "posts": posts,
    }

    if not output_path:
        safe_kw = re.sub(r"[^\w]+", "_", keyword)
        output_path = str(OUTPUT_DIR / f"{safe_kw}_{int(time.time())}.json")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info("\n" + "=" * 60)
    log.info("Pipeline complete!")
    log.info(f"  Total posts:    {result['total_posts']}")
    log.info(f"  Total comments: {result['total_comments']}")
    log.info(f"  Total replies:  {result['total_replies']}")
    log.info(f"  Elapsed:        {elapsed:.1f}s")
    log.info(f"  Output:         {output_file}")
    log.info("=" * 60)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Facebook GraphQL Full Scraper — 100% GraphQL, $0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--max-posts", type=int, default=5)
    parser.add_argument("--max-comments", type=int, default=100)
    parser.add_argument("--sort", choices=["top", "recent"], default="top")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    result = run_pipeline(
        keyword=args.keyword,
        max_posts=args.max_posts,
        max_comments=args.max_comments,
        sort_mode=args.sort,
        output_path=args.output,
    )
    print(f"\nDone! Posts: {result.get('total_posts', 0)} | "
          f"Comments: {result.get('total_comments', 0)} | "
          f"Replies: {result.get('total_replies', 0)}")


if __name__ == "__main__":
    main()
