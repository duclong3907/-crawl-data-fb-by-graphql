# Codebase Summary

## Project

**FB Group Posts Crawler (GraphQL)** — Automated Facebook group post crawler using reverse-engineered GraphQL API.

## Tech Stack

- **ASP.NET Core 10 MVC** — Web UI + API orchestrator
- **Python 3.10+** — Selenium crawler + HTTP GraphQL client
- **Chrome CDP** — Network interception for auto-capturing API params

## Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `Scripts/crawl_group_posts.py` | ~1400 | Main crawler: login, token extraction, GraphQL pagination, post parsing |
| `Services/PythonCrawlerService.cs` | ~100 | Python subprocess management |
| `Controllers/HomeController.cs` | ~80 | HTTP endpoint, JSON parsing |
| `Views/Home/Index.cshtml` | ~200 | Dark theme UI with Table/JSON views |
| `Models/CrawlRequestModel.cs` | ~20 | Input model: groupUrl, dates, maxPosts |
| `Models/CrawlResultModel.cs` | ~30 | Output model: posts array |

## Core Algorithms

### 1. Auto-Capture (`doc_id` + `variables_template`)
- CDP network interception captures GraphQL requests from live browser
- Extracts `doc_id` (query identifier) and 37-key `variables_template`
- Fallback: manual config in `graphql_config.json`

### 2. Pagination
- Cursor-based: `after` parameter in GraphQL variables
- Extract cursor from `page_info.end_cursor` or last edge's `cursor`
- Stop when: empty edges OR no cursor OR max_posts reached

### 3. Post Parsing (`parse_post_edge`)
- Handles two FB response formats: standard edges + streamed Stories
- Deep path extraction for engagement data (7 levels nested)
- `_safe_get()` helper for clean path navigation

### 4. Deduplication
- `seen_ids` set tracks post IDs across pages
- Each page returns ~3 edges, ~2 are duplicates from previous page

### 5. Date Filtering
- Converts user dates to Unix timestamps using **local timezone** (not UTC)
- Skip posts outside range (both before and after)

## Known Limitations

1. **Engagement data** depends on FB's response structure — may be 0 if FB changes lazy-loading behavior
2. **doc_id changes** when FB deploys new frontend code — auto-capture handles this
3. **Rate limiting** — random 1.5-4s delays, but aggressive crawling may trigger CAPTCHAs
4. **Single session** — one Chrome instance, one crawl at a time
