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
│  Phase 1: Login & Token Extraction               │
│  ┌──────────────────────────────────────────────┐│
│  │ Selenium Chrome (real profile, có GUI)       ││
│  │  → Login FB (dùng profile lưu sẵn)           ││
│  │  → Extract cookies, fb_dtsg via CDP          ││
│  │  → Auto-capture doc_id + variables_template  ││
│  │  → Đóng Chrome                                ││
│  └──────────────────────────────────────────────┘│
│                                                   │
│  Phase 2: GraphQL Crawling (HTTP thuần)           │
│  ┌──────────────────────────────────────────────┐│
│  │ HTTP POST → facebook.com/api/graphql/        ││
│  │  → Sort: CHRONOLOGICAL (mới nhất trước)      ││
│  │  → 30 bài/page, delay 6-12s giữa requests    ││
│  │  → Paginate via cursor                        ││
│  │  → Parse streamed JSON response              ││
│  │  → Dedup via seen_ids set                     ││
│  │  → Filter by date range (giờ Việt Nam)       ││
│  │  → Early stop khi vượt quá khoảng thời gian ││
│  └──────────────────────────────────────────────┘│
│                                                   │
│  Output: JSON to stdout → C# parse               │
│  Hiển thị thời gian theo giờ Việt Nam (local TZ) │
└──────────────────────────────────────────────────┘
```

## Luồng hoạt động chi tiết

### Phase 1: Login & Lấy Token (Selenium Chrome)

- Mở Chrome thật với profile đã lưu sẵn (có giao diện, không phải headless)
- Truy cập facebook.com → nếu chưa login thì chờ user đăng nhập thủ công
- Truy cập trang group → trích xuất **Group ID** từ URL
- Trích xuất **fb_dtsg** (CSRF token) từ source code trang
- Tự động bắt **doc_id** và **variables_template** qua CDP (Chrome DevTools Protocol):
  - Inject interceptor theo dõi mọi request GraphQL
  - Cuộn feed để Facebook gửi request phân trang
  - Bắt request `GroupsCometFeedRegularStoriesPaginationQuery` → lưu config
- Xuất cookies → **đóng Chrome** hoàn toàn

### Phase 2: Cào dữ liệu qua GraphQL API (HTTP thuần, không cần Chrome)

- Tạo HTTP session với cookies + headers giả lập trình duyệt thật (chống phát hiện)
- Gọi `POST facebook.com/api/graphql/` với `doc_id`, `variables`, `fb_dtsg`
- Cấu hình:
  - Sắp xếp: **CHRONOLOGICAL** (bài mới nhất trả về trước)
  - Mỗi page: **30 bài**
  - Delay giữa các request: **6-12 giây** (ngẫu nhiên, mô phỏng hành vi người dùng)
- Với mỗi bài viết, trích xuất: tác giả, nội dung, thời gian đăng, reactions, comments, shares, link, media
- Lọc theo khoảng thời gian (giờ Việt Nam):
  - Trong khoảng `fromDate` → `toDate` → giữ
  - Ngoài khoảng → bỏ qua
- **Dừng cào** khi gặp 1 trong 3 điều kiện (cái nào trước thì dừng):
  1. Đủ số bài tối đa (`max_posts`)
  2. Gặp 1 page mà **tất cả bài đều cũ hơn** `fromDate` → dừng sớm (early stop)
  3. Hết feed (không còn page tiếp theo)

### Phase 3: Trả kết quả

- Python xuất JSON qua stdout → C# nhận + parse → trả về giao diện web
- Hiển thị dạng **Bảng** hoặc **JSON**, thời gian theo **giờ Việt Nam**
- Hỗ trợ **xuất file JSON**

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
| Pagination loop | 810-960 | Cursor-based, dedup, date filter, early stop |
| CLI entry | 960+ | argparse, JSON output |

### Data Flow

```
Facebook GraphQL API
    │
    │  POST /api/graphql/ (doc_id, variables, fb_dtsg)
    │  Sort: CHRONOLOGICAL, Count: 30/page
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
| Random delays | **6-12s** between API requests |
| Cookie auth | Session cookies, not API tokens |
| Request mimicry | Exact same form-data format as browser |

## Key Technical Decisions

1. **Auto-capture doc_id**: CDP network interception captures `doc_id` and `variables_template` from live browser requests — eliminates manual F12 setup
2. **CHRONOLOGICAL sorting**: Bài mới nhất trả về trước → kết hợp early stop để dừng sớm khi vượt quá khoảng thời gian, tránh duyệt toàn bộ feed
3. **Early stop**: Khi tất cả bài trong 1 page đều cũ hơn `fromDate` → dừng luôn, không cào tiếp. Giúp tiết kiệm hàng trăm requests khi chỉ cần bài gần đây
4. **Streaming response**: FB returns multi-line JSON (not standard JSON array) — parser handles both formats
5. **Deep feedback path**: Engagement data (reactions/comments/shares) is nested 7 levels deep in `story_ufi_container` — uses `_safe_get()` helper
6. **Local timezone (Việt Nam)**: Date filters và hiển thị thời gian đều dùng timezone local, hỗ trợ chọn cả ngày + giờ:phút
7. **Deduplication**: `seen_ids` set prevents counting same post across overlapping pages

## Ước tính hiệu năng

| Số bài | Pages (30 bài/page) | Delay TB (9s) | Thời gian |
|--------|---------------------|---------------|-----------|
| 100 | ~4 | 9s | ~36 giây |
| 500 | ~17 | 9s | ~2.5 phút |
| 1000 | ~34 | 9s | ~5 phút |
| 1500 | ~50 | 9s | ~7.5 phút |

> **Lưu ý**: Với early stop + CHRONOLOGICAL sorting, nếu chỉ cần bài trong ngày thì thời gian thực tế sẽ ngắn hơn nhiều.
