---
description: Update doc_id when Facebook changes their GraphQL query IDs
---

# Update GraphQL doc_id

## When to use
- Crawler returns HTTP 400 errors
- Response contains "This content isn't available"
- Auto-capture fails to find new doc_id

## Steps

1. Open Chrome with the crawler's profile:
```bash
cd "E:\Workspace\stackway\crawl posts group by graphql\Scripts"
chrome --user-data-dir=chrome_profile
```

2. Navigate to a Facebook group page

3. Open DevTools (F12) → Network tab

4. Filter by: `graphql`

5. Scroll down in the group feed to trigger pagination requests

6. Look for request with payload containing `GroupsCometFeedRegularStoriesPaginationQuery`

7. Copy the `doc_id` value from the request Payload (Form Data)

8. Update `Scripts/graphql_config.json`:
```json
{
  "doc_id": "YOUR_NEW_DOC_ID_HERE"
}
```

9. Restart the crawler and test

## Auto-Capture (Preferred)

The crawler auto-captures `doc_id` via CDP network interception.
If auto-capture is working, you don't need to do this manually.

To verify auto-capture:
- Check logs for: `Captured GraphQL request: doc_id=XXXX`
- If no capture: FB may have changed the request pattern
- Update the CDP interception regex in `crawl_group_posts.py`
