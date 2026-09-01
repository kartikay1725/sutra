from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / "frontend-audit-report.json"

routes = []
interactive = []
flags = []

page_files = list((ROOT / "app").rglob("page.tsx")) if (ROOT / "app").exists() else []
screen_file = ROOT / "components" / "screens.tsx"

for p in page_files:
    rel = p.relative_to(ROOT).as_posix()
    route = "/" + p.parent.relative_to(ROOT / "app").as_posix()
    route = route.replace("/page.tsx", "")
    route = route.replace("\\", "/")
    if route == "/.":
        route = "/"
    routes.append({"file": rel, "route": route})

files = list((ROOT / "components").rglob("*.tsx")) if (ROOT / "components").exists() else []
if screen_file.exists():
    files.append(screen_file)

for p in sorted(set(files)):
    text = p.read_text(encoding="utf-8", errors="ignore")
    rel = p.relative_to(ROOT).as_posix()

    for m in re.finditer(r"<button\\b[^>]*>(.*?)</button>", text, re.S):
        chunk = m.group(0)
        label = re.sub(r"<[^>]+>", " ", m.group(1)).strip()
        interactive.append({
            "file": rel,
            "kind": "button",
            "label": " ".join(label.split())[:120],
            "has_onClick": "onClick=" in chunk,
        })

    for m in re.finditer(r"<input\\b[^>]*>|<select\\b[^>]*>|<textarea\\b[^>]*>", text, re.S):
        chunk = m.group(0)
        interactive.append({
            "file": rel,
            "kind": chunk.split()[0].lstrip("<"),
            "label": "",
            "has_handler": any(x in chunk for x in ("onChange=", "onInput=", "value=")),
        })

    for token, label in [
        ("mock", "mock keyword"),
        ("hardcoded", "hardcoded keyword"),
        ("demo", "demo keyword"),
        ("coming soon", "coming soon"),
        ("not implemented", "not implemented"),
    ]:
        if token in text.lower():
            flags.append({"file": rel, "flag": label})

report = {
    "routes": sorted(routes, key=lambda x: x["route"]),
    "interactive_elements": interactive,
    "heuristic_flags": flags,
    "summary": {
        "route_count": len(routes),
        "interactive_count": len(interactive),
        "heuristic_flag_count": len(flags),
    },
}
OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report["summary"], indent=2))
print(f"Wrote {OUT}")
