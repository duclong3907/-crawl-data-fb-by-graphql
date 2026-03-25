# FB Group Posts Crawler (GraphQL)

Cào bài viết nhóm Facebook qua **GraphQL API** — nhanh, chính xác, ít bị detect.

> **Dùng Chrome thật với profile đăng nhập sẵn** — login 1 lần, crawl nhiều lần.

---

## ⚡ Quick Start

```bash
# 1. Cài Python dependencies
pip install selenium requests

# 2. Chạy app
dotnet run

# Mở http://localhost:5230
```

---

## 🔧 Setup (1 lần duy nhất)

### Auto-Capture (Khuyến nghị)
Crawler **tự động bắt** `doc_id` và `variables_template` qua CDP — không cần setup thủ công.

### Manual Fallback
Nếu auto-capture fail:
1. Mở nhóm Facebook trong Chrome → F12 → Network → filter `graphql`
2. Scroll feed → tìm `GroupsCometFeedRegularStoriesPaginationQuery`
3. Copy `doc_id` → paste vào `Scripts/graphql_config.json`

---

## 🏗️ Kiến trúc

```
[Browser UI — ASP.NET MVC]
     │  POST /Home/Crawl
     ▼
[HomeController.cs]
     ▼
[PythonCrawlerService.cs] → subprocess
     ▼
[crawl_group_posts.py]
     │  Phase 1: Selenium Chrome → login → cookies + fb_dtsg
     │  Phase 2: HTTP GraphQL → paginate → parse posts
     ▼
[JSON Output] → C# parse → UI (Table/JSON)
```

### Dữ liệu cào được

| Field | Source |
|-------|--------|
| Post ID | `node.post_id` |
| Tác giả | `node.actors[0].name/id` |
| Nội dung | `comet_sections.content.story.message.text` |
| Thời gian | `comet_sections.timestamp.story.creation_time` |
| Reactions | `story_ufi_container...reaction_count.count` |
| Comments | `...comment_rendering_instance.comments.total_count` |
| Shares | `...share_count.count` |
| Link | `node.permalink_url` |

### Anti-Detection

- Chrome thật (có GUI, có profile)
- `navigator.webdriver` override
- Exact browser headers (sec-fetch-*, User-Agent thật)
- Random delay 1.5-4s giữa mỗi request
- Cookie auth (không dùng API token)

---

## 📂 Cấu trúc

```
crawl posts group by graphql/
├── .agent/
│   ├── rules/                    # Agent rules
│   ├── skills/fb-graphql-crawler/ # Crawler skill reference
│   └── workflows/                # Dev workflows
├── Controllers/
│   └── HomeController.cs
├── Models/
│   ├── CrawlRequestModel.cs
│   └── CrawlResultModel.cs
├── Services/
│   └── PythonCrawlerService.cs
├── Scripts/
│   ├── crawl_group_posts.py      # Main crawler
│   ├── analyze_fb.py             # Debug analysis
│   ├── graphql_config.json       # Manual doc_id fallback
│   ├── chrome_profile/           # Chrome profile (gitignore)
│   └── _cookies.json             # Session cookies (gitignore)
├── Views/
│   └── Home/Index.cshtml         # Dark theme UI
├── docs/                         # Project documentation
│   ├── system-architecture.md
│   ├── code-standards.md
│   ├── codebase-summary.md
│   ├── development-roadmap.md
│   └── project-changelog.md
├── plans/                        # Implementation plans & reports
├── Program.cs
└── GroupPostsCrawler.csproj
```

---

## ⚙️ Yêu cầu

| Thành phần | Version |
|---|---|
| .NET SDK | 10+ |
| Python | 3.10+ |
| Google Chrome | Latest |
| pip packages | `selenium`, `requests` |

---

## 🚀 Sử dụng

1. Truy cập `http://localhost:5230`
2. Nhập URL nhóm Facebook
3. (Tùy chọn) Chọn khoảng thời gian filter
4. Nhập số bài tối đa
5. Nhấn **Bắt Đầu Cào**
6. Xem kết quả dạng **Bảng** hoặc **JSON**, xuất file JSON

---

## 🔍 Debugging

- Debug response: `Scripts/_debug_response.json`
- Analyze structure: `python Scripts/analyze_fb.py`
- Workflow: `.agent/workflows/debug-crawler.md`
- Skill reference: `.agent/skills/fb-graphql-crawler/SKILL.md`
