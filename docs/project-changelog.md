# Project Changelog

## [2026-03-26] - Engagement Data & Timezone Fix

### Added
- Deep feedback extraction: reactions, comments, shares from nested `story_ufi_container` path
- `_safe_get()` helper for clean nested dict navigation
- Debug logging for date filter timestamps
- Full response save (removed 50KB cap on debug file)

### Fixed
- **Timezone bug**: Date filter now uses local timezone instead of UTC — fixes empty results when filtering by specific dates
- **Premature stop**: Changed `ts < ts_from → return` to `continue` — FB doesn't guarantee strict chronological order
- **Author extraction**: Now correctly reads from `node.actors[0].name/id`
- **Content extraction**: Uses exact path `comet_sections.content.story.message.text`
- **Timestamp extraction**: Reads from `comet_sections.timestamp.story.creation_time`
- **Post deduplication**: Added `seen_ids` set to prevent counting same posts across pages

### Technical Details
- FB engagement data is nested 7 levels deep in `story_ufi_container`
- Full path: `feedback → story → story_ufi_container → story → feedback_context → feedback_target_with_context → comet_ufi_summary_and_actions_renderer → feedback`
- Reactions: `feedback.reaction_count.count`
- Comments: `feedback.comment_rendering_instance.comments.total_count`
- Shares: `feedback.share_count.count`

## [2026-03-25] - Initial GraphQL Crawler

### Added
- Selenium Chrome login with persistent profile
- CDP network interception for auto-capturing `doc_id` and `variables_template`
- GraphQL API pagination via cursor
- ASP.NET Core 10 MVC web UI (dark theme)
- Table and JSON view for results
- JSON export functionality
- Anti-detection: real browser, proper headers, random delays
