import requests, os, glob, json, time

base = "http://localhost:9000"
skills_dir = r"C:\Users\user\skills"
added = 0
errors = []

for path in glob.glob(os.path.join(skills_dir, "**", "SKILL.md"), recursive=True):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        name = os.path.basename(os.path.dirname(path))
        payload = {
            "name": f"Skill: {name}",
            "content": text[:12000],
            "doc_type": "skill",
            "tags": ["skill", "claude-business" if "claude-business" in path else "ecc" if "ecc" in path else "core"]
        }
        r = requests.post(f"{base}/knowledge-base/add", json=payload, timeout=30)
        if r.status_code == 200:
            added += 1
        else:
            errors.append(f"{path}: {r.status_code} {r.text[:120]}")
    except Exception as e:
        errors.append(f"{path}: {e}")

print(f"Indexed {added} skill files")
if errors:
    print(f"Errors ({len(errors)}):")
    for e in errors[:10]:
        print(" -", e)
