"""
Facebook Group Posts Crawler via GraphQL API.

Flow:
1. Open Chrome with persistent profile → login if needed
2. Navigate to group page → extract fb_dtsg token + cookies
3. Use HTTP requests to call /api/graphql/ with group feed query
4. Paginate via cursor, filter by date range
5. Output JSON to stdout

Anti-detection:
- Real Chrome profile (no headless)
- Clone exact browser headers
- Random delays between requests
- Cookie-based auth (no API tokens)
"""

import sys
import json
import os
import re
import time
import shutil
import random
import argparse
import urllib.parse
from time import sleep
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

try:
    import requests
except ImportError:
    print("Installing requests...", file=sys.stderr)
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROME_PROFILE_DIR = os.path.join(SCRIPT_DIR, "chrome_profile")
COOKIES_FILE = os.path.join(SCRIPT_DIR, "_cookies.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "_fb_dtsg.txt")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "graphql_config.json")


def log(message):
    print(message, file=sys.stderr, flush=True)


def load_config():
    """Load GraphQL config (doc_id, etc.) from file."""
    default_config = {
        "doc_id": "",
        "user_agent": "",
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            saved = json.load(f)
            default_config.update(saved)
    return default_config


def save_config(config):
    """Save GraphQL config to file."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def init_driver():
    """Chrome with persistent profile + anti-detection."""
    opts = Options()
    opts.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--lang=vi")
    opts.add_argument("--start-maximized")
    opts.add_experimental_option(
        "excludeSwitches", ["enable-automation"]
    )
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2
    })

    driver = webdriver.Chrome(options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver',
                {get: () => undefined});
            window.chrome = {runtime: {}};
        """
    })
    return driver


def is_logged_in(driver):
    try:
        return "c_user" in str(driver.get_cookies())
    except Exception:
        return False


def wait_for_login(driver):
    """Wait for user to login manually."""
    log("Navigating to Facebook...")
    driver.get("https://www.facebook.com/")
    sleep(3)

    if is_logged_in(driver):
        log("Already logged in!")
        return True

    log("=" * 50)
    log("HAY DANG NHAP FACEBOOK TRONG CUA SO CHROME")
    log("Script se doi. Khong gioi han thoi gian.")
    log("=" * 50)

    for _ in range(120):  # 10 minutes
        sleep(5)
        try:
            if is_logged_in(driver):
                log("Login successful!")
                sleep(2)
                return True
        except Exception:
            continue
    raise ValueError("Timeout waiting for login (10 minutes)")


def extract_fb_dtsg(driver):
    """Extract fb_dtsg CSRF token from page source."""
    # Method 1: From page source regex
    page_source = driver.page_source
    patterns = [
        r'"DTSGInitialData".*?"token":"([^"]+)"',
        r'fb_dtsg.*?value="([^"]+)"',
        r'"dtsg":\{"token":"([^"]+)"',
        r'name="fb_dtsg" value="([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_source)
        if match:
            token = match.group(1)
            log(f"Found fb_dtsg via regex: {token[:20]}...")
            return token

    # Method 2: Execute JS to find it in React internals
    token = driver.execute_script("""
        try {
            // Try requireLazy
            if (typeof require !== 'undefined') {
                var dtsg = require('DTSGInitialData');
                if (dtsg && dtsg.token) return dtsg.token;
            }
        } catch(e) {}
        try {
            // Try scanning script elements
            var scripts = document.querySelectorAll('script');
            for (var i = 0; i < scripts.length; i++) {
                var text = scripts[i].textContent || '';
                var match = text.match(/"DTSGInitialData".*?"token":"([^"]+)"/);
                if (match) return match[1];
                match = text.match(/"dtsg":\\{"token":"([^"]+)"/);
                if (match) return match[1];
            }
        } catch(e) {}
        return null;
    """)
    if token:
        log(f"Found fb_dtsg via JS: {token[:20]}...")
        return token

    raise ValueError("Could not extract fb_dtsg token")


def extract_group_id_from_url(driver, group_url):
    """Navigate to group and extract numeric group ID."""
    log(f"Navigating to group: {group_url}")
    driver.get(group_url)
    sleep(4)

    # Method 1: From URL redirect (FB redirects to canonical URL)
    current_url = driver.current_url
    match = re.search(r'/groups/(\d+)', current_url)
    if match:
        return match.group(1)

    # Method 2: From page source
    page_source = driver.page_source
    patterns = [
        r'"groupID":"(\d+)"',
        r'"group_id":"(\d+)"',
        r'entity_id":"(\d+)"',
        r'/groups/(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_source)
        if match:
            return match.group(1)

    # Method 3: From meta tags
    group_id = driver.execute_script("""
        var metas = document.querySelectorAll('meta');
        for (var i = 0; i < metas.length; i++) {
            var content = metas[i].getAttribute('content') || '';
            var match = content.match(/fb:\\/\\/group\\/(\\d+)/);
            if (match) return match[1];
        }
        // Try al:android:url
        var al = document.querySelector(
            'meta[property="al:android:url"]');
        if (al) {
            var m = al.content.match(/(\\d+)/);
            if (m && m[1].length > 5) return m[1];
        }
        return null;
    """)
    if group_id:
        return group_id

    raise ValueError(f"Could not extract group ID from: {group_url}")


def extract_user_agent(driver):
    """Get real User-Agent from the browser."""
    return driver.execute_script("return navigator.userAgent;")


def build_session(cookies, user_agent):
    """Build requests.Session with Facebook cookies and headers."""
    session = requests.Session()

    # Set cookies
    for c in cookies:
        session.cookies.set(
            c['name'], c['value'],
            domain=c.get('domain', '.facebook.com'),
            path=c.get('path', '/')
        )

    # Clone browser headers exactly
    session.headers.update({
        'User-Agent': user_agent,
        'Accept': '*/*',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://www.facebook.com',
        'Referer': 'https://www.facebook.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'X-FB-Friendly-Name': 'GroupsCometFeedRegularStoriesPaginationQuery',
    })

    return session


def graphql_request(session, fb_dtsg, doc_id, variables):
    """Make a single GraphQL request to Facebook."""
    url = "https://www.facebook.com/api/graphql/"

    data = {
        'fb_dtsg': fb_dtsg,
        'fb_api_caller_class': 'RelayModern',
        'fb_api_req_friendly_name':
            'GroupsCometFeedRegularStoriesPaginationQuery',
        'variables': json.dumps(variables),
        'doc_id': doc_id,
    }

    # Random delay to mimic human behavior
    delay = random.uniform(1.5, 4.0)
    log(f"  Waiting {delay:.1f}s before request...")
    sleep(delay)

    response = session.post(url, data=data, timeout=30)

    log(f"  Response: HTTP {response.status_code}, "
        f"length={len(response.text)}, "
        f"content-type={response.headers.get('content-type', '?')}")

    if response.status_code != 200:
        # Save error response for debugging
        debug_file = os.path.join(
            SCRIPT_DIR, "_debug_error_response.txt")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(f"HTTP {response.status_code}\n")
            f.write(f"Headers: {dict(response.headers)}\n\n")
            f.write(response.text[:10000])
        log(f"  Saved error response to {debug_file}")
        log(f"  Response preview: {response.text[:300]}")
        raise ValueError(
            f"GraphQL request failed: HTTP {response.status_code}"
        )

    # Log preview for debugging
    preview = response.text[:200].replace('\n', ' ')
    log(f"  Response preview: {preview}...")

    return response.text


def parse_graphql_response(raw_text):
    """Parse Facebook's GraphQL response (may contain multiple JSON)."""
    text = raw_text.strip()

    # FB sometimes prefixes with 'for (;;);' as anti-XSSI
    if text.startswith('for (;;);'):
        text = text[len('for (;;);'):].strip()
        log("  Stripped 'for (;;);' prefix from response")

    # Save raw response to debug file
    debug_file = os.path.join(SCRIPT_DIR, "_debug_raw_response.txt")
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(text[:50000])

    # Try parsing entire text as single JSON first
    try:
        data = json.loads(text)
        return [data]
    except json.JSONDecodeError:
        pass

    # FB sometimes returns multiple JSON objects separated by newlines
    lines = text.split('\n')
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Also strip for(;;); from individual lines
        if line.startswith('for (;;);'):
            line = line[len('for (;;);'):].strip()
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not results:
        log(f"  Raw response length: {len(raw_text)}")
        log(f"  First 500 chars: {raw_text[:500]}")
        raise ValueError("No valid JSON in GraphQL response")

    return results


def extract_posts_from_response(response_data):
    """Extract post list + pagination from GraphQL response."""
    posts = []
    end_cursor = None
    has_next = False

    for data in response_data:
        # Format 1: Streamed response with label/path/data
        # e.g. {"label":"GroupsCometFeed...", "path":[...],
        #        "data":{"node":{"__typename":"Story",...}}}
        if 'label' in data and 'data' in data:
            story_node = data.get('data', {}).get('node', {})
            typename = story_node.get('__typename', '')
            if typename == 'Story':
                post = parse_post_edge({'node': story_node})
                if post:
                    posts.append(post)
            continue

        # Format 2: Standard group_feed response
        # Navigate directly: data.node.group_feed
        node = data
        if 'data' in node:
            node = node['data']
        if 'node' in node:
            node = node['node']
        feed = node.get('group_feed', {})
        if not feed or not isinstance(feed, dict):
            continue

        edges = feed.get('edges', [])
        if not isinstance(edges, list):
            continue

        page_info = feed.get('page_info', {})
        if page_info:
            end_cursor = page_info.get(
                'end_cursor', end_cursor)
            has_next = page_info.get(
                'has_next_page', False)

        for edge in edges:
            # Extract cursor from EVERY edge
            # (including header edges)
            edge_cursor = edge.get('cursor', '')
            if edge_cursor:
                end_cursor = edge_cursor

            edge_node = edge.get('node', edge)
            typename = edge_node.get('__typename', '')
            # Skip non-post items (headers, etc.)
            if typename in (
                'GroupsSectionHeaderUnit',
                'GroupsCometFeedRegularStoriesUnit',
            ):
                continue
            post = parse_post_edge(edge)
            if post:
                posts.append(post)

    # For streaming format: if we got posts and cursor
    # but no explicit page_info, assume more pages exist
    if posts and end_cursor and not has_next:
        has_next = True

    log(f"  Extracted: {len(posts)} posts, "
        f"cursor={'Yes' if end_cursor else 'None'}, "
        f"has_next={has_next}")

    return posts, end_cursor, has_next


def find_feed_data(node, depth=0):
    """Recursively find the feed data containing edges."""
    if depth > 10:
        return None
    if not isinstance(node, dict):
        return None

    # Direct match: edges is required, page_info optional
    if 'edges' in node and isinstance(node['edges'], list):
        return node

    # Known paths in Facebook's GraphQL responses
    search_keys = [
        'group_feed', 'group', 'node',
        'comet_sections', 'content',
        'story', 'stories',
    ]

    # First try known keys
    for key in search_keys:
        if key in node:
            result = find_feed_data(node[key], depth + 1)
            if result:
                return result

    # Then try all keys
    for key, value in node.items():
        if isinstance(value, dict):
            result = find_feed_data(value, depth + 1)
            if result:
                return result

    return None


def _safe_get(data, keys):
    """Safely navigate nested dict by key path."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def parse_post_edge(edge):
    """Parse a single post edge from GraphQL response."""
    try:
        node = edge.get('node', edge)
        cs = node.get('comet_sections', {})
        if not cs:
            return None

        # Post ID (numeric)
        post_id = node.get('post_id', '')
        if not post_id:
            post_id = node.get('id', '')

        # Permalink URL
        post_url = node.get('permalink_url', '')
        if not post_url and post_id:
            post_url = f"https://www.facebook.com/{post_id}"

        # Author from node.actors[]
        author_name = "N/A"
        author_id = ""
        actors = node.get('actors', [])
        if actors and isinstance(actors, list):
            actor = actors[0]
            author_name = actor.get('name', 'N/A')
            author_id = actor.get('id', '')

        # Message from comet_sections.content.story.message
        content = ""
        content_sec = cs.get('content', {})
        if isinstance(content_sec, dict):
            story = content_sec.get('story', {})
            if isinstance(story, dict):
                msg = story.get('message', {})
                if isinstance(msg, dict):
                    content = msg.get('text', '')
                elif isinstance(msg, str):
                    content = msg

        # Timestamp from comet_sections.timestamp.story
        created_time = 0
        ts_sec = cs.get('timestamp', {})
        if isinstance(ts_sec, dict):
            ts_story = ts_sec.get('story', {})
            if isinstance(ts_story, dict):
                created_time = ts_story.get(
                    'creation_time', 0)
        # Fallback: context_layout
        if not created_time:
            ctx = cs.get('context_layout', {})
            if isinstance(ctx, dict):
                ctx_story = ctx.get('story', {})
                if isinstance(ctx_story, dict):
                    ctx_cs = ctx_story.get(
                        'comet_sections', {})
                    if isinstance(ctx_cs, dict):
                        md = ctx_cs.get('metadata', [])
                        if isinstance(md, list):
                            for m in md:
                                if isinstance(m, dict):
                                    t = m.get(
                                        'creation_time', 0)
                                    if t:
                                        created_time = t
                                        break

        # Engagement: navigate deep FB structure
        reactions = 0
        comments = 0
        shares = 0
        fb_sec = cs.get('feedback', {})
        # Navigate: story.story_ufi_container.story
        #   .feedback_context.feedback_target_with_context
        #   .comet_ufi_summary_and_actions_renderer.feedback
        fb_data = _safe_get(fb_sec, [
            'story', 'story_ufi_container', 'story',
            'feedback_context',
            'feedback_target_with_context',
            'comet_ufi_summary_and_actions_renderer',
            'feedback',
        ])
        if fb_data:
            rc = fb_data.get('reaction_count', {})
            if isinstance(rc, dict):
                reactions = rc.get('count', 0)
            cri = fb_data.get(
                'comment_rendering_instance', {})
            if isinstance(cri, dict):
                cm = cri.get('comments', {})
                if isinstance(cm, dict):
                    comments = cm.get('total_count', 0)
            sc = fb_data.get('share_count', {})
            if isinstance(sc, dict):
                shares = sc.get('count', 0)

        # Media from attachments
        media_urls = []
        attachments = node.get('attachments', [])
        if isinstance(attachments, list):
            for att in attachments:
                if not isinstance(att, dict):
                    continue
                media = att.get('media', {})
                if isinstance(media, dict):
                    url = media.get('url', '')
                    if url:
                        media_urls.append(url)
                    # Photo
                    img = media.get('image', {})
                    if isinstance(img, dict):
                        uri = img.get('uri', '')
                        if uri:
                            media_urls.append(uri)

        post_type = "media" if media_urls else "text"

        return {
            "post_id": str(post_id),
            "author_name": author_name,
            "author_id": str(author_id),
            "content": content,
            "created_time": created_time,
            "created_time_formatted": format_timestamp(
                created_time),
            "reaction_count": reactions,
            "comment_count": comments,
            "share_count": shares,
            "media_urls": media_urls,
            "post_url": post_url,
            "post_type": post_type,
        }
    except Exception as e:
        log(f"  Error parsing post edge: {e}")
        return None


def extract_post_content(node, depth=0):
    """Extract text content from post node."""
    if depth > 8 or not isinstance(node, dict):
        return ""

    # Direct text fields
    for key in ['text', 'message']:
        val = node.get(key)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, dict) and 'text' in val:
            return val['text']

    # comet_sections → content → story → message
    cs = node.get('comet_sections', {})
    if isinstance(cs, dict):
        content = cs.get('content', {})
        if isinstance(content, dict):
            story = content.get('story', {})
            if isinstance(story, dict):
                msg = story.get('message', {})
                if isinstance(msg, dict):
                    return msg.get('text', '')
                if isinstance(msg, str):
                    return msg

    # Try message → text pattern
    msg = node.get('message', {})
    if isinstance(msg, dict):
        return msg.get('text', '')

    # Recursive search for text
    for key in ['story', 'content', 'node', 'comet_sections']:
        if key in node and isinstance(node[key], dict):
            result = extract_post_content(node[key], depth + 1)
            if result:
                return result

    return ""


def extract_author(node, depth=0):
    """Extract author name and ID from post node."""
    if depth > 8 or not isinstance(node, dict):
        return "", ""

    # Direct actor fields
    for key in ['actor', 'author', 'user']:
        val = node.get(key)
        if isinstance(val, dict):
            name = val.get('name', '')
            uid = val.get('id', '')
            if name:
                return name, uid

    # comet_sections → context_layout → story → actors
    cs = node.get('comet_sections', {})
    if isinstance(cs, dict):
        ctx = cs.get('context_layout', {})
        if isinstance(ctx, dict):
            story = ctx.get('story', {})
            if isinstance(story, dict):
                actors = story.get('actors', [])
                if actors and isinstance(actors[0], dict):
                    return actors[0].get('name', ''), \
                        actors[0].get('id', '')

    # Recursive
    for key in ['story', 'content', 'node', 'comet_sections']:
        if key in node and isinstance(node[key], dict):
            name, uid = extract_author(node[key], depth + 1)
            if name:
                return name, uid

    return "", ""


def extract_timestamp(node, depth=0):
    """Extract creation timestamp from post node."""
    if depth > 8 or not isinstance(node, dict):
        return 0

    # Direct time fields
    for key in ['created_time', 'creation_time', 'timestamp']:
        val = node.get(key)
        if isinstance(val, (int, float)) and val > 1000000000:
            return int(val)

    # comet_sections → context_layout → story → creation_time
    cs = node.get('comet_sections', {})
    if isinstance(cs, dict):
        ctx = cs.get('context_layout', {})
        if isinstance(ctx, dict):
            story = ctx.get('story', {})
            if isinstance(story, dict):
                t = story.get('creation_time', 0)
                if isinstance(t, (int, float)) and t > 1000000000:
                    return int(t)

    # Recursive
    for key in ['story', 'content', 'node', 'comet_sections']:
        if key in node and isinstance(node[key], dict):
            result = extract_timestamp(node[key], depth + 1)
            if result:
                return result

    return 0


def extract_engagement(node, depth=0):
    """Extract reaction/comment/share counts."""
    if depth > 8 or not isinstance(node, dict):
        return 0, 0, 0

    reactions = 0
    comments = 0
    shares = 0

    # feedback → reaction_count, comment_count, share_count
    fb = node.get('feedback', node)
    if isinstance(fb, dict):
        # Reactions
        rc = fb.get('reaction_count', fb.get('reactors', {}))
        if isinstance(rc, dict):
            reactions = rc.get('count', 0)
        elif isinstance(rc, int):
            reactions = rc

        # Comments
        cc = fb.get('comment_count', fb.get('comments', {}))
        if isinstance(cc, dict):
            comments = cc.get('total_count', 0)
        elif isinstance(cc, int):
            comments = cc

        # Shares
        sc = fb.get('share_count', fb.get('reshares', {}))
        if isinstance(sc, dict):
            shares = sc.get('count', 0)
        elif isinstance(sc, int):
            shares = sc

    if reactions or comments or shares:
        return reactions, comments, shares

    # Recursive
    for key in ['story', 'feedback', 'comet_sections',
                'content', 'node']:
        if key in node and isinstance(node[key], dict):
            r, c, s = extract_engagement(node[key], depth + 1)
            if r or c or s:
                return r, c, s

    return 0, 0, 0


def extract_media(node, depth=0):
    """Extract media URLs from post."""
    if depth > 8 or not isinstance(node, dict):
        return []

    urls = []

    # Direct media fields
    for key in ['attachments', 'media', 'photo', 'video']:
        val = node.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    url = (
                        item.get('url')
                        or item.get('uri')
                        or item.get('src')
                    )
                    if url:
                        urls.append(url)
        elif isinstance(val, dict):
            url = (
                val.get('url')
                or val.get('uri')
                or val.get('src')
            )
            if url:
                urls.append(url)

    if urls:
        return urls[:5]  # Cap at 5 media items

    # Recursive for attachments
    for key in ['story', 'comet_sections', 'content', 'node']:
        if key in node and isinstance(node[key], dict):
            result = extract_media(node[key], depth + 1)
            if result:
                return result

    return []


def format_timestamp(ts):
    """Format unix timestamp to readable string."""
    if not ts:
        return ""
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return str(ts)


def crawl_group_posts(
    session, fb_dtsg, doc_id, group_id,
    max_posts=100, date_from=None, date_to=None
):
    """Crawl group posts via GraphQL pagination."""
    all_posts = []
    seen_ids = set()
    cursor = None
    page = 0

    # Parse date filters (local timezone, not UTC)
    ts_from = 0
    ts_to = int(time.time()) + 86400  # tomorrow
    if date_from:
        try:
            dt = datetime.strptime(date_from, '%Y-%m-%d')
            # Use local timezone (no tzinfo = local)
            ts_from = int(dt.timestamp())
            log(f"  Filter from: {date_from} "
                f"(ts={ts_from})")
        except ValueError:
            log(f"  Invalid date_from: {date_from}, "
                "ignoring")
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d')
            # End of day in local timezone
            ts_to = int(dt.timestamp()) + 86400
            log(f"  Filter to: {date_to} "
                f"(ts={ts_to})")
        except ValueError:
            log(f"  Invalid date_to: {date_to}, "
                "ignoring")

    template = {}
    while len(all_posts) < max_posts:
        page += 1
        log(f"  Page {page}: fetching posts "
            f"(cursor={str(cursor)[:30] if cursor else 'None'})")

        # Build variables from captured template
        if page == 1:
            config = load_config()
            template = config.get('variables_template', {})
            if template:
                log(f"  Using captured template"
                    f" ({len(template)} keys)")
            else:
                log("  ⚠ No variables template found,"
                    " using minimal variables")

        if template:
            # Clone the template and override pagination
            variables = dict(template)
            variables['id'] = group_id
            variables['count'] = 10
            variables['cursor'] = cursor
        else:
            # Fallback minimal variables
            variables = {
                "id": group_id,
                "count": 10,
                "cursor": cursor,
                "feedLocation": "GROUP",
                "feedType": "DISCUSSION",
                "feedbackSource": 0,
                "focusCommentID": None,
                "renderLocation": "group",
                "scale": 1,
                "sortingSetting": "CHRONOLOGICAL",
                "useDefaultActor": False,
            }

        try:
            raw = graphql_request(session, fb_dtsg, doc_id, variables)
            response_data = parse_graphql_response(raw)

            # Save raw response for first page (debugging)
            if page == 1:
                debug_file = os.path.join(
                    SCRIPT_DIR, "_debug_response.json")
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(raw)  # Save full response
                log(f"  Saved debug response to {debug_file}")

            posts, next_cursor, has_next = \
                extract_posts_from_response(response_data)

            if not posts:
                log(f"  No posts found on page {page}")
                # Save full response for debugging
                debug_file = os.path.join(
                    SCRIPT_DIR, f"_debug_page{page}.json")
                with open(debug_file, 'w', encoding='utf-8') as f:
                    json.dump(
                        response_data, f,
                        ensure_ascii=False, indent=2
                    )
                log(f"  Saved debug: {debug_file}")
                break

            # Filter by date + dedup
            new_count = 0
            for post in posts:
                pid = post.get('post_id', '')
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)

                ts = post.get('created_time', 0)
                if ts and ts_from and ts < ts_from:
                    continue  # Before range, skip
                if ts and ts > ts_to:
                    continue  # After range, skip

                all_posts.append(post)
                new_count += 1
                if len(all_posts) >= max_posts:
                    break

            log(f"  Page {page}: {len(posts)} raw, "
                f"{new_count} new unique "
                f"(total: {len(all_posts)})")

            if not has_next or not next_cursor:
                log("  No more pages")
                break

            cursor = next_cursor

        except Exception as e:
            log(f"  Error on page {page}: {e}")
            if page == 1:
                raise  # First page fail = critical
            break

    return all_posts


def capture_doc_id_from_network(driver, group_url):
    """Scroll group feed and intercept GraphQL requests to capture doc_id.

    Injects fetch/XHR interceptor BEFORE page scripts run via CDP,
    then reloads the group page to capture all GraphQL requests.
    """
    log("Auto-capturing doc_id from network requests...")

    # Inject interceptor BEFORE any page JS runs
    # This ensures we capture requests from initial page load too
    intercept_script = """
        window._graphqlCaptures = [];

        // Override fetch
        var origFetch = window.fetch;
        window.fetch = function() {
            var url = arguments[0];
            var opts = arguments[1] || {};
            if (typeof url === 'string'
                && url.indexOf('/api/graphql') > -1
                && opts.body) {
                try {
                    var body = opts.body;
                    if (typeof body === 'string') {
                        var params = new URLSearchParams(body);
                        var docId = params.get('doc_id');
                        var fname = params.get(
                            'fb_api_req_friendly_name');
                        if (docId && fname) {
                            window._graphqlCaptures.push({
                                doc_id: docId,
                                friendly_name: fname,
                                variables: params.get('variables') || '',
                                fb_dtsg: params.get('fb_dtsg') || ''
                            });
                        }
                    }
                } catch(e) {}
            }
            return origFetch.apply(this, arguments);
        };

        // Override XMLHttpRequest
        var origOpen = XMLHttpRequest.prototype.open;
        var origSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.open = function() {
            this._url = arguments[1];
            return origOpen.apply(this, arguments);
        };
        XMLHttpRequest.prototype.send = function(body) {
            if (this._url
                && this._url.indexOf('/api/graphql') > -1
                && body) {
                try {
                    var params = new URLSearchParams(body);
                    var docId = params.get('doc_id');
                    var fname = params.get(
                        'fb_api_req_friendly_name');
                    if (docId && fname) {
                        window._graphqlCaptures.push({
                            doc_id: docId,
                            friendly_name: fname,
                            variables: params.get('variables') || '',
                            fb_dtsg: params.get('fb_dtsg') || ''
                        });
                    }
                } catch(e) {}
            }
            return origSend.apply(this, arguments);
        };
    """

    # Register script to run on every new document (before page JS)
    result = driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": intercept_script}
    )
    script_id = result.get('identifier', '')

    # Navigate to group (or reload if already there)
    current = driver.current_url or ""
    if "groups" in current and group_url in current:
        log("  Reloading group page with interceptor active...")
        driver.refresh()
    else:
        log(f"  Navigating to group: {group_url}")
        driver.get(group_url)
    sleep(6)

    captured_doc_ids = []

    # Check captures from initial page load
    try:
        found = driver.execute_script(
            "return window._graphqlCaptures || [];"
        )
        if found:
            for cap in found:
                fname = cap.get('friendly_name', '')
                doc_id = cap.get('doc_id', '')
                log(f"    Captured: {fname} → doc_id={doc_id}")
                if 'GroupsCometFeed' in fname and doc_id:
                    captured_doc_ids.append(doc_id)
    except Exception as e:
        log(f"    Initial capture check error: {e}")

    # If not found yet, scroll to trigger pagination requests
    if not captured_doc_ids:
        log("  Scrolling group feed to trigger more requests...")
        for scroll_i in range(10):
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            sleep(2.0 + random.uniform(0.5, 2.0))

            try:
                found = driver.execute_script(
                    "return window._graphqlCaptures || [];"
                )
                if found:
                    for cap in found:
                        fname = cap.get('friendly_name', '')
                        doc_id = cap.get('doc_id', '')
                        if 'GroupsCometFeed' in fname and doc_id:
                            if doc_id not in captured_doc_ids:
                                captured_doc_ids.append(doc_id)
                                log(f"    Captured: {fname}"
                                    f" → doc_id={doc_id}")

                if captured_doc_ids:
                    log(f"  Found doc_id after"
                        f" {scroll_i + 1} scrolls!")
                    break

            except Exception as e:
                log(f"    Scroll {scroll_i + 1} error: {e}")

    # Fallback: parse from page source
    if not captured_doc_ids:
        log("  Trying page source fallback...")
        page_source = driver.page_source
        patterns = [
            r'"doc_id":"(\d{10,20})"[^}]*'
            r'"GroupsCometFeed',
            r'GroupsCometFeed[^"]*"[^}]*"doc_id":"(\d{10,20})"',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, page_source)
            if matches:
                captured_doc_ids.extend(matches)
                log(f"    Found via page source: {matches}")
                break

    # Fallback 2: scan script tags
    if not captured_doc_ids:
        log("  Scanning script tags...")
        scripts = driver.execute_script(r"""
            var result = [];
            var scripts = document.querySelectorAll('script');
            for (var i = 0; i < scripts.length; i++) {
                var text = scripts[i].textContent || '';
                if (text.indexOf('GroupsCometFeed') > -1) {
                    var matches = text.match(
                        /"doc_id"\s*:\s*"(\d{10,20})"/g
                    );
                    if (matches) {
                        for (var j = 0; j < matches.length; j++) {
                            var m = matches[j].match(/(\d{10,20})/);
                            if (m) result.push(m[1]);
                        }
                    }
                }
            }
            return result;
        """)
        if scripts:
            captured_doc_ids.extend(scripts)
            log(f"    Found via script tags: {scripts}")

    # Fallback 3: log ALL captured graphql requests for debugging
    if not captured_doc_ids:
        log("  No GroupsCometFeed found. All captured requests:")
        try:
            all_caps = driver.execute_script(
                "return window._graphqlCaptures || [];"
            )
            for cap in (all_caps or []):
                log(f"    - {cap.get('friendly_name', '?')}"
                    f" → {cap.get('doc_id', '?')}")

            # Try any request with "Group" in name as fallback
            for cap in (all_caps or []):
                fname = cap.get('friendly_name', '')
                doc_id = cap.get('doc_id', '')
                if 'Group' in fname and 'Feed' in fname and doc_id:
                    captured_doc_ids.append(doc_id)
                    log(f"    Using fallback match: {fname}"
                        f" → {doc_id}")
                    break
        except Exception as e:
            log(f"    Debug dump error: {e}")

    # Cleanup: remove the injected script
    try:
        if script_id:
            driver.execute_cdp_cmd(
                "Page.removeScriptToEvaluateOnNewDocument",
                {"identifier": script_id}
            )
    except Exception:
        pass

    if captured_doc_ids:
        doc_id = captured_doc_ids[0]
        log(f"  ✅ Captured doc_id: {doc_id}")

        # Save all captured requests and extract variables template
        try:
            all_caps = driver.execute_script(
                "return window._graphqlCaptures || [];"
            )
            debug_file = os.path.join(
                SCRIPT_DIR, "_debug_captured_requests.json")
            with open(debug_file, 'w', encoding='utf-8') as f:
                json.dump(all_caps, f, ensure_ascii=False, indent=2)
            log(f"  Saved {len(all_caps)} captured requests"
                f" to {debug_file}")

            # Extract variables template from GroupsCometFeed
            for cap in (all_caps or []):
                fname = cap.get('friendly_name', '')
                if 'GroupsCometFeed' in fname:
                    vars_str = cap.get('variables', '')
                    if vars_str:
                        try:
                            vars_obj = json.loads(vars_str)
                            # Save template to config
                            config = load_config()
                            config['variables_template'] = vars_obj
                            save_config(config)
                            log(f"  ✅ Saved variables template"
                                f" ({len(vars_obj)} keys)")
                        except json.JSONDecodeError:
                            log(f"  ⚠ Could not parse"
                                f" variables: {vars_str[:100]}")
                    break
        except Exception as e:
            log(f"  Error saving captured data: {e}")

        return doc_id

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Facebook Group Posts Crawler via GraphQL"
    )
    parser.add_argument(
        "--group-url",
        help="Facebook group URL"
    )
    parser.add_argument(
        "--group-id",
        help="Facebook group numeric ID"
    )
    parser.add_argument(
        "--max", type=int, default=100,
        help="Maximum posts to crawl"
    )
    parser.add_argument(
        "--date-from",
        help="Start date filter (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--date-to",
        help="End date filter (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--clear-cookies", action="store_true",
        help="Clear Chrome profile and re-login"
    )
    args = parser.parse_args()

    if not args.group_url and not args.group_id:
        parser.error("Either --group-url or --group-id required")

    if args.clear_cookies and os.path.exists(CHROME_PROFILE_DIR):
        shutil.rmtree(CHROME_PROFILE_DIR, ignore_errors=True)
        log("Cleared Chrome profile")

    # Load config
    config = load_config()

    # Phase 1: Login + extract tokens + auto-capture doc_id
    log("Phase 1: Login & extract tokens")
    driver = None
    group_id = args.group_id
    group_name = ""
    cookies = []
    fb_dtsg = ""

    try:
        driver = init_driver()
        wait_for_login(driver)

        # Extract group ID if needed
        group_url = args.group_url or ""
        if not group_id and group_url:
            group_id = extract_group_id_from_url(driver, group_url)
            # Try to get group name
            try:
                group_name = driver.execute_script("""
                    var h1 = document.querySelector('h1');
                    return h1 ? h1.textContent.trim() : '';
                """) or ""
            except Exception:
                pass
        elif group_id and not group_url:
            group_url = f"https://www.facebook.com/groups/{group_id}"
            driver.get(group_url)
            sleep(4)

        log(f"Group ID: {group_id}")
        if group_name:
            log(f"Group Name: {group_name}")

        # Extract fb_dtsg
        fb_dtsg = extract_fb_dtsg(driver)
        log(f"fb_dtsg: {fb_dtsg[:20]}...")

        # Auto-capture doc_id AND variables template
        need_capture = (
            not config.get('doc_id')
            or not config.get('variables_template')
        )
        if need_capture:
            if not config.get('doc_id'):
                log("doc_id not found in config,"
                    " auto-capturing...")
            else:
                log("Capturing real variables template...")
            doc_id = capture_doc_id_from_network(
                driver, group_url)
            if doc_id:
                # Reload config first to preserve
                # variables_template saved inside capture
                config = load_config()
                config['doc_id'] = doc_id
                save_config(config)
                log(f"Saved doc_id to {CONFIG_FILE}")
            else:
                log("=" * 60)
                log("KHONG THE TU DONG LAY doc_id!")
                log("Ban can tu lay thu cong:")
                log("  1. Mo DevTools (F12) > Network"
                    " > filter 'graphql'")
                log("  2. Scroll group feed")
                log("  3. Tim request GroupsCometFeed...")
                log("  4. Copy doc_id vao file:")
                log(f"     {CONFIG_FILE}")
                log("=" * 60)
                print(json.dumps({
                    "success": False,
                    "error": "Không thể tự động lấy doc_id. "
                             "Xem hướng dẫn trong console.",
                    "total": 0,
                    "group_id": group_id or "",
                    "group_name": group_name,
                    "posts": []
                }, ensure_ascii=False))
                return

        # Save token
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(fb_dtsg)

        # Extract cookies
        cookies = driver.get_cookies()
        with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f)
        log(f"Exported {len(cookies)} cookies")

        # Get User-Agent
        user_agent = extract_user_agent(driver)
        config['user_agent'] = user_agent
        save_config(config)

    finally:
        if driver:
            driver.quit()

    # Phase 2: GraphQL HTTP requests
    log("\nPhase 2: Crawling via GraphQL")
    session = build_session(cookies, config.get('user_agent', ''))

    try:
        posts = crawl_group_posts(
            session=session,
            fb_dtsg=fb_dtsg,
            doc_id=config['doc_id'],
            group_id=group_id,
            max_posts=args.max,
            date_from=args.date_from,
            date_to=args.date_to,
        )

        result = {
            "success": True,
            "total": len(posts),
            "group_id": group_id,
            "group_name": group_name,
            "posts": posts,
            "has_more": len(posts) >= args.max,
        }

        log(f"\nDone: {len(posts)} posts crawled")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        log(f"Crawl error: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({
            "success": False,
            "error": str(e),
            "total": 0,
            "group_id": group_id or "",
            "group_name": group_name or "",
            "posts": [],
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
