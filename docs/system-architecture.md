# System Architecture

## Overview

FB Group Posts Crawler — reverse-engineers Facebook's internal GraphQL API to crawl group posts with metadata. ASP.NET Core 10 MVC orchestrator + Python Selenium/CDP crawler.

## Architecture Diagram

```
┌──────────────────────────────────────────────────┐
│                Browser (User)                     │
│          http://localhost:5230                     │
└──────────────┬───────────────────────────────────┘
               │ POST /Home/Crawl
               ▼
┌──────────────────────────────────────────────────┐
│           ASP.NET Core 10 MVC                     │
│  ┌────────────────┐  ┌─────────────────────────┐ │
│  │HomeController   │→ │PythonCrawlerService     │ │
│  │  - Crawl()     │  │  - StartCrawlAsync()    │ │
│  │  - parse JSON  │  │  - subprocess Python    │ │
│  └────────────────┘  └──────────┬──────────────┘ │
└─────────────────────────────────┼────────────────┘
                                  │ subprocess
                                  ▼
┌──────────────────────────────────────────────────┐
│           crawl_group_posts.py                    │
│                                                   │
│  Phase 1: Login & Token Extraction                │
│  ┌──────────────────────────────────────────────┐│
│  │ Selenium Chrome (real profile)               ││
│  │  → Navigate to FB group                       ││
│  │  → Extract cookies, fb_dtsg via CDP          ││
│  │  → Auto-capture doc_id + variables_template  ││
│  └──────────────────────────────────────────────┘│
│                                                   │
│  Phase 2: GraphQL Crawling                        │
│  ┌──────────────────────────────────────────────┐│
│  │ HTTP POST → facebook.com/api/graphql/        ││
│  │  → Paginate via cursor                        ││
│  │  → Parse streamed JSON response              ││
│  │  → Dedup via seen_ids set                     ││
│  │  → Filter by date range (local TZ)           ││
│  │  → Extract: author, content, timestamp,      ││
│  │    reactions, comments, shares                ││
│  └──────────────────────────────────────────────┘│
│                                                   │
│  Output: JSON to stdout → C# parse               │
└──────────────────────────────────────────────────┘
```

## Component Details

### ASP.NET Core 10 MVC (Orchestrator)

| File | Purpose |
|------|---------|
| `Controllers/HomeController.cs` | HTTP endpoint, triggers crawl, parses JSON output |
| `Services/PythonCrawlerService.cs` | Manages Python subprocess lifecycle |
| `Models/CrawlRequestModel.cs` | Input: groupUrl, dateFrom, dateTo, maxPosts, clearCookies |
| `Models/CrawlResultModel.cs` | Output: posts array with metadata |
| `Views/Home/Index.cshtml` | Dark theme UI with Table/JSON view |

### Python Crawler (`Scripts/crawl_group_posts.py`)

| Module | Lines | Purpose |
|--------|-------|---------|
| Login & tokens | 1-300 | Selenium Chrome, CDP network interception |
| GraphQL capture | 300-460 | Auto-capture doc_id + variables template |
| Post parsing | 460-620 | `parse_post_edge()`, `_safe_get()` |
| Response extraction | 620-810 | Multi-format: streaming + standard edges |
| Pagination loop | 810-960 | Cursor-based, dedup, date filter |
| CLI entry | 960+ | argparse, JSON output |

### Data Flow

```
Facebook GraphQL API
    │
    │  POST /api/graphql/ (doc_id, variables, fb_dtsg)
    │
    ▼
Response (multi-line JSON, streamed)
    │
    ├─ Line 0: {data.node.group_feed.edges[]} — standard format
    ├─ Line 1+: {label, data.node(Story)} — streamed format
    │
    ▼
extract_posts_from_response()
    │
    ├─ Format 1: edges[].node → parse_post_edge()
    ├─ Format 2: streamed Story → parse_post_edge()
    │
    ▼
parse_post_edge(node)
    │
    ├─ post_id: node.post_id
    ├─ author: node.actors[0].name/id
    ├─ content: comet_sections.content.story.message.text
    ├─ timestamp: comet_sections.timestamp.story.creation_time
    ├─ reactions: feedback→story_ufi_container→...→reaction_count.count
    ├─ comments: ...→comment_rendering_instance.comments.total_count
    ├─ shares: ...→share_count.count
    └─ permalink: node.permalink_url
```

## Anti-Detection Strategy

| Technique | Implementation |
|-----------|---------------|
| Real Chrome | Selenium with user profile, GUI visible |
| WebDriver mask | `navigator.webdriver = undefined` via CDP |
| Browser headers | Exact `sec-fetch-*`, real User-Agent |
| Random delays | 1.5-4s between API requests |
| Cookie auth | Session cookies, not API tokens |
| Request mimicry | Exact same form-data format as browser |

## Key Technical Decisions

1. **Auto-capture doc_id**: CDP network interception captures `doc_id` and `variables_template` from live browser requests — eliminates manual F12 setup
2. **Streaming response**: FB returns multi-line JSON (not standard JSON array) — parser handles both formats
3. **Deep feedback path**: Engagement data (reactions/comments/shares) is nested 7 levels deep in `story_ufi_container` — uses `_safe_get()` helper
4. **Local timezone**: Date filters use machine's local timezone, not UTC
5. **Deduplication**: `seen_ids` set prevents counting same post across overlapping pages
