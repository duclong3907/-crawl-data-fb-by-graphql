# Code Standards

## Languages & Frameworks

| Layer | Tech | Version |
|-------|------|---------|
| Backend | ASP.NET Core MVC | .NET 10 |
| Crawler | Python | 3.10+ |
| Browser Automation | Selenium + CDP | Latest |
| HTTP Client | requests (Python) | Latest |

## File Naming

- **kebab-case** for all new files
- File names should be self-documenting
- Examples: `crawl-group-posts.py`, `python-crawler-service.cs`

## Project Structure

```
crawl posts group by graphql/
├── .agent/                    # Agent config
│   ├── rules/                 # Always-on rules
│   ├── skills/                # Custom skills
│   └── workflows/             # Workflow definitions
├── Controllers/               # MVC controllers
├── Models/                    # Request/response models
├── Services/                  # Business logic services
├── Scripts/                   # Python crawler scripts
│   ├── crawl_group_posts.py   # Main crawler (~1400 lines)
│   ├── graphql_config.json    # Manual doc_id fallback
│   └── chrome_profile/        # Chrome user data (gitignored)
├── Views/                     # Razor views
├── docs/                      # Project documentation
├── plans/                     # Implementation plans & reports
└── wwwroot/                   # Static files
```

## Python Code Standards

### Error Handling
- All external calls (HTTP, Selenium) wrapped in try/except
- Graceful fallback: if auto-capture fails, use manual `graphql_config.json`
- Log errors with `log()` helper, never crash silently

### Type Safety
- Use `isinstance()` checks before `.get()` on nested dicts
- `_safe_get(data, keys)` helper for deep path navigation
- Default values for all `.get()` calls

### Logging
- `log(msg)` prints to stderr (captured by C# service)
- Prefix with context: `[Python]`, page number, etc.
- Print JSON output to stdout only (parsed by C#)

### Response Parsing
- FB returns multi-line JSON (streaming format)
- Always handle both standard edges AND streamed Story nodes
- Dedup via `seen_ids` set before adding to results

## C# Code Standards

### Controllers
- Single responsibility: one action per endpoint
- Model binding for input validation
- Return appropriate status codes

### Services
- `PythonCrawlerService` manages Python subprocess
- Capture stdout (JSON output) and stderr (logs) separately
- Handle encoding: force UTF-8 for Python process

### Models
- Separate request and result models
- Nullable annotations where appropriate

## Git Conventions

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`
- No AI references in commit messages
- Never commit: `.env`, `_cookies.json`, `chrome_profile/`, `_debug*`

## Security

- Chrome profile stored locally (gitignored)
- Cookies file gitignored
- No API keys or tokens in code
- fb_dtsg extracted at runtime only
