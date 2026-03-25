---
description: Debug FB GraphQL crawler response parsing issues
---

# Debug Crawler Response

## When to use
- Posts showing 0 reactions/comments/shares
- Empty results when posts exist
- Author/content not extracted
- Date filter not matching expected results

## Steps

1. Run a crawl to generate debug response file
   - The crawler saves full response to `Scripts/_debug_response.json`
   - Page-specific debug: `Scripts/_debug_pageN.json`

2. Analyze the response structure
```bash
cd "E:\Workspace\stackway\crawl posts group by graphql"
python Scripts/analyze_fb.py
```

3. Key paths in FB GraphQL response:

| Data | Path |
|------|------|
| Post ID | `node.post_id` |
| Author | `node.actors[0].name` |
| Content | `comet_sections.content.story.message.text` |
| Timestamp | `comet_sections.timestamp.story.creation_time` |
| Reactions | `...story_ufi_container...feedback.reaction_count.count` |
| Comments | `...feedback.comment_rendering_instance.comments.total_count` |
| Shares | `...feedback.share_count.count` |

4. If FB changed their response structure:
   - Open Chrome DevTools → Network → filter `graphql`
   - Scroll in the FB group to trigger requests
   - Find `GroupsCometFeedRegularStoriesPaginationQuery`
   - Inspect Response to find new field paths
   - Update `parse_post_edge()` in `crawl_group_posts.py`

5. If `doc_id` stopped working:
   - Auto-capture should handle this
   - If not: manually copy new `doc_id` from DevTools request payload
   - Save to `Scripts/graphql_config.json`

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| 0 posts found | Timezone mismatch | Check `ts_from`/`ts_to` conversion uses local time |
| All engagement = 0 | Path changed | Analyze `_debug_response.json`, update extraction path |
| Login loop | Cookies expired | Check "Xóa cookies" and re-login |
| HTTP 400 | doc_id expired | Delete `graphql_config.json`, let auto-capture refresh |
