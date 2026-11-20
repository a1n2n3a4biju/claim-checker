"""
Scripted edits without damage annotations (E1.3).

Finds where things are automatically, then blends the edits in with OpenCV
Poisson blending (cv2.seamlessClone). Self-contained: needs no other script.

  Car body   Mask R-CNN pretrained on COCO (torchvision, CPU, no training) gives
             the car's pixel mask. CAR_MASK_METHOD = "grabcut" uses OpenCV GrabCut
             instead (no PyTorch needed, less reliable).
  Panels     inside the car mask, smooth evenly coloured areas (low local
             variance), away from the car outline, without dark low-saturation
             areas that are probably glass or tyres. New damage goes here.
  Damage     spots whose edge energy is much higher than the rest of their
             region and that sit away from region borders (where trims and
             panel gaps are). On donors the search runs inside the annotated
             body panels (Front-door, Hood, ...) if part annotations exist;
             otherwise (and always on genuine photos) inside the car mask.

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


DEFAULT_PANELS = ("panel,front-door,back-door,door,hood,fender,quarter-panel,trunk,"
                  "front-bumper,back-bumper,bumper,rocker-panel,roof")
MIN_SIDE = 256
INSIDE_PANEL = 0.95        # share of the pasted area that must lie on the panel
MAX_COLOR_DIST = 18.0      # LAB distance for "same paint" when no panels exist


# SETTINGS: edit these, then run the script
ROOT_DIR = Path(__file__).resolve().parent.parent
MAIN_FOLDER = ROOT_DIR / "data" / "images"                      # your dataset folder

GENUINE_DIR = MAIN_FOLDER / "genuine"             # P_###.jpg
DONOR_IMAGES_DIR = MAIN_FOLDER / "donors"         # D_###.jpg
DONOR_ANN_DIR = None                              # optional part annotations, e.g. MAIN_FOLDER / "donors" / "annotations"
OUTPUT_DIR = MAIN_FOLDER / "Scripted_edits"       # edited JPEGs go here
MASKS_DIR = MAIN_FOLDER / "masks"                 # masks go here
PREVIEW_DIR = None     # MAIN_FOLDER / "previews"      # original | edit | mask; None to turn off
DEBUG_DIR = None       #MAIN_FOLDER / "debug"          # detection overlays; None to turn off
DEBUG_ONLY = False                                # True = only write overlays, no edits

N_COPY_MOVE = 15
N_SPLICE = 15

CAR_MASK_METHOD = "maskrcnn"    # "maskrcnn" (needs PyTorch) or "grabcut" (OpenCV only)
MIN_SCORE = 0.6                 # Mask R-CNN confidence; lower (0.4) if close-ups find no car
DAMAGE_FACTOR = 2.0             # higher = fewer false "damage" (handles, badges); lower = more
KEEP_DARK = False               # True for black/dark cars
PANEL_CLASSES = DEFAULT_PANELS   # donor part classes searched for damage
CLONE_MODE = "hybrid"           # "hybrid", "normal" or "mixed"
JPEG_QUALITY = "keep"           # "keep" = source photo's own JPEG tables, or a number like 90
SEED = 42
OVERWRITE = False               # True = remake edits that already exist


GENUINE_RE = re.compile(r"^P_\d+\.jpg$")
DONOR_RE = re.compile(r"^D_\d+\.jpg$")
COCO_VEHICLES = {3, 8}               # COCO labels: 3 = car, 8 = truck

MIN_DAMAGE = 0.001                   # damage candidate: 0.1% ...
MAX_DAMAGE = 0.06                    # ... to 6% of the photo
MIN_SMOOTH = 0.01                    # smooth panel area: at least 1% of the photo
SMOOTH_STD_FLOOR = 8.0               # local grey-level std always counted as smooth paint


# shared helpers

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
        self.dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel(5))


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
    k = kernel(odd(0.02 * f.unit))
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
    hot = cv2.morphologyEx(hot, cv2.MORPH_CLOSE, kernel(odd(0.015 * f.unit)))
    hot = cv2.morphologyEx(hot, cv2.MORPH_OPEN, kernel(5))
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
    """One photo with its car mask, smooth panel areas and damage candidates."""

    def __init__(self, path, masker, ann_dir=None, panel_classes=None):
        self.path = path
        self.img, self.qtables, self.sampling = load_jpeg(path)
        h, w = self.img.shape[:2]
        if min(h, w) < MIN_SIDE:
            raise ValueError(f"too small ({w}x{h})")
        f = Features(self.img)
        self.lab = cv2.cvtColor(self.img, cv2.COLOR_RGB2LAB).astype(np.float32)
        self.car = None
        self.scores = []

        # where to search for damage: annotated body panels if available, else the car
        regions = []
        ann = find_ann(ann_dir, path) if ann_dir else None
        if ann is not None:
            objs = load_objects(ann, w, h)
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
        self.avoid = cv2.dilate(avoid, kernel(15))


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
        draw_label(view, f"{score:.1f}", (x, max(15, y - 5)))
    h = int(view.shape[0] * width / view.shape[1])
    Image.fromarray(cv2.resize(view, (width, h), interpolation=cv2.INTER_AREA)).save(dst)


def draw_label(img, text, org):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)


# patch, placement and blending

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


def ring_color(photo, mask):
    ring = cv2.dilate(mask, kernel(21)) & ~cv2.dilate(mask, kernel(7)) & ~photo.avoid
    if cv2.countNonZero(ring) < 30:
        return None
    return photo.lab[ring > 0].mean(axis=0)


def find_spot(photo, pm, rng, panel=None, anchor=None, ref=None, extra_avoid=None, tries=400):
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


def clone(photo, patch, pm, core, x, y, mode: str):
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


def make_copy_move(photo, rng, mode):
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


def make_splice(photo, donor, rng, mode):
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


# saving

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

    panel_classes = {norm(c) for c in PANEL_CLASSES.split(",")}
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
        save_edit(out, OUTPUT_DIR / f"{name}.jpg", str(JPEG_QUALITY), photo.qtables, photo.sampling)
        Image.fromarray(mask).save(MASKS_DIR / f"{name}.png")
        if PREVIEW_DIR is not None:
            save_preview(photo.img, out, mask, PREVIEW_DIR / f"{name}.png")
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
            out, mask = make_copy_move(photo, random.Random(f"{SEED}-{name}"), CLONE_MODE)
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
        print("Not enough usable photos. Look at the debug overlays; try a lower "
              "DAMAGE_FACTOR, or KEEP_DARK = True for dark cars.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())