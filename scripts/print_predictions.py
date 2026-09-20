"""Print the latest saved predictions file in a readable format.

Usage:
    python scripts/print_predictions.py                       # latest file, auto-saves .txt
    python scripts/print_predictions.py path/to/file.json    # specific file
    python scripts/print_predictions.py --out output.txt     # custom output path
    python scripts/print_predictions.py file.json --out out.txt
"""
import json, sys
from pathlib import Path

pred_dir = Path(__file__).parent.parent / "data" / "predictions"
files = sorted(pred_dir.glob("*.json"))
if not files:
    sys.exit("No prediction files found in data/predictions/")

# Parse args
args = sys.argv[1:]
out_path = None
file_arg = None
i = 0
while i < len(args):
    if args[i] == "--out" and i + 1 < len(args):
        out_path = Path(args[i + 1])
        i += 2
    else:
        file_arg = args[i]
        i += 1

target = Path(file_arg) if file_arg else files[-1]
d = json.loads(target.read_text(encoding="utf-8"))

lines = []
lines.append(f"File    : {target.name}")
lines.append(f"Saved   : {d['saved_at']}")
submitted = d.get("submitted", 0)
updated   = d.get("updated", 0)
existing  = sum(1 for m in d["matches"].values() for p in m if p["action"] == "existing")
lines.append(f"Actions : {submitted} submitted  {updated} updated  {existing} existing")
lines.append("")
lines.append("Source key:  [polymarket]   = live Polymarket market odds")
lines.append("             [poisson(odds)]= Poisson model derived from Polymarket odds")
lines.append("             [bookmaker]   = bookmaker prop odds (The Odds API)")
lines.append("             [model]       = historical stats model (no live source)")
lines.append("             [polymarket*] = model used now — Polymarket market opens closer to kickoff")
lines.append("             [model*]      = model used — bookmaker prop will open closer to kickoff")
lines.append("")

for match, preds in d["matches"].items():
    lines.append("=" * 90)
    lines.append(f"  {match}")
    lines.append("=" * 90)
    for p in preds:
        action = p.get("action", "")
        if action == "unsubmitted":
            prob_str   = " ---"
            action_tag = "[MISSING]"
            src_display = ""
        else:
            prob_str   = f"{p['probability']:3}%"
            action_tag = f"[{action}]" if action not in ("existing",) else ""
            src = p.get("source", "")
            src_display = f"[{src}]" if src and src != "existing" else ""
        lines.append(f"  {prob_str}  {action_tag:10}  {src_display:20}  {p['question']}")
    lines.append("")

output = "\n".join(lines)

# Save to file first — full unwrapped text, UTF-8
if out_path is None:
    out_path = target.with_suffix(".txt")
out_path.write_text(output, encoding="utf-8")

# Print to console with safe encoding fallback for Windows terminals
try:
    print(output)
except UnicodeEncodeError:
    safe = output.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
        sys.stdout.encoding or "utf-8", errors="replace"
    )
    print(safe)

sys.stderr.write(f"\nSaved to: {out_path}\n")
