"""
Scripted edits without damage annotations (E1.3).

Finds where things are automatically, then reuses the blending code in
make_scripted_edits.py (keep both files in the same folder):

  Car body   Mask R-CNN pretrained on COCO (torchvision, CPU, no training) gives
             the car's pixel mask. CAR_MASK_METHOD = "grabcut" uses OpenCV GrabCut
             instead (no PyTorch needed, less reliable).
  Panels     inside the car mask, smooth evenly coloured areas (low local
             variance), away from the car outline, without dark low-saturation
             areas that are probably glass or tyres. New damage goes here.
  Damage     spots whose edge energy is much higher than the rest of their
             region and that sit away from region borders (where trims and
             panel gaps are). On donors the search runs inside the annotated
             body panels (Front-door, Hood, ...); on genuine photos, inside the
             car mask.

  Copy-move  CM_P_014.jpg           a damage candidate of P_014 is cloned onto a
                                    smooth panel area of the same car
  Splice     SP_P_014__D_007.jpg    a damage candidate from donor D_007 is pasted
                                    onto a smooth panel area of P_014
  Masks      masks/<same name>.png  white = pixels that changed

The detection is heuristic: it sometimes picks a door handle, a badge or a
reflection as "damage". Always look at the previews and delete bad edits; rerun
and only the missing ones are made again.

Install:  pip install torch torchvision opencv-python pillow numpy
          (the Mask R-CNN weights, about 170 MB, download on first run)

How to run: edit the SETTINGS below, then
  python make_scripted_edits_auto.py

Step 1: set DEBUG_ONLY = True and run. It writes overlays to DEBUG_DIR and makes
        no edits. Blue = car outline, green = smooth panel areas, red = damage
        candidates (number = how unusual the texture is).
Step 2: set DEBUG_ONLY = False and run again to make the edits.
"""

import random
import re
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import make_scripted_edits as base   # blending, placement and saving code


ROOT = Path(__file__).resolve().parent.parent
MAIN_FOLDER = ROOT / "data" / "images"                      # your dataset folder

GENUINE_DIR = MAIN_FOLDER / "genuine"             # P_###.jpg
DONOR_IMAGES_DIR = MAIN_FOLDER / "donors" / "images"         # D_###.jpg
DONOR_ANN_DIR = MAIN_FOLDER / "donors" / "annotations"       # D_###.jpg.json (parts); None if missing
OUTPUT_DIR = MAIN_FOLDER / "Scripted_edits"       # edited JPEGs go here
MASKS_DIR = MAIN_FOLDER / "masks"                 # masks go here
PREVIEW_DIR = ROOT / "data" / "images" / "previews"         # original | edit | mask; None to turn off
DEBUG_DIR = ROOT / "data" / "images" / "debug"    # detection overlays; None to turn off
DEBUG_ONLY = False                                # True = only write overlays, no edits

N_COPY_MOVE = 15
N_SPLICE = 15

CAR_MASK_METHOD = "maskrcnn"    # "maskrcnn" (needs PyTorch) or "grabcut" (OpenCV only)
MIN_SCORE = 0.6                 # Mask R-CNN confidence; lower (0.4) if close-ups find no car
DAMAGE_FACTOR = 2.0             # higher = fewer false "damage" (handles, badges); lower = more
KEEP_DARK = False               # True for black/dark cars
PANEL_CLASSES = base.DEFAULT_PANELS   # donor part classes searched for damage
CLONE_MODE = "hybrid"           # "hybrid", "normal" or "mixed"
JPEG_QUALITY = "keep"           # "keep" = source photo's own JPEG tables, or a number like 90
SEED = 42
OVERWRITE = True               # True = remake edits that already exist


GENUINE_RE = re.compile(r"^P_\d+\.jpg$")
DONOR_RE = re.compile(r"^D_\d+\.jpg$")
COCO_VEHICLES = {3}               # COCO labels: 3 = car, 8 = truck

MIN_DAMAGE = 0.001                   # damage candidate: 0.1% ...
MAX_DAMAGE = 0.06                    # ... to 6% of the photo
MIN_SMOOTH = 0.01                    # smooth panel area: at least 1% of the photo
SMOOTH_STD_FLOOR = 8.0               # local grey-level std always counted as smooth paint


# car mask

class CarMasker:
    def __init__(self, method: str, min_score: float):
        self.method = method
        self.min_score = min_score
        self.model = None
        if method == "maskrcnn":
            try:
                import torch  # noqa: F401
                from torchvision.models.detection import (
                    MaskRCNN_ResNet50_FPN_V2_Weights, maskrcnn_resnet50_fpn_v2)
            except ImportError:
                sys.exit("PyTorch/torchvision not installed. "
                         "pip install torch torchvision, or set CAR_MASK_METHOD = \"grabcut\"")
            weights = MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT
            self.model = maskrcnn_resnet50_fpn_v2(weights=weights).eval()

    def __call__(self, img):
        return self._rcnn(img) if self.method == "maskrcnn" else self._grabcut(img)

    def _rcnn(self, img):
        import torch
        t = torch.from_numpy(img).permute(2, 0, 1).float() / 255
        with torch.no_grad():
            out = self.model([t])[0]
        best, best_area = None, 0
        for label, score, m in zip(out["labels"], out["scores"], out["masks"]):
            if int(label) in COCO_VEHICLES and float(score) >= self.min_score:
                mask = (m[0].numpy() > 0.5).astype(np.uint8) * 255
                area = cv2.countNonZero(mask)
                if area > best_area:
                    best, best_area = mask, area
        return best

    @staticmethod
    def _grabcut(img):
        h, w = img.shape[:2]
        s = min(1.0, 600 / max(h, w))
        small = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
        sh, sw = small.shape[:2]
        rect = (int(0.05 * sw), int(0.08 * sh), int(0.90 * sw), int(0.84 * sh))
        gc = np.zeros((sh, sw), np.uint8)
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(small, gc, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
        fg = np.isin(gc, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8) * 255
        fg = cv2.resize(fg, (w, h), interpolation=cv2.INTER_NEAREST)
        return largest_component(fg)


def largest_component(mask):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == i).astype(np.uint8) * 255


# texture features

class Features:
    def __init__(self, img):
        h, w = img.shape[:2]
        self.unit = min(h, w)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        win = odd(max(9, round(0.02 * self.unit)))
        self.energy = cv2.blur(cv2.magnitude(gx, gy), (win, win))
        mean = cv2.blur(gray, (win, win))
        sq = cv2.blur(gray * gray, (win, win))
        self.std = np.sqrt(np.maximum(sq - mean * mean, 0))
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        s, v = hsv[..., 1], hsv[..., 2]
        dark = ((v < 55) | ((v < 90) & (s < 40))).astype(np.uint8) * 255
        self.dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, base.kernel(5))


def odd(n):
    n = int(n)
    return n if n % 2 else n + 1


def inner_region(region, margin):
    dist = cv2.distanceTransform((region > 0).astype(np.uint8), cv2.DIST_L2, 5)
    return (dist > margin).astype(np.uint8) * 255


def smooth_areas(f: Features, car, keep_dark):
    """Smooth, evenly coloured parts of the car: where new damage can go."""
    area = car.size
    region = inner_region(car, 0.03 * f.unit)
    if not keep_dark:
        region &= ~f.dark
    if cv2.countNonZero(region) < MIN_SMOOTH * area:
        return []
    # median roughness of the car, but never stricter than a floor, so a car that is
    # smooth everywhere isn't split into random halves
    thr = max(float(np.percentile(f.std[region > 0], 50)), SMOOTH_STD_FLOOR)
    smooth = ((f.std <= thr) & (region > 0)).astype(np.uint8) * 255
    k = base.kernel(odd(0.02 * f.unit))
    smooth = cv2.morphologyEx(cv2.morphologyEx(smooth, cv2.MORPH_OPEN, k), cv2.MORPH_CLOSE, k)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(smooth, 8)
    comps = [(stats[i, cv2.CC_STAT_AREA], i) for i in range(1, n)
             if stats[i, cv2.CC_STAT_AREA] >= MIN_SMOOTH * area]
    comps.sort(reverse=True)
    return [(labels == i).astype(np.uint8) * 255 for _, i in comps[:6]]


def damage_candidates(f: Features, region, factor, keep_dark):
    """Spots with much more edge energy than the rest of the region."""
    area = region.size
    inner = inner_region(region, 0.025 * f.unit)
    if cv2.countNonZero(inner) < 0.005 * area:
        return []
    med = float(np.median(f.energy[inner > 0])) + 1e-6
    hot = ((f.energy > factor * med) & (inner > 0)).astype(np.uint8) * 255
    if not keep_dark:
        hot &= ~f.dark
    hot = cv2.morphologyEx(hot, cv2.MORPH_CLOSE, base.kernel(odd(0.015 * f.unit)))
    hot = cv2.morphologyEx(hot, cv2.MORPH_OPEN, base.kernel(5))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(hot, 8)
    out = []
    for i in range(1, n):
        frac = stats[i, cv2.CC_STAT_AREA] / area
        if not (MIN_DAMAGE <= frac <= MAX_DAMAGE):
            continue
        comp = (labels == i).astype(np.uint8)
        score = float(f.energy[comp > 0].mean() / med)
        contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        hull = cv2.convexHull(np.vstack(contours))
        m = np.zeros_like(comp)
        cv2.fillPoly(m, [hull], 255)
        out.append((score, m))
    out.sort(key=lambda t: -t[0])
    return out[:3]


# photos

class AutoPhoto:
    """Same attributes as base.Photo, so base.make_copy_move/make_splice work."""

    def __init__(self, path, masker, ann_dir=None, panel_classes=None):
        self.path = path
        self.img, self.qtables, self.sampling = base.load_jpeg(path)
        h, w = self.img.shape[:2]
        if min(h, w) < base.MIN_SIDE:
            raise ValueError(f"too small ({w}x{h})")
        f = Features(self.img)
        self.lab = cv2.cvtColor(self.img, cv2.COLOR_RGB2LAB).astype(np.float32)
        self.car = None
        self.scores = []

        # where to search for damage: annotated body panels if available, else the car
        regions = []
        ann = base.find_ann(ann_dir, path) if ann_dir else None
        if ann is not None:
            objs = base.load_objects(ann, w, h)
            regions = [m for c, m in objs if c in panel_classes
                       and cv2.countNonZero(m) >= 0.01 * h * w]
        if not regions:
            self.car = masker(self.img)
            if self.car is None or cv2.countNonZero(self.car) < 0.05 * h * w:
                raise ValueError("no car found")
            regions = [self.car]

        cands = []
        for r in regions:
            cands += damage_candidates(f, r, DAMAGE_FACTOR, KEEP_DARK)
        cands.sort(key=lambda t: -t[0])
        self.scores = [s for s, _ in cands]
        self.damages = [m for _, m in cands]

        if self.car is None:
            self.car = np.zeros((h, w), np.uint8)
            for r in regions:
                self.car |= r
        self.panels = smooth_areas(f, self.car, KEEP_DARK)

        avoid = np.zeros((h, w), np.uint8)
        for m in self.damages:
            avoid |= m
        self.avoid = cv2.dilate(avoid, base.kernel(15))


def save_debug(photo: AutoPhoto, dst: Path, width=700):
    view = photo.img.copy()
    for p in photo.panels:
        g = p > 0
        view[g] = (0.6 * view[g] + 0.4 * np.array([0, 200, 0])).astype(np.uint8)
    contours, _ = cv2.findContours(photo.car, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(view, contours, -1, (0, 120, 255), 2)
    for score, m in zip(photo.scores, photo.damages):
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(view, cs, -1, (255, 0, 0), 2)
        x, y, _, _ = cv2.boundingRect(m)
        base_text(view, f"{score:.1f}", (x, max(15, y - 5)))
    h = int(view.shape[0] * width / view.shape[1])
    Image.fromarray(cv2.resize(view, (width, h), interpolation=cv2.INTER_AREA)).save(dst)


def base_text(img, text, org):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)


# main

def main() -> int:
    if CLONE_MODE not in ("hybrid", "normal", "mixed"):
        print('CLONE_MODE must be "hybrid", "normal" or "mixed"', file=sys.stderr)
        return 1
    if CAR_MASK_METHOD not in ("maskrcnn", "grabcut"):
        print('CAR_MASK_METHOD must be "maskrcnn" or "grabcut"', file=sys.stderr)
        return 1
    if JPEG_QUALITY != "keep" and not str(JPEG_QUALITY).isdigit():
        print('JPEG_QUALITY must be "keep" or a number', file=sys.stderr)
        return 1
    if DEBUG_ONLY and DEBUG_DIR is None:
        print("DEBUG_ONLY needs DEBUG_DIR to be set", file=sys.stderr)
        return 1
    for d in (GENUINE_DIR, DONOR_IMAGES_DIR if N_SPLICE else None):
        if d is not None and not d.is_dir():
            print(f"Folder not found: {d.resolve()}", file=sys.stderr)
            return 1

    panel_classes = {base.norm(c) for c in PANEL_CLASSES.split(",")}
    for d in (OUTPUT_DIR, MASKS_DIR, PREVIEW_DIR, DEBUG_DIR):
        if d is not None and not (DEBUG_ONLY and d in (OUTPUT_DIR, MASKS_DIR, PREVIEW_DIR)):
            d.mkdir(parents=True, exist_ok=True)

    masker = CarMasker(CAR_MASK_METHOD, MIN_SCORE)

    def load_all(folder, pattern, ann_dir=None):
        photos = []
        files = sorted(p for p in folder.iterdir() if pattern.match(p.name))
        for k, p in enumerate(files, 1):
            print(f"\r{folder.name}: analysing {k}/{len(files)}", end="", flush=True)
            try:
                ph = AutoPhoto(p, masker, ann_dir, panel_classes)
            except Exception as exc:
                print(f"\nskip {p.name}: {exc}", file=sys.stderr)
                continue
            photos.append(ph)
            if DEBUG_DIR is not None:
                save_debug(ph, DEBUG_DIR / f"{p.stem}.png")
        print()
        return photos

    genuine = load_all(GENUINE_DIR, GENUINE_RE)
    donors = load_all(DONOR_IMAGES_DIR, DONOR_RE, DONOR_ANN_DIR) if N_SPLICE else []
    donors = [d for d in donors if d.damages]

    cm_ok = [p for p in genuine if p.damages and p.panels]
    sp_ok = [p for p in genuine if p.panels]
    print(f"Genuine usable for copy-move: {len(cm_ok)}, for splice: {len(sp_ok)}, "
          f"donors with damage candidates: {len(donors)}")
    if DEBUG_ONLY:
        print(f"Overlays written to {DEBUG_DIR.resolve()}")
        return 0
    if N_SPLICE and not donors:
        print("No donor has a damage candidate; try a lower DAMAGE_FACTOR", file=sys.stderr)
        return 1

    rng = random.Random(SEED)
    rng.shuffle(cm_ok)
    rng.shuffle(sp_ok)
    rng.shuffle(donors)
    used, stats = set(), Counter()

    def finish(name, photo, out, mask):
        frac = cv2.countNonZero(mask) / mask.size
        base.save_edit(out, OUTPUT_DIR / f"{name}.jpg", str(JPEG_QUALITY), photo.qtables, photo.sampling)
        Image.fromarray(mask).save(MASKS_DIR / f"{name}.png")
        if PREVIEW_DIR is not None:
            base.save_preview(photo.img, out, mask, PREVIEW_DIR / f"{name}.png")
        print(f"{name}.jpg  edited area {frac:.1%}")

    done = 0
    for photo in cm_ok:
        if done >= N_COPY_MOVE:
            break
        name = f"CM_{photo.path.stem}"
        if (OUTPUT_DIR / f"{name}.jpg").exists() and not OVERWRITE:
            used.add(photo.path.stem)
            done += 1; stats["skipped"] += 1
            continue
        try:
            out, mask = base.make_copy_move(photo, random.Random(f"{SEED}-{name}"), CLONE_MODE)
        except Exception as exc:
            print(f"try next ({name}: {exc})", file=sys.stderr)
            continue
        used.add(photo.path.stem)
        finish(name, photo, out, mask)
        done += 1; stats["written"] += 1
    stats["copy-move"] = done

    done, di = 0, 0
    for photo in sp_ok:
        if done >= N_SPLICE:
            break
        if photo.path.stem in used:
            continue
        if list(OUTPUT_DIR.glob(f"SP_{photo.path.stem}__*.jpg")) and not OVERWRITE:
            used.add(photo.path.stem)
            done += 1; stats["skipped"] += 1
            continue
        result = None
        for _ in range(min(5, len(donors))):
            donor = donors[di % len(donors)]
            di += 1
            name = f"SP_{photo.path.stem}__{donor.path.stem}"
            try:
                result = base.make_splice(photo, donor, random.Random(f"{SEED}-{name}"), CLONE_MODE)
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
        print("Not enough usable photos. Look at the debug overlays; try a lower "
              "DAMAGE_FACTOR, or KEEP_DARK = True for dark cars.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())