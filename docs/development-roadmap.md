# Development Roadmap

## Phase 1: Core Crawler ✅ Complete

- [x] Selenium Chrome login with real profile
- [x] Cookie + fb_dtsg extraction
- [x] Auto-capture doc_id + variables_template via CDP
- [x] GraphQL API requests with proper headers
- [x] Cursor-based pagination
- [x] Post content extraction (message text)
- [x] Author extraction (name + ID)
- [x] Timestamp extraction from `comet_sections.timestamp`
- [x] Engagement extraction (reactions, comments, shares)
- [x] Date filtering with local timezone
- [x] Post deduplication via seen_ids

## Phase 2: Web UI ✅ Complete

- [x] ASP.NET Core 10 MVC scaffold
- [x] Dark theme UI with glassmorphism
- [x] Input form: group URL, date range, max posts
- [x] Table view with columns: author, content, time, engagement, link
- [x] JSON view with raw data
- [x] JSON export button
- [x] Real-time log streaming from Python

## Phase 3: Stability & Polish 🔄 In Progress

- [ ] Handle FB response structure changes gracefully
- [ ] Retry logic for failed API requests
- [ ] Better error messages in UI
- [ ] Encoding fixes for Vietnamese text in logs
- [ ] Clean up debug files (analyze_fb.py, _debug*)

## Phase 4: Future Enhancements 📋 Planned

- [ ] Multi-group crawling (queue system)
- [ ] Comment crawling integration
- [ ] Export to CSV/Excel
- [ ] Scheduled/automated crawling
- [ ] Dashboard with crawl history
- [ ] Proxy support for anti-detection
