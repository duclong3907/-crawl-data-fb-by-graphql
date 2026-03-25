---
description: Analyze Facebook GraphQL response structure for reverse-engineering
---

# Analyze FB Response

## When to use
- Need to extract new fields from FB response
- Debugging data extraction issues
- FB changed response structure

## Steps

1. First ensure you have a debug response file:
   - Run a crawl → file saved at `Scripts/_debug_response.json`

2. Write/update analysis script at `Scripts/analyze_fb.py`:
```python
"""Analyze FB GraphQL response structure."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'Scripts/_debug_response.json'
with open(path, 'r', encoding='utf-8') as f:
    raw = f.read()

# Parse multi-line JSON (FB streams multiple objects)
results = []
for line in raw.split('\n'):
    line = line.strip()
    if not line: continue
    try: results.append(json.loads(line))
    except: pass

print(f"JSON objects: {len(results)}")

# Inspect structure of each object
for i, obj in enumerate(results[:5]):
    if 'data' in obj:
        node = obj['data'].get('node', {})
        print(f"\nObj {i}: __typename={node.get('__typename')}")
        if node.get('__typename') == 'Story':
            cs = node.get('comet_sections', {})
            print(f"  section keys: {sorted(cs.keys())}")
```

3. Run analysis:
```bash
cd "E:\Workspace\stackway\crawl posts group by graphql"
python Scripts/analyze_fb.py
```

4. Key response formats to handle:

**Format 1: Standard edges (first page)**
```
data.node.group_feed.edges[].node (Story)
```

**Format 2: Streamed objects (subsequent pages)**
```
{label: "...", data: {node: {__typename: "Story", ...}}}
```

5. After identifying new paths, update `parse_post_edge()` in `crawl_group_posts.py`

## Useful Analysis Patterns

### Dump all keys at a path
```python
import json
section = node['comet_sections']['feedback']
print(json.dumps(section, ensure_ascii=False, indent=2)[:3000])
```

### Find a field by name recursively
```python
def find_key(d, target, path=""):
    if isinstance(d, dict):
        for k, v in d.items():
            if k == target:
                print(f"Found {target} at {path}.{k}: {v}")
            find_key(v, target, f"{path}.{k}")
    elif isinstance(d, list):
        for i, v in enumerate(d):
            find_key(v, target, f"{path}[{i}]")
```
