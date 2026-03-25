---
description: Run the FB Group Posts Crawler locally for development
---

# Run Crawler Dev Server

// turbo-all

## Steps

1. Install Python dependencies (if not already)
```bash
pip install selenium requests
```

2. Start the ASP.NET dev server
```bash
cd "E:\Workspace\stackway\crawl posts group by graphql"
dotnet run
```

3. Server runs at http://localhost:5230

4. To test the crawler:
   - Open http://localhost:5230 in browser
   - Enter Facebook group URL
   - (Optional) Set date range
   - Set max posts
   - Click "Bắt Đầu Cào"

## Notes

- First run requires Chrome login to Facebook (manual, one-time)
- Chrome profile saved in `Scripts/chrome_profile/` (gitignored)
- Cookies cached in `Scripts/_cookies.json` (gitignored)
- To re-login: check "Xóa cookies" checkbox in UI
