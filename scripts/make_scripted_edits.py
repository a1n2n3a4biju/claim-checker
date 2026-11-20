"""
Scripted edits with masks (E1.3, owner: M2) — annotation-guided version.

Uses the dataset's Supervisely polygon annotations so edits make sense:
  Copy-move  CM_P_014.jpg           a real damage region of P_014 is cloned onto
                                    another spot on the car body of the same photo
  Splice     SP_P_014__D_007.jpg    a damage region from donor D_007 is pasted
                                    onto a body panel of P_014
  Masks      masks/<same name>.png  white = pixels that were changed

Where damage goes:
  - If the photo has body-panel polygons (Front-door, Hood, Fender, ...), the
    pasted damage must lie at least 95% inside one panel.
  - If it only has damage polygons, the paste goes near existing damage on a
    surface whose colour matches the paint around that damage.
Glass, lights, wheels and mirrors are never used as destinations.

Blending uses OpenCV Poisson blending (cv2.seamlessClone). By default (CLONE_MODE =
"hybrid") the damage keeps its own pixels and only the surrounding ring is
Poisson-blended, so dark damage doesn't fade. The mask is built from the pixels
that actually changed, so it includes the blended edge.

Each edit is saved with the source photo's own JPEG quantization tables
(JPEG_QUALITY = "keep"), so genuine and edited photos share the same JPEG quality.

Annotation files: for image P_014.jpg the script looks for P_014.jpg.json
(Supervisely style) or P_014.json in the annotation folder. When you rename
images to P_### / D_###, rename their .json files the same way.

This file is also imported by make_scripted_edits_auto.py (for its blending
code), so keep both files in the same folder.

How to run: edit the SETTINGS below, then
  python make_scripted_edits.py

Step 1: set LIST_CLASSES = True and run. It prints which class names your
        annotations use and makes no edits. If your damage or panel names
        differ from DAMAGE_CLASSES / PANEL_CLASSES, add them there.
Step 2: set LIST_CLASSES = False and run again to make the edits, then look at
        the previews.
"""

import json
import math
import random
import re
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, JpegImagePlugin

GENUINE_RE = re.compile(r"^P_\d+\.jpg$")
DONOR_RE = re.compile(r"^D_\d+\.jpg$")

DEFAULT_DAMAGE = ("damage,dent,scratch,cracked,crack,broken-part,missing-part,"
                  "paint-chip,flaking,corrosion")
DEFAULT_PANELS = ("panel,front-door,back-door,door,hood,fender,quarter-panel,trunk,"
                  "front-bumper,back-bumper,bumper,rocker-panel,roof")

MIN_SIDE = 256

# SETTINGS: edit these, then run the script
# (only used when this file is run directly, not when it is imported)

MAIN_FOLDER = Path("images")                      # your dataset folder

GENUINE_DIR = MAIN_FOLDER / "genuine"             # P_###.jpg
GENUINE_ANN_DIR = MAIN_FOLDER / "genuine_annotations"        # P_###.jpg.json
DONOR_IMAGES_DIR = MAIN_FOLDER / "donors" / "images"         # D_###.jpg
DONOR_ANN_DIR = MAIN_FOLDER / "donors" / "annotations"       # D_###.jpg.json
OUTPUT_DIR = MAIN_FOLDER / "Scripted_edits"       # edited JPEGs go here
MASKS_DIR = MAIN_FOLDER / "masks"                 # masks go here
PREVIEW_DIR = Path("previews")                    # original | edit | mask; None to turn off
LIST_CLASSES = False                              # True = only print class names, no edits

N_COPY_MOVE = 15
N_SPLICE = 15

DAMAGE_CLASSES = DEFAULT_DAMAGE   # comma-separated class names counted as damage
PANEL_CLASSES = DEFAULT_PANELS    # comma-separated class names counted as body panels
CLONE_MODE = "hybrid"             # "hybrid", "normal" or "mixed"
JPEG_QUALITY = "keep"             # "keep" = source photo's own JPEG tables, or a number like 90
SEED = 42
OVERWRITE = False                 # True = remake edits that already exist


MIN_DAMAGE_FRAC = 0.0008   # ignore damage polygons smaller than 0.08% of the photo
MAX_DAMAGE_FRAC = 0.15     # ...or larger than 15%
MIN_PANEL_FRAC = 0.01      # ignore panels smaller than 1% of the photo
INSIDE_PANEL = 0.95        # share of the pasted area that must lie on the panel
MAX_COLOR_DIST = 18.0      # LAB distance for "same paint" when no panels exist


# helpers

def norm(title: str) -> str:
    return re.sub(r"[\s_]+", "-", title.strip().lower())


def kernel(size: int):
    size = max(1, int(size))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def find_ann(ann_dir: Path, img_path: Path):
    for cand in (ann_dir / f"{img_path.name}.json", ann_dir / f"{img_path.stem}.json"):
        if cand.exists():
            return cand
    return None


def load_jpeg(path: Path):
    with Image.open(path) as im:
        if im.format != "JPEG":
            raise ValueError(f"{path.name} is not a real JPEG (format: {im.format})")
        qtables = im.quantization
        sampling = JpegImagePlugin.get_sampling(im)
        arr = np.asarray(im.convert("RGB")).copy()
    return arr, qtables, sampling


def load_objects(ann_file: Path, w: int, h: int):
    """Return [(class, mask)] with polygons scaled to the real image size."""
    data = json.loads(ann_file.read_text())
    aw, ah = data["size"]["width"], data["size"]["height"]
    if abs(aw / ah - w / h) > 0.01:
        raise ValueError(f"annotation size {aw}x{ah} does not match image {w}x{h}")
    sx, sy = w / aw, h / ah
    objs = []
    for o in data.get("objects", []):
        if o.get("geometryType") != "polygon":
            continue
        ext = o["points"]["exterior"]
        if len(ext) < 3:
            continue
        m = np.zeros((h, w), np.uint8)
        cv2.fillPoly(m, [np.round(np.array(ext) * [sx, sy]).astype(np.int32)], 255)
        for hole in o["points"].get("interior", []):
            if len(hole) >= 3:
                cv2.fillPoly(m, [np.round(np.array(hole) * [sx, sy]).astype(np.int32)], 0)
        objs.append((norm(o["classTitle"]), m))
    return objs


class Photo:
    def __init__(self, path: Path, ann_dir: Path, damage: set, panels: set):
        self.path = path
        self.img, self.qtables, self.sampling = load_jpeg(path)
        h, w = self.img.shape[:2]
        if min(h, w) < MIN_SIDE:
            raise ValueError(f"too small ({w}x{h})")
        ann = find_ann(ann_dir, path)
        if ann is None:
            raise FileNotFoundError(f"no annotation for {path.name} in {ann_dir}")
        objs = load_objects(ann, w, h)
        area = w * h
        self.damages = [m for c, m in objs if c in damage
                        and MIN_DAMAGE_FRAC <= cv2.countNonZero(m) / area <= MAX_DAMAGE_FRAC]
        self.panels = [m for c, m in objs if c in panels
                       and cv2.countNonZero(m) / area >= MIN_PANEL_FRAC]
        all_damage = np.zeros((h, w), np.uint8)
        for c, m in objs:
            if c in damage:
                all_damage |= m
        self.avoid = cv2.dilate(all_damage, kernel(15))   # never paste over existing damage
        self.lab = cv2.cvtColor(self.img, cv2.COLOR_RGB2LAB).astype(np.float32)


# patch, placement, cloning

def extract_patch(img, mask, rng, scale=None, target_area=None):
    """Cut the damage plus a small margin of surrounding surface, then scale/rotate."""
    H, W = img.shape[:2]
    x, y, w, h = cv2.boundingRect(mask)
    pad = max(4, int(0.15 * max(w, h)))
    x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
    patch = img[y0:y1, x0:x1].copy()
    core = mask[y0:y1, x0:x1].copy()              # the damage itself
    pm = cv2.dilate(core, kernel(max(3, pad // 2)))  # damage plus a thin ring of surface

    if target_area is not None:
        s = math.sqrt(target_area / max(1, cv2.countNonZero(pm)))
    else:
        s = rng.uniform(*scale)
    s = float(np.clip(s, 0.3, 3.0))
    size = (max(8, round(patch.shape[1] * s)), max(8, round(patch.shape[0] * s)))
    patch = cv2.resize(patch, size, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    pm = cv2.resize(pm, size, interpolation=cv2.INTER_NEAREST)
    core = cv2.resize(core, size, interpolation=cv2.INTER_NEAREST)

    angle = rng.uniform(-10, 10)
    ph, pw = pm.shape
    M = cv2.getRotationMatrix2D((pw / 2, ph / 2), angle, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(ph * sin + pw * cos) + 1, int(ph * cos + pw * sin) + 1
    M[0, 2] += nw / 2 - pw / 2
    M[1, 2] += nh / 2 - ph / 2
    patch = cv2.warpAffine(patch, M, (nw, nh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    pm = cv2.warpAffine(pm, M, (nw, nh), flags=cv2.INTER_NEAREST, borderValue=0)
    core = cv2.warpAffine(core, M, (nw, nh), flags=cv2.INTER_NEAREST, borderValue=0)

    # zero border so seamlessClone never sees mask pixels on the patch edge
    patch = cv2.copyMakeBorder(patch, 3, 3, 3, 3, cv2.BORDER_REFLECT)
    pm = cv2.copyMakeBorder(pm, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=0)
    core = cv2.copyMakeBorder(core, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=0)
    return patch, pm, core


def ring_color(photo: Photo, mask):
    ring = cv2.dilate(mask, kernel(21)) & ~cv2.dilate(mask, kernel(7)) & ~photo.avoid
    if cv2.countNonZero(ring) < 30:
        return None
    return photo.lab[ring > 0].mean(axis=0)


def find_spot(photo: Photo, pm, rng, panel=None, anchor=None, ref=None, extra_avoid=None, tries=400):
    H, W = photo.img.shape[:2]
    ph, pw = pm.shape
    if ph >= H - 2 or pw >= W - 2:
        return None
    on = pm > 0
    avoid = photo.avoid if extra_avoid is None else (photo.avoid | extra_avoid)
    if panel is not None:
        ys, xs = np.nonzero(panel)
    for _ in range(tries):
        if panel is not None:
            i = rng.randrange(len(xs))
            x, y = int(xs[i]) - pw // 2, int(ys[i]) - ph // 2
        else:
            ax, ay, aw, ah = anchor
            a = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(0.7, 2.0) * max(aw, ah, pw, ph)
            x = int(ax + aw / 2 + d * math.cos(a) - pw / 2)
            y = int(ay + ah / 2 + d * math.sin(a) - ph / 2)
        if x < 1 or y < 1 or x + pw > W - 1 or y + ph > H - 1:
            continue
        if avoid[y:y + ph, x:x + pw][on].any():
            continue
        if panel is not None:
            if (panel[y:y + ph, x:x + pw][on] > 0).mean() < INSIDE_PANEL:
                continue
        else:
            if ref is None:
                return None
            col = photo.lab[y:y + ph, x:x + pw][on].mean(axis=0)
            if np.linalg.norm(col - ref) > MAX_COLOR_DIST:
                continue
        return x, y
    return None


def clone(photo: Photo, patch, pm, core, x, y, mode: str):
    """
    normal: Poisson blending (seamless edges, but colours drift toward the
            surroundings, so dark damage can fade)
    mixed:  Poisson blending that keeps the stronger texture of the two images
    hybrid: Poisson blending for the surface ring, original pixels for the
            damage itself (seamless edges and the damage keeps its colour)
    """
    target = photo.img
    ph, pw = pm.shape

    # shift the patch's colours so its surface ring matches the paint it lands on
    # (matters for splices, where the donor car has a different colour)
    ring = (pm > 0) & (core == 0)
    if ring.sum() > 30:
        dst_ring = target[y:y + ph, x:x + pw][ring].astype(np.float32).mean(axis=0)
        src_ring = patch[ring].astype(np.float32).mean(axis=0)
        patch = np.clip(patch.astype(np.float32) + (dst_ring - src_ring), 0, 255).astype(np.uint8)

    bx, by, bw, bh = cv2.boundingRect(pm)
    center = (x + bx + bw // 2, y + by + bh // 2)
    flag = cv2.MIXED_CLONE if mode == "mixed" else cv2.NORMAL_CLONE
    out = cv2.seamlessClone(patch, target, pm, center, flag)

    if mode == "hybrid":
        a = cv2.GaussianBlur(cv2.erode(core, kernel(3)), (0, 0), 2.0).astype(np.float32)[..., None] / 255
        region = out[y:y + ph, x:x + pw].astype(np.float32)
        out[y:y + ph, x:x + pw] = (region * (1 - a) + patch.astype(np.float32) * a).astype(np.uint8)

    placed = np.zeros(target.shape[:2], np.uint8)
    placed[y:y + ph, x:x + pw] = pm
    diff = np.abs(out.astype(np.int16) - target.astype(np.int16)).max(axis=2)
    changed = ((diff > 8) & (cv2.dilate(placed, kernel(15)) > 0)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(changed, cv2.MORPH_CLOSE, kernel(7)) | placed
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return out, filled


# the two edit types

def make_copy_move(photo: Photo, rng, mode):
    H, W = photo.img.shape[:2]
    for _ in range(25):
        dmg = rng.choice(photo.damages)
        patch, pm, core = extract_patch(photo.img, dmg, rng, scale=(0.8, 1.2))
        src_area = cv2.dilate(dmg, kernel(25))
        if photo.panels:
            panel = rng.choice(photo.panels)
            spot = find_spot(photo, pm, rng, panel=panel, extra_avoid=src_area)
        else:
            spot = find_spot(photo, pm, rng, anchor=cv2.boundingRect(dmg),
                             ref=ring_color(photo, dmg), extra_avoid=src_area)
        if spot:
            return clone(photo, patch, pm, core, *spot, mode)
    raise RuntimeError("no sensible destination found")


def make_splice(photo: Photo, donor: Photo, rng, mode):
    H, W = photo.img.shape[:2]
    for _ in range(25):
        dmg = rng.choice(donor.damages)
        if photo.panels:
            panel = rng.choice(photo.panels)
            area = rng.uniform(0.05, 0.25) * cv2.countNonZero(panel)
            area = float(np.clip(area, 0.004 * W * H, 0.08 * W * H))
            patch, pm, core = extract_patch(donor.img, dmg, rng, target_area=area)
            spot = find_spot(photo, pm, rng, panel=panel)
        elif photo.damages:
            anchor = rng.choice(photo.damages)
            area = rng.uniform(0.6, 1.5) * cv2.countNonZero(anchor)
            patch, pm, core = extract_patch(donor.img, dmg, rng, target_area=area)
            spot = find_spot(photo, pm, rng, anchor=cv2.boundingRect(anchor),
                             ref=ring_color(photo, anchor))
        else:
            raise RuntimeError("photo has no panels or damage to place against")
        if spot:
            return clone(photo, patch, pm, core, *spot, mode)
    raise RuntimeError("no sensible destination found")


# output

def save_edit(arr, dst: Path, quality, qtables, sampling):
    img = Image.fromarray(arr)
    if quality == "keep":
        img.save(dst, format="JPEG", qtables=qtables, subsampling=sampling)
    else:
        img.save(dst, format="JPEG", quality=int(quality))


def save_preview(orig, edit, mask, dst: Path, width=500):
    overlay = edit.copy()
    red = np.zeros_like(edit)
    red[..., 0] = 255
    on = mask > 0
    overlay[on] = (0.55 * edit[on] + 0.45 * red[on]).astype(np.uint8)
    h = int(orig.shape[0] * width / orig.shape[1])
    tiles = [cv2.resize(a, (width, h), interpolation=cv2.INTER_AREA) for a in (orig, edit, overlay)]
    Image.fromarray(np.hstack(tiles)).save(dst)


def list_classes(folders):
    for label, img_dir, ann_dir, pattern in folders:
        counts = Counter()
        n = 0
        for p in sorted(img_dir.iterdir()):
            if not pattern.match(p.name):
                continue
            ann = find_ann(ann_dir, p)
            if ann is None:
                continue
            n += 1
            titles = {norm(o["classTitle"]) for o in json.loads(ann.read_text()).get("objects", [])}
            counts.update(titles)
        print(f"\n{label}: {n} annotated images. Images containing each class:")
        for title, c in counts.most_common():
            print(f"  {title:<20} {c}")


def main() -> int:
    if LIST_CLASSES:
        folders = [("Genuine", GENUINE_DIR, GENUINE_ANN_DIR, GENUINE_RE)]
        if DONOR_IMAGES_DIR is not None and DONOR_ANN_DIR is not None:
            folders.append(("Donors", DONOR_IMAGES_DIR, DONOR_ANN_DIR, DONOR_RE))
        for label, img_dir, ann_dir, _ in folders:
            for d in (img_dir, ann_dir):
                if not d.is_dir():
                    print(f"{label}: folder not found: {d.resolve()}", file=sys.stderr)
                    return 1
        list_classes(folders)
        return 0

    if CLONE_MODE not in ("hybrid", "normal", "mixed"):
        print('CLONE_MODE must be "hybrid", "normal" or "mixed"', file=sys.stderr)
        return 1
    if JPEG_QUALITY != "keep" and not str(JPEG_QUALITY).isdigit():
        print('JPEG_QUALITY must be "keep" or a number', file=sys.stderr)
        return 1
    needed = [GENUINE_DIR, GENUINE_ANN_DIR]
    if N_SPLICE:
        needed += [DONOR_IMAGES_DIR, DONOR_ANN_DIR]
    for d in needed:
        if d is None or not d.is_dir():
            print(f"Folder not found: {d if d is None else d.resolve()}", file=sys.stderr)
            return 1

    damage = {norm(c) for c in DAMAGE_CLASSES.split(",")}
    panels = {norm(c) for c in PANEL_CLASSES.split(",")}
    for d in (OUTPUT_DIR, MASKS_DIR, PREVIEW_DIR):
        if d is not None:
            d.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)

    def load_all(folder, ann_dir, pattern):
        photos, unannotated = [], 0
        for p in sorted(folder.iterdir()):
            if not pattern.match(p.name):
                continue
            if find_ann(ann_dir, p) is None:
                unannotated += 1          # normal: only marked photos have annotations
                continue
            try:
                photos.append(Photo(p, ann_dir, damage, panels))
            except Exception as exc:
                print(f"skip {p.name}: {exc}", file=sys.stderr)
        print(f"{folder}: {len(photos)} annotated photos loaded, {unannotated} without annotations")
        return photos

    genuine = load_all(GENUINE_DIR, GENUINE_ANN_DIR, GENUINE_RE)
    donors = ([d for d in load_all(DONOR_IMAGES_DIR, DONOR_ANN_DIR, DONOR_RE) if d.damages]
              if N_SPLICE else [])
    rng.shuffle(genuine)
    rng.shuffle(donors)

    cm_ok = [p for p in genuine if p.damages]
    sp_ok = [p for p in genuine if p.panels or p.damages]
    print(f"Genuine usable for copy-move: {len(cm_ok)}, for splice: {len(sp_ok)}, "
          f"donors with damage: {len(donors)}")
    if N_SPLICE and not donors:
        print("No donor has a usable damage polygon; check DAMAGE_CLASSES", file=sys.stderr)
        return 1

    used = set()
    stats = Counter()

    def finish(name, photo, out, mask):
        frac = cv2.countNonZero(mask) / mask.size
        save_edit(out, OUTPUT_DIR / f"{name}.jpg", str(JPEG_QUALITY), photo.qtables, photo.sampling)
        Image.fromarray(mask).save(MASKS_DIR / f"{name}.png")
        if PREVIEW_DIR is not None:
            save_preview(photo.img, out, mask, PREVIEW_DIR / f"{name}.png")
        print(f"{name}.jpg  edited area {frac:.1%}")

    # copy-move first: fewer photos qualify
    done = 0
    for photo in cm_ok:
        if done >= N_COPY_MOVE:
            break
        name = f"CM_{photo.path.stem}"
        used.add(photo.path.stem)
        if (OUTPUT_DIR / f"{name}.jpg").exists() and not OVERWRITE:
            done += 1; stats["skipped"] += 1
            continue
        try:
            out, mask = make_copy_move(photo, random.Random(f"{SEED}-{name}"), CLONE_MODE)
        except Exception as exc:
            print(f"try next ({name}: {exc})", file=sys.stderr)
            used.discard(photo.path.stem)
            continue
        finish(name, photo, out, mask)
        done += 1; stats["written"] += 1
    stats["copy-move"] = done

    done, di = 0, 0
    for photo in sp_ok:
        if done >= N_SPLICE:
            break
        if photo.path.stem in used:
            continue
        existing = list(OUTPUT_DIR.glob(f"SP_{photo.path.stem}__*.jpg"))
        if existing and not OVERWRITE:
            used.add(photo.path.stem)
            done += 1; stats["skipped"] += 1
            continue
        result = None
        for _ in range(min(5, len(donors))):
            donor = donors[di % len(donors)]
            di += 1
            name = f"SP_{photo.path.stem}__{donor.path.stem}"
            try:
                result = make_splice(photo, donor, random.Random(f"{SEED}-{name}"), CLONE_MODE)
                break
            except Exception as exc:
                print(f"try next ({name}: {exc})", file=sys.stderr)
        if result is None:
            continue
        used.add(photo.path.stem)
        finish(name, photo, *result)
        done += 1; stats["written"] += 1
    stats["splice"] = done

    print(f"\nDone: copy-move {stats['copy-move']}/{N_COPY_MOVE}, "
          f"splice {stats['splice']}/{N_SPLICE} "
          f"({stats['written']} written, {stats['skipped']} already existed).")
    if stats["copy-move"] < N_COPY_MOVE or stats["splice"] < N_SPLICE:
        print("Not enough usable photos; add more annotated photos or adjust class lists.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())