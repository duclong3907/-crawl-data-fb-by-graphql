---
name: fb-graphql-crawler
description: Facebook Group Posts GraphQL Crawler — reverse-engineer FB internal API to extract posts with metadata. Use for crawling group posts, debugging response parsing, updating doc_id, or extending data extraction.
---

# FB GraphQL Crawler Skill

## Overview

Crawl Facebook group posts via reverse-engineered GraphQL API. The system uses:
- **Selenium Chrome** with real user profile for authentication
- **CDP (Chrome DevTools Protocol)** for network interception
- **HTTP requests** to FB's internal `/api/graphql/` endpoint

## Architecture

```
ASP.NET Core MVC (http://localhost:5230)
  └→ PythonCrawlerService (subprocess)
       └→ crawl_group_posts.py
            ├── Phase 1: Selenium login → extract cookies + fb_dtsg
            └── Phase 2: HTTP GraphQL → paginate → parse → output JSON
```

## Key Files

| File | Purpose |
|------|---------|
| `Scripts/crawl_group_posts.py` | Main crawler (~1400 lines) |
| `Services/PythonCrawlerService.cs` | Python subprocess manager |
| `Controllers/HomeController.cs` | HTTP endpoint |
| `Scripts/graphql_config.json` | Manual doc_id fallback |
| `Scripts/analyze_fb.py` | Debug analysis script |

## FB GraphQL Response Paths

### Post Data
```
node.post_id                          → Post ID
node.actors[0].name                   → Author name
node.actors[0].id                     → Author ID
comet_sections.content.story
  .message.text                       → Post content
comet_sections.timestamp.story
  .creation_time                      → Unix timestamp
node.permalink_url                    → Post link
```

### Engagement Data (7 levels deep)
```
comet_sections.feedback.story
  .story_ufi_container.story
  .feedback_context
  .feedback_target_with_context
  .comet_ufi_summary_and_actions_renderer
  .feedback
    .reaction_count.count             → Reactions
    .comment_rendering_instance
      .comments.total_count           → Comments
    .share_count.count                → Shares
```

## Common Tasks

### Fix empty results
1. Check date filter timezone — must use **local time**, not UTC
2. Verify `ts_from` / `ts_to` in logs match expected values
3. FB doesn't guarantee chronological order → don't stop early

### Fix 0 engagement
1. Run `analyze_fb.py` to inspect `_debug_response.json`
2. Navigate to `story_ufi_container` path
3. Check if FB moved the feedback data to a new location
4. Update `parse_post_edge()` and `_safe_get()` calls

### Update doc_id
1. See workflow: `.agent/workflows/update-doc-id.md`
2. Auto-capture via CDP usually handles this
3. Manual fallback: DevTools → Network → graphql filter

### Add new extracted fields
1. Analyze response: `.agent/workflows/analyze-fb-response.md`
2. Find field path using `find_key()` recursive search
3. Add extraction to `parse_post_edge()` function
4. Update output dict at end of function
5. Update `CrawlResultModel.cs` if needed for UI display

## Anti-Detection Notes

- Always use real Chrome with real profile
- Random delays 1.5-4s between requests
- Exact browser headers (sec-fetch-*, User-Agent)
- Cookie-based auth, never API tokens
- `navigator.webdriver = undefined` via CDP

## Debugging

### Debug files (auto-generated)
- `Scripts/_debug_response.json` — Full last response
- `Scripts/_debug_pageN.json` — Per-page debug
- `Scripts/_debug_raw_response.txt` — Raw HTTP body
- `Scripts/_debug_captured_requests.json` — CDP captures

### Log analysis
- All Python logs go to stderr → captured by C#
- JSON output goes to stdout → parsed by C#
- Enable verbose: check for `log()` calls in crawler
