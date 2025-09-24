#!/usr/bin/env python3
# scripts/generate_parent_view.py
import yaml
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROADMAP_FILE = BASE_DIR / "roadmap.yaml"
OUTPUT_FILE = BASE_DIR / "docs" / "Parent_View.md"

def load_roadmap(path=ROADMAP_FILE):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def generate_markdown(data):
    out = []
    out.append(f"# Parent View (Auto-generated)\n")
    out.append(f"Generated: {date.today().isoformat()}\n")

    for stage in data.get("stages", []):
        out.append(f"## {stage['name']} (status: {stage['status']})\n")
        out.append("| Task ID | Title | Status | Target Files | Est. Hours |")
        out.append("|---------|-------|--------|--------------|------------|")

        for task in stage.get("tasks", []):
            out.append("| {id} | {title} | {status} | {files} | {hours} |".format(
                id=task.get("id", ""),
                title=task.get("title", ""),
                status=task.get("status", ""),
                files=", ".join(task.get("target_files", [])) if "target_files" in task else "-",
                hours=task.get("est_hours", "-"),
            ))
        out.append("")

    out.append("## Goals")
    for k, v in data.get("goals", {}).items():
        out.append(f"- **{k}**: {v}")
    out.append(f"\n**Final Goal**: {data.get('final_goal', '')}\n")

    return "\n".join(out)

def main():
    data = load_roadmap()
    md = generate_markdown(data)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(md)

if __name__ == "__main__":
    main()
