"""Extract exact engagement data paths."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'E:\Workspace\stackway\crawl posts group by graphql\Scripts\_debug_response.json'
with open(path, 'r', encoding='utf-8') as f:
    raw = f.read()

results = []
for line in raw.split('\n'):
    line = line.strip()
    if not line:
        continue
    try:
        results.append(json.loads(line))
    except:
        pass

# Find Story #2 (has reactions)
obj = results[2]
node = obj['data']['node']
cs = node['comet_sections']
fb_sec = cs['feedback']
ufi = fb_sec['story']['story_ufi_container']['story']
ctx = ufi['feedback_context']['feedback_target_with_context']
renderer = ctx['comet_ufi_summary_and_actions_renderer']
feedback = renderer['feedback']

print("=== FEEDBACK DATA (the real one) ===")
print(f"Keys: {sorted(feedback.keys())}")
print()

# Reaction count
rc = feedback.get('reaction_count', {})
print(f"reaction_count: {rc}")
print(f"i18n_reaction_count: {feedback.get('i18n_reaction_count')}")

# Top reactions
tr = feedback.get('top_reactions', {})
print(f"top_reactions count: {tr.get('count', 0)}")
edges = tr.get('edges', [])
for e in edges:
    rn = e.get('node', {})
    print(f"  reaction: {rn.get('reaction_type','?')} x{e.get('reaction_count','?')}")

# Comment count
print(f"\ncomment_count: {feedback.get('comment_count', '?')}")
print(f"total_comment_count: {feedback.get('total_comment_count', '?')}")

# Comment rendering
cri = feedback.get('comment_rendering_instance', {})
if cri:
    comments = cri.get('comments', {})
    if comments:
        print(f"comments.total_count: {comments.get('total_count', '?')}")

# Share count
print(f"\nshare_count: {feedback.get('share_count', '?')}")
print(f"reshares: {feedback.get('reshares', '?')}")

# Check for share_count_reduced
for key in sorted(feedback.keys()):
    val = feedback[key]
    if 'share' in key.lower() or 'reshare' in key.lower():
        print(f"  {key}: {val}")
    if 'comment' in key.lower():
        print(f"  {key}: {json.dumps(val, ensure_ascii=False)[:200]}")

print("\n=== ALL KEYS WITH VALUES ===")
for key in sorted(feedback.keys()):
    val = feedback[key]
    if isinstance(val, (int, str, bool, float)) or val is None:
        print(f"  {key}: {val}")
    elif isinstance(val, dict):
        print(f"  {key}: dict({len(val)} keys) = {json.dumps(val, ensure_ascii=False)[:150]}")
    elif isinstance(val, list):
        print(f"  {key}: list({len(val)} items)")
