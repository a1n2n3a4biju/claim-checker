"""
E4.2: compare the AI-image detector candidates (owner: M1).

Two steps:
  1) score    run every detector on every image in data/images and save the scores
              (resumable: images already scored are skipped)
  2) compare  build the comparison table, optionally only on the tuning split

Usage (from the project root, venv active):
  python evaluation/detector_comparison.py score
  python evaluation/detector_comparison.py compare
  python evaluation/detector_comparison.py compare --split tuning     # once M2's split is in the manifest

Detectors are loaded through backend/app/modules/ai_detector.py, so the scores match what the app uses.
"""
import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "data" / "images"
MANIFEST = ROOT / "data" / "manifest.csv"
RESULTS = ROOT / "evaluation" / "results"
SCORES_CSV = RESULTS / "ai_scores_all.csv"
TIMING_CSV = RESULTS / "ai_detector_timing.csv"

DETECTORS = ["ufd", "community_forensics", "bfree", "siglip"]
NAMES = {"ufd": "UniversalFakeDetect", "community_forensics": "Community Forensics",
         "bfree": "B-Free", "siglip": "SigLIP"}

# folder -> (label, what it means for the AI detectors)
#   ai      = an AI fake: the AI detectors should catch it
#   genuine = a real photo: any flag is a false positive
#   edit    = edited by hand or script: not the AI detectors' job (reported for information)
CATEGORIES = {
    "genuine": ("real", "genuine"),
    "hard_genuine": ("real", "genuine"),
    "forwarded_genuine": ("real", "genuine"),
    "ai": ("fake", "ai"),
    "ai_inpaint": ("fake", "ai"),
    "forwarded_fake": ("fake", None),          # decided per file: AI or edit
    "Scripted_edits": ("fake", "edit"),
    "careful_manual_edits": ("fake", "edit"),
}
SKIP_FOLDERS = {"masks", "box_previews"}


def role_of(folder, name):
    if folder == "forwarded_fake":
        return "ai" if "AI_" in name.upper() else "edit"
    return CATEGORIES[folder][1]


def generator_of(name):
    u = name.upper()
    for key, gen in (("AI_GPT", "ChatGPT"), ("AI_GEM", "Gemini"), ("AI_SD", "Stable Diffusion")):
        if key in u:
            return gen
    if u.startswith("IN_") or "_IN_P_" in u:
        return "SD inpainting"
    return ""


def list_images():
    folders = {d.name.lower(): d for d in IMAGES.iterdir() if d.is_dir()} if IMAGES.exists() else {}
    unknown = [d.name for d in folders.values() if d.name not in CATEGORIES and d.name not in SKIP_FOLDERS]
    if unknown:
        print(f"Note: skipping folders not in the category list: {', '.join(unknown)}")
    for folder in CATEGORIES:
        d = folders.get(folder.lower())
        if d is None:
            print(f"Warning: folder data/images/{folder} not found")
            continue
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg"):
                yield folder, f


# ------------------------------------------------------------------ step 1: score

def read_scores():
    if not SCORES_CSV.exists():
        return {}
    with open(SCORES_CSV, newline="") as fh:
        return {(r["folder"], r["filename"]): r for r in csv.DictReader(fh)}


def write_scores(rows):
    RESULTS.mkdir(parents=True, exist_ok=True)
    fields = ["folder", "filename", "label", "role", "generator"] + DETECTORS
    with open(SCORES_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for key in sorted(rows):
            w.writerow(rows[key])


def cmd_score(args):
    sys.path.insert(0, str(ROOT / "backend"))
    from app.modules import ai_detector

    images = list(list_images())
    if not images:
        sys.exit("No images found in data/images. See the dataset setup steps.")
    print(f"{len(images)} images found\n")

    rows = read_scores()
    for folder, path in images:
        key = (folder, path.name)
        rows.setdefault(key, {"folder": folder, "filename": path.name, "label": CATEGORIES[folder][0],
                              "role": role_of(folder, path.name), "generator": generator_of(path.name)})

    timing = []
    for det in args.detectors:
        todo = [(f, p) for f, p in images if not rows[(f, p.name)].get(det)]
        if not todo:
            print(f"{NAMES[det]}: all images already scored, skipping")
            continue
        print(f"{NAMES[det]}: loading ...", flush=True)
        start = time.perf_counter()
        try:
            predict = ai_detector._detector(det)
        except Exception as e:
            print(f"  could not load, skipping: {e}\n")
            continue
        load_s = time.perf_counter() - start

        start = time.perf_counter()
        for i, (folder, path) in enumerate(todo, 1):
            try:
                rows[(folder, path.name)][det] = f"{float(predict(str(path))):.4f}"
            except Exception as e:
                print(f"  failed on {folder}/{path.name}: {e}")
            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} images", flush=True)
                write_scores(rows)            # save progress so a crash loses little
        per_image = (time.perf_counter() - start) / len(todo)
        timing.append({"detector": NAMES[det], "load_seconds": f"{load_s:.1f}",
                       "seconds_per_image": f"{per_image:.2f}", "images": len(todo)})
        print(f"  done: {per_image:.2f} s per image, loaded in {load_s:.1f} s\n")

    write_scores(rows)
    if timing:
        with open(TIMING_CSV, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(timing[0]))
            w.writeheader()
            w.writerows(timing)
    print(f"Scores saved to {SCORES_CSV.relative_to(ROOT)}")


# ------------------------------------------------------------------ step 2: compare

def split_filter(args):
    """Return the set of filenames in the requested split, or None for all images."""
    if not args.split:
        return None
    if not MANIFEST.exists():
        sys.exit(f"--split needs {MANIFEST.relative_to(ROOT)}")
    with open(MANIFEST, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        cols = {c.strip().lower(): c for c in reader.fieldnames or []}
        file_col = next((cols[c] for c in ("filename", "file", "file_name", "image", "path") if c in cols), None)
        split_col = cols.get(args.split_col.lower())
        if not file_col or not split_col:
            sys.exit(f"Manifest columns are {reader.fieldnames}. Use --split-col to name the split column.")
        keep = {Path(r[file_col].strip()).name for r in reader
                if r[split_col].strip().lower() == args.split.lower()}
    if not keep:
        sys.exit(f"No manifest rows have {split_col} = '{args.split}'.")
    return keep


def auc(pos, neg):
    """Probability that a random AI fake scores higher than a random genuine photo (0.5 = guessing)."""
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def cmd_compare(args):
    if not SCORES_CSV.exists():
        sys.exit("No scores yet. Run:  python evaluation/detector_comparison.py score")
    with open(SCORES_CSV, newline="") as fh:
        rows = list(csv.DictReader(fh))

    keep = split_filter(args)
    if keep is not None:
        rows = [r for r in rows if r["filename"] in keep]
    scope = f"{args.split} split" if args.split else "all images (no split applied)"
    dets = [d for d in DETECTORS if any(r.get(d) for r in rows)]
    t = args.threshold

    def score(r, d):
        return float(r[d]) if r.get(d) else None

    groups = [
        ("AI fakes (should be caught)", None, None),
        ("Fully AI: ChatGPT", lambda r: r["folder"] == "ai" and r["generator"] == "ChatGPT", "catch"),
        ("Fully AI: Gemini", lambda r: r["folder"] == "ai" and r["generator"] == "Gemini", "catch"),
        ("Fully AI: Stable Diffusion", lambda r: r["folder"] == "ai" and r["generator"] == "Stable Diffusion", "catch"),
        ("Fully AI: other/unknown", lambda r: r["folder"] == "ai" and not r["generator"], "catch"),
        ("AI-inpainted", lambda r: r["folder"] == "ai_inpaint", "catch"),
        ("Forwarded AI fakes", lambda r: r["folder"] == "forwarded_fake" and r["role"] == "ai", "catch"),
        ("All AI fakes", lambda r: r["role"] == "ai", "catch"),
        ("Genuine photos (any flag is a false positive)", None, None),
        ("Genuine", lambda r: r["folder"] == "genuine", "fp"),
        ("Hard genuine", lambda r: r["folder"] == "hard_genuine", "fp"),
        ("Forwarded genuine", lambda r: r["folder"] == "forwarded_genuine", "fp"),
        ("All genuine", lambda r: r["role"] == "genuine", "fp"),
        ("Edited photos (not the AI detectors' job; for information)", None, None),
        ("Scripted edits", lambda r: r["folder"] == "Scripted_edits", "info"),
        ("Careful manual edits", lambda r: r["folder"] == "careful_manual_edits", "info"),
        ("Forwarded edits", lambda r: r["folder"] == "forwarded_fake" and r["role"] == "edit", "info"),
    ]

    table = []        # (group, n, {det: "k of n"})
    for title, test, kind in groups:
        if test is None:
            table.append((title, None, None))
            continue
        members = [r for r in rows if test(r)]
        if not members:
            continue
        cells = {}
        for d in dets:
            vals = [score(r, d) for r in members if score(r, d) is not None]
            flagged = sum(v >= t for v in vals)
            cells[d] = f"{flagged} of {len(vals)}"
        table.append((title, len(members), cells))

    pos = {d: [score(r, d) for r in rows if r["role"] == "ai" and score(r, d) is not None] for d in dets}
    neg = {d: [score(r, d) for r in rows if r["role"] == "genuine" and score(r, d) is not None] for d in dets}
    fwd = {d: [score(r, d) for r in rows if r["folder"] == "forwarded_genuine" and score(r, d) is not None] for d in dets}

    summary = []
    for d in dets:
        a = auc(pos[d], neg[d])
        summary.append({
            "detector": NAMES[d],
            "ai_caught": f"{sum(v >= t for v in pos[d])} of {len(pos[d])}",
            "genuine_flagged": f"{sum(v >= t for v in neg[d])} of {len(neg[d])}",
            "forwarded_genuine_flagged": f"{sum(v >= t for v in fwd[d])} of {len(fwd[d])}",
            "auc": f"{a:.3f}" if a is not None else "-",
        })

    # ---------- print
    header = ["Group", "n"] + [NAMES[d] for d in dets]
    print(f"\nAI detector comparison: {scope}, flag threshold {t}\n")
    for title, n, cells in table:
        if n is None:
            print(f"\n{title}")
            continue
        print(f"  {title:<30} {n:>4}   " + "   ".join(f"{NAMES[d]}: {cells[d]}" for d in dets))
    print("\nSummary (AUC: 1.0 = perfect separation of AI fakes from genuine photos, 0.5 = guessing)")
    for s in summary:
        print(f"  {s['detector']:<22} AI caught {s['ai_caught']:<9} genuine flagged {s['genuine_flagged']:<9} "
              f"forwarded genuine flagged {s['forwarded_genuine_flagged']:<8} AUC {s['auc']}")

    # ---------- save
    RESULTS.mkdir(parents=True, exist_ok=True)
    tag = args.split or "all"
    md = RESULTS / f"detector_comparison_{tag}.md"
    lines = [f"# AI detector comparison (E4.2)", "",
             f"Scope: {scope}. Flag threshold: {t}. Generated {date.today().isoformat()}.", "",
             "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for title, n, cells in table:
        if n is None:
            lines.append(f"| **{title}** |" + " |" * (len(header) - 1))
        else:
            lines.append(f"| {title} | {n} | " + " | ".join(cells[d] for d in dets) + " |")
    lines += ["", "## Summary", "",
              "| Detector | AI fakes caught | Genuine flagged | Forwarded genuine flagged | AUC |",
              "|---|---|---|---|---|"]
    lines += [f"| {s['detector']} | {s['ai_caught']} | {s['genuine_flagged']} | "
              f"{s['forwarded_genuine_flagged']} | {s['auc']} |" for s in summary]
    lines += ["", "AUC: chance that a random AI fake scores higher than a random genuine photo "
              "(1.0 = perfect, 0.5 = no better than guessing). It does not depend on the threshold.", "",
              "## Chosen detectors", "", "_To fill in: the best two, with reasons._"]
    md.write_text("\n".join(lines), encoding="utf-8")

    with open(RESULTS / f"detector_summary_{tag}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    print(f"\nSaved {md.relative_to(ROOT)} and detector_summary_{tag}.csv")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="run detectors on every image and save scores")
    s.add_argument("--detectors", nargs="+", default=DETECTORS, choices=DETECTORS)
    c = sub.add_parser("compare", help="build the comparison table")
    c.add_argument("--split", help="only images in this split, e.g. tuning")
    c.add_argument("--split-col", default="split", help="manifest column holding the split (default: split)")
    c.add_argument("--threshold", type=float, default=0.5)
    args = p.parse_args()
    cmd_score(args) if args.cmd == "score" else cmd_compare(args)


if __name__ == "__main__":
    main()