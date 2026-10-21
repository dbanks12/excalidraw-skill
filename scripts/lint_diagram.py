#!/usr/bin/env python3
"""Check a diagram against the skill's budgets. Exit 1 on any FAIL.

Usage:
  python3 lint_diagram.py scene.excalidraw
  npx -y mcp-excalidraw-server@2.1.2 export | python3 lint_diagram.py -
  python3 lint_diagram.py scene.excalidraw --box 0,0,900,400   (one diagram on a shared canvas)

A node is a shape with a label. A zone is a shape without one. A text element
whose id is "<element id>-label" labels that element (place.py writes these). Name a
zone or panel title "<id>-title", never "<id>-label".
Free text (titles, rules panels, notes) has no word limit. Raise a limit with a flag
only when the brief says why.
An arrow segment within --max-skew degrees of vertical or horizontal must be exact.
So must a straight arrow between two shapes that overlap across it. Clear diagonals
and curves pass. An arrow end far from every shape is a WARN.
"""
import argparse
import json
import math
import sys

SHAPES = {"rectangle", "ellipse", "diamond"}
NEUTRAL = {"#1e1e1e", "#000000", "#495057", "#868e96", "transparent"}


def words(s):
    return len(s.split())


def points(e):
    """Absolute polyline points of an arrow or connector line."""
    pts = [(e["x"] + p[0], e["y"] + p[1]) for p in e.get("points", [])]
    if (e.get("customData") or {}).get("connect"):
        pts = pts[:-3]  # connector line: drop the arrowhead wings
    return pts


def bbox(e):
    if e.get("points"):
        xs, ys = zip(*[(e["x"] + p[0], e["y"] + p[1]) for p in e["points"]])
        return min(xs), min(ys), max(xs), max(ys)
    return e["x"], e["y"], e["x"] + e.get("width", 0), e["y"] + e.get("height", 0)


def meet(s, t):
    """Intersection point of two segments, or None (parallel segments never meet here)."""
    (x1, y1), (x2, y2) = s
    (x3, y3), (x4, y4) = t
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(d) < 1e-9:
        return None
    u = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
    v = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d
    if -1e-9 <= u <= 1 + 1e-9 and -1e-9 <= v <= 1 + 1e-9:
        return x1 + u * (x2 - x1), y1 + u * (y2 - y1)
    return None


def close(p, q, gap=2):
    return abs(p[0] - q[0]) <= gap and abs(p[1] - q[1]) <= gap


def through(seg, box, pad=4):
    """Segment enters the box interior (shrunk by pad)."""
    x0, y0, x1, y1 = box[0] + pad, box[1] + pad, box[2] - pad, box[3] - pad
    if x0 >= x1 or y0 >= y1:
        return False
    inside = lambda p: x0 < p[0] < x1 and y0 < p[1] < y1  # noqa: E731
    sides = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return inside(seg[0]) or inside(seg[1]) or any(meet(seg, side) for side in sides)


def text_box(t):
    """Rendered bounds of left-aligned free text: about 0.52 x fontSize per character."""
    lines = t["text"].split("\n")
    return (t["x"], t["y"], t["x"] + max(map(len, lines)) * 0.52 * t["fontSize"],
            t["y"] + len(lines) * 1.25 * t["fontSize"])


def overlap(a, b, pad=2):
    return a[0] < b[2] - pad and b[0] + pad < a[2] and a[1] < b[3] - pad and b[1] + pad < a[3]


def area(e):
    x0, y0, x1, y1 = bbox(e)
    return (x1 - x0) * (y1 - y0)


def band(e, k):
    """Where an exact vertical (k=0) or horizontal (k=1) arrow can meet shape e: 10px in from its corners.
    A diamond meets arrows only at its corners, so its band is its center line. Matches place.py."""
    lo, hi = bbox(e)[k], bbox(e)[k + 2]
    return ((lo + hi) / 2,) * 2 if e["type"] == "diamond" else (lo + 10, hi - 10)


def apart(a, b, k):
    """The two shapes have a gap between them along axis k."""
    return max(bbox(a)[k], bbox(b)[k]) > min(bbox(a)[k + 2], bbox(b)[k + 2])


def near(pt, box, gap=16):
    return box[0] - gap <= pt[0] <= box[2] + gap and box[1] - gap <= pt[1] <= box[3] + gap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", help=".excalidraw file, or - for stdin")
    ap.add_argument("--box", help="x0,y0,x1,y1: lint only elements inside this scene region")
    ap.add_argument("--max-nodes", type=int, default=15)
    ap.add_argument("--max-label-words", type=int, default=5, help="words per line of a node label")
    ap.add_argument("--max-arrow-words", type=int, default=5)
    ap.add_argument("--max-aspect", type=float, default=3.0, help="width / height of the drawing")
    ap.add_argument("--max-colors", type=int, default=5, help="distinct non-gray stroke colors")
    ap.add_argument("--max-skew", type=float, default=10.0,
                    help="degrees off vertical or horizontal that count as a crooked straight arrow")
    args = ap.parse_args()

    scene = json.load(sys.stdin if args.scene == "-" else open(args.scene))
    els = [e for e in scene["elements"] if not e.get("isDeleted")]
    if args.box:
        x0, y0, x1, y1 = map(float, args.box.split(","))
        els = [e for e in els if x0 <= bbox(e)[0] and bbox(e)[2] <= x1 and y0 <= bbox(e)[1] and bbox(e)[3] <= y1]
    by_id = {e["id"]: e for e in els}

    texts = [e for e in els if e["type"] == "text"]
    labels = {}  # labelled element id -> text element
    for t in texts:
        owner = t.get("containerId") or (t["id"][:-len("-label")] if t["id"].endswith("-label") else None)
        if owner in by_id:
            labels[owner] = t
    shapes = [e for e in els if e["type"] in SHAPES]
    nodes = [s for s in shapes if s["id"] in labels and labels[s["id"]].get("containerId")]
    edges = [e for e in els if e["type"] == "arrow"
             or (e["type"] == "line" and (e.get("customData") or {}).get("connect"))]
    fails, warns = [], []

    if len(nodes) > args.max_nodes:
        fails.append(f"nodes={len(nodes)} (max {args.max_nodes}). Split the diagram.")

    total = sum(words(t.get("originalText") or t["text"]) for t in texts)
    if els:
        boxes = [bbox(e) for e in els]
        w = max(b[2] for b in boxes) - min(b[0] for b in boxes)
        h = max(b[3] for b in boxes) - min(b[1] for b in boxes)
        if h and w / h > args.max_aspect:
            fails.append(f"aspect={w / h:.1f}:1 (max {args.max_aspect}:1). Wrap the flow or lay it out top-down.")

    for owner, t in labels.items():
        is_edge = by_id[owner] in edges
        limit = args.max_arrow_words if is_edge else args.max_label_words
        for line in (t.get("originalText") or t["text"]).splitlines():
            if words(line) > limit:
                fails.append(f"{owner}: '{line}' has {words(line)} words (max {limit}).")
        if t.get("containerId") and by_id[owner]["type"] in SHAPES:
            tx0, ty0, tx1, ty1 = bbox(t)
            bx0, by0, bx1, by1 = bbox(by_id[owner])
            if tx0 < bx0 or ty0 < by0 or tx1 > bx1 or ty1 > by1:
                fails.append(f"{owner}: label spills out of its box. Widen the box or cut words.")

    colors = {s.get("strokeColor", "").lower() for s in shapes + edges} - NEUTRAL - {""}
    if len(nodes) >= 4 and not colors:
        warns.append("every shape is gray or black. Color by kind, layer, or outcome.")
    if len(colors) > args.max_colors:
        fails.append(f"colors={len(colors)} (max {args.max_colors}): {', '.join(sorted(colors))}")

    paths = {e["id"]: points(e) for e in edges}
    ids = [i for i in paths if len(paths[i]) >= 2]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ends = [paths[a][0], paths[a][-1], paths[b][0], paths[b][-1]]
            for s in zip(paths[a], paths[a][1:]):
                for t in zip(paths[b], paths[b][1:]):
                    p = meet(s, t)
                    if p and not any(close(p, q) for q in ends):  # edges sharing a box may meet at it
                        fails.append(f"crossing: {a} x {b}")
                        break
                else:
                    continue
                break

    for eid in ids:
        pts = paths[eid]
        for n in nodes:
            box = bbox(n)
            if near(pts[0], box) or near(pts[-1], box):
                continue  # an endpoint box
            if any(through(s, box) for s in zip(pts, pts[1:])):
                fails.append(f"{eid} passes through {n['id']}")
        for t in texts:
            if t.get("containerId"):
                continue
            if any(through(s, text_box(t), pad=2) for s in zip(pts, pts[1:])):
                fails.append(f"{eid} runs through text {t['id']}. Move the text off the line.")

    for eid in ids:
        pts = paths[eid]
        curve = len(pts) > 2 and by_id[eid].get("roundness")
        crooked = False
        for (ax, ay), (bx, by) in [] if curve else zip(pts, pts[1:]):
            dx, dy = abs(bx - ax), abs(by - ay)
            skew = math.degrees(math.atan2(min(dx, dy), max(dx, dy)))
            if min(dx, dy) > 0.5 and skew < args.max_skew:
                axis = "vertical" if dy > dx else "horizontal"
                fails.append(f"{eid}: a segment is {skew:.1f} degrees off {axis}. Make it exact, or clearly diagonal.")
                crooked = True
                break
        a, b = (min((s for s in shapes if near(end, bbox(s))), key=area, default=None) for end in (pts[0], pts[-1]))
        if not a or not b:
            warns.append(f"{eid}: an end is not at a shape. Arrows should run box to box.")
        elif len(pts) == 2 and a is not b and not crooked:
            for k, axis in ((0, "vertical"), (1, "horizontal")):
                (alo, ahi), (blo, bhi) = band(a, k), band(b, k)
                if max(alo, blo) <= min(ahi, bhi) and apart(a, b, 1 - k) and abs(pts[0][k] - pts[1][k]) > 0.5:
                    fails.append(f"{eid}: {a['id']} and {b['id']} line up, so the arrow must be exactly {axis}.")

    for t in texts:
        if t.get("containerId"):
            continue
        tb = text_box(t)
        for n in nodes:
            if overlap(tb, bbox(n)):
                fails.append(f"text {t['id']} overlaps {n['id']}. Move it, or shorten the arrow's label.")

    for line in fails:
        print("FAIL ", line)
    for line in warns:
        print("WARN ", line)
    print(f"{'FAIL' if fails else 'PASS'}  nodes={len(nodes)} words={total} edges={len(edges)} "
          f"colors={len(colors)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
