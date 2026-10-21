#!/usr/bin/env python3
"""Hand-placement helper: you choose positions, it builds clean Excalidraw elements.

Write a small script that imports this file, place shapes on a grid, and print:

    import sys; sys.path.insert(0, "<skill>/scripts")
    from place import Diagram
    d = Diagram("jobs", "Standup jobs: task_attempt lifecycle")
    d.start("s", 0, 112)
    d.box("queued", 80, 100, "queued")
    d.box("running", 320, 100, "running", fam="blue")
    d.arrow("s", "queued", "enqueue")
    d.arrow("queued", "running", "claim")
    d.emit()        # JSON for: python3 jobs.py | npx -y mcp-excalidraw-server@2.1.2 add

Every id gets the diagram key as a prefix. Arrows are unbound polylines that end
6px off the box edge. Each arrow label is free text with id "<arrow id>-label",
placed beside the arrow's longest segment, so it never sits on the line.
"""
import json

FAM = {
    "gray": ("#495057", "#e9ecef"),
    "blue": ("#1971c2", "#e3f2fd"),
    "green": ("#2f9e44", "#d3f9d8"),
    "orange": ("#f08c00", "#fff9db"),
    "purple": ("#9c36b5", "#f3d9fa"),
    "red": ("#e03131", "#ffe3e3"),
    "teal": ("#0ca678", "#e6fcf5"),
    "ink": ("#1e1e1e", "transparent"),
}
CHANGE = {  # code-change palette: stroke, fill, strokeStyle
    "added": ("#2f9e44", "#d3f9d8", "solid"),
    "changed": ("#f08c00", "#fff9db", "solid"),
    "removed": ("#e03131", "transparent", "dashed"),
    "context": ("#868e96", "transparent", "solid"),
}
SQUARE = {"type": 3, "value": 0}  # an omitted roundness exports as rounded
CHAR = 0.52  # rendered hand-font width per character, per font-size unit
GAP = 6


def text_size(text, fs):
    lines = text.split("\n")
    return max(len(line) for line in lines) * CHAR * fs, len(lines) * 1.25 * fs


class Diagram:
    def __init__(self, key, title=None, x=0, y=0):
        self.key, self.els, self.shapes, self.arrows = key, [], {}, []
        self.ox, self.oy = x, y + (60 if title else 0)
        if title:
            self._text("title", x, y, title, 28)

    def id(self, name):
        return f"{self.key}-{name}"

    def _style(self, fam, change):
        if change:
            return CHANGE[change]
        stroke, fill = FAM[fam]
        return stroke, fill, "solid"

    def _text(self, name, x, y, text, fs, color="#1e1e1e"):
        w, h = text_size(text, fs)
        e = {"id": self.id(name), "type": "text", "x": x, "y": y, "width": w, "height": h, "text": text,
             "fontSize": fs, "strokeColor": color, "textAlign": "left", "verticalAlign": "top"}
        self.els.append(e)
        return e

    def box(self, name, x, y, label, sub=None, fam="gray", change=None, w=None, h=None, fs=18, shape="rectangle"):
        """A labeled box at (x, y), top left. Sized to its label unless w or h is given."""
        text = f"{label}\n{sub}" if sub else label
        tw, th = text_size(text, fs)
        pad = 2.0 if shape == "diamond" else 1.0  # a diamond's label needs twice the room
        w = w or max(120, round(tw * pad + 48))
        h = h or max(64, round(th * pad + 28))
        stroke, fill, dash = self._style(fam, change)
        e = {"id": self.id(name), "type": shape, "x": self.ox + x, "y": self.oy + y, "width": w, "height": h,
             "strokeColor": stroke, "backgroundColor": fill, "fillStyle": "solid", "strokeStyle": dash,
             "text": text, "fontSize": fs}
        if shape == "rectangle":
            e["roundness"] = SQUARE
        else:
            e["roughness"] = 0  # clean decision diamonds
        self.els.append(e)
        self.shapes[name] = e
        return e

    def diamond(self, name, x, y, question, fam="blue", **kw):
        """A decision. Keep the question short: the diamond doubles its size."""
        return self.box(name, x, y, question, fam=fam, shape="diamond", **kw)

    def start(self, name, x, y):
        """A filled start dot for a state machine."""
        e = {"id": self.id(name), "type": "ellipse", "x": self.ox + x, "y": self.oy + y, "width": 20, "height": 20,
             "strokeColor": "#1e1e1e", "backgroundColor": "#1e1e1e", "fillStyle": "solid"}
        self.els.append(e)
        self.shapes[name] = e
        return e

    def arrow(self, a, b, label=None, fam="ink", change=None, dashed=False, route="straight", via=None):
        """Arrow from shape a to shape b. Geometry is computed in emit().

        route="straight" joins facing sides, diagonally when the shapes are offset (trees).
        route="elbow" leaves sideways, then turns into b from above or below.
        via=[(x, y), ...] adds explicit bend points in diagram coordinates.
        Arrows that share a side of a box spread along it, ordered by where they go.
        """
        name = f"{a}--{b}"
        if any(r["name"] == name for r in self.arrows):
            name += f"--{len(self.arrows)}"
        self.arrows.append({"name": name, "a": a, "b": b, "label": label, "fam": fam, "change": change,
                            "dashed": dashed, "route": route,
                            "via": [(self.ox + x, self.oy + y) for x, y in via or []]})

    @staticmethod
    def _center(e):
        return e["x"] + e["width"] / 2, e["y"] + e["height"] / 2

    def _sides(self, r):
        """Which side of a, and of b, the arrow uses: 'l', 'r', 't' or 'b'."""
        s, t = self.shapes[r["a"]], self.shapes[r["b"]]
        (scx, scy), (tcx, tcy) = self._center(s), self._center(t)
        first = r["via"][0] if r["via"] else (tcx, tcy)
        last = r["via"][-1] if r["via"] else (scx, scy)

        def side(e, toward, horiz):
            cx, cy = self._center(e)
            return ("r" if toward[0] > cx else "l") if horiz else ("b" if toward[1] > cy else "t")

        def facing(e, p):  # the face that sees point p, scaled by the shape's own width and height
            cx, cy = self._center(e)
            return side(e, p, abs(p[0] - cx) / e["width"] >= abs(p[1] - cy) / e["height"])

        if r["via"]:
            return facing(s, first), facing(t, last)
        # Side by side (rows overlap) or mostly sideways: join the facing sides.
        # Otherwise join bottom to top, which draws trees with diagonal edges.
        rows_overlap = s["y"] < t["y"] + t["height"] and t["y"] < s["y"] + s["height"]
        horizontal = rows_overlap or abs(tcx - scx) > 2 * abs(tcy - scy)
        cols_overlap = s["x"] < t["x"] + t["width"] and t["x"] < s["x"] + s["width"]
        if r["route"] == "elbow" and not rows_overlap and not cols_overlap:
            return side(s, (tcx, tcy), horizontal), side(t, (scx, scy), not horizontal)
        return side(s, (tcx, tcy), horizontal), side(t, (scx, scy), horizontal)

    def _ports(self):
        """Spread the arrows on each side of each shape, ordered by the far end's position."""
        uses = {}
        for i, r in enumerate(self.arrows):
            sa, sb = self._sides(r)
            far_a = r["via"][0] if r["via"] else self._center(self.shapes[r["b"]])
            far_b = r["via"][-1] if r["via"] else self._center(self.shapes[r["a"]])
            uses.setdefault((r["a"], sa), []).append((i, 0, far_a))
            uses.setdefault((r["b"], sb), []).append((i, 1, far_b))
        ports = {}
        for (name, side), ends in uses.items():
            e = self.shapes[name]
            along_x = side in "tb"
            ends.sort(key=lambda u: u[2][0 if along_x else 1])
            for k, (i, end, _) in enumerate(ends):
                f = (k + 1) / (len(ends) + 1)
                if side == "l":
                    p = (e["x"] - GAP, e["y"] + f * e["height"])
                elif side == "r":
                    p = (e["x"] + e["width"] + GAP, e["y"] + f * e["height"])
                elif side == "t":
                    p = (e["x"] + f * e["width"], e["y"] - GAP)
                else:
                    p = (e["x"] + f * e["width"], e["y"] + e["height"] + GAP)
                if e["type"] == "diamond":  # a diamond only has its four corners to attach to
                    p = {"l": (e["x"] - GAP, e["y"] + e["height"] / 2),
                         "r": (e["x"] + e["width"] + GAP, e["y"] + e["height"] / 2),
                         "t": (e["x"] + e["width"] / 2, e["y"] - GAP),
                         "b": (e["x"] + e["width"] / 2, e["y"] + e["height"] + GAP)}[side]
                ports[(i, end)] = p
        return ports

    @staticmethod
    def _band(e, k):
        """Where an exactly vertical (k=0) or horizontal (k=1) arrow may meet shape e: 10px in from its corners.

        A diamond attaches only at its corners, so its band is the center line.
        """
        lo, size = e["xy"[k]], e["width" if k == 0 else "height"]
        if e["type"] == "diamond":
            return lo + size / 2, lo + size / 2
        return lo + 10, lo + size - 10

    def _snap(self, r, p0, p1):
        """Make a straight arrow exactly vertical or horizontal when its shapes overlap across it.

        The shared line runs through the narrower shape's port, clamped into both bands.
        """
        k = 0 if self._sides(r)[0] in "tb" else 1  # the coordinate both ends must share
        (slo, shi), (tlo, thi) = self._band(self.shapes[r["a"]], k), self._band(self.shapes[r["b"]], k)
        lo, hi = max(slo, tlo), min(shi, thi)
        if lo > hi:
            return p0, p1
        v = min(max((p0 if shi - slo <= thi - tlo else p1)[k], lo), hi)
        return tuple((v, p[1]) if k == 0 else (p[0], v) for p in (p0, p1))

    def _toward(self, name, side, p, q):
        """Slide end p along its side to line up with bend point q, when the shape allows it."""
        k = 0 if side in "tb" else 1
        lo, hi = self._band(self.shapes[name], k)
        return ((q[0], p[1]) if k == 0 else (p[0], q[1])) if lo <= q[k] <= hi else p

    def _arrows(self):
        ports = self._ports()
        for i, r in enumerate(self.arrows):
            p0, p1 = ports[(i, 0)], ports[(i, 1)]
            if r["via"]:
                sa, sb = self._sides(r)
                pts = [self._toward(r["a"], sa, p0, r["via"][0]), *r["via"], self._toward(r["b"], sb, p1, r["via"][-1])]
            elif (self._sides(r)[0] in "lr") != (self._sides(r)[1] in "lr"):  # elbow: one corner
                corner = (p1[0], p0[1]) if self._sides(r)[0] in "lr" else (p0[0], p1[1])
                pts = [p0, corner, p1]
            else:
                pts = list(self._snap(r, p0, p1))
            stroke, _, dash = self._style(r["fam"], r["change"])
            x0, y0 = pts[0]
            self.els.append({"id": self.id(r["name"]), "type": "arrow", "x": x0, "y": y0,
                             "points": [[px - x0, py - y0] for px, py in pts], "strokeColor": stroke,
                             "strokeStyle": "dashed" if r["dashed"] else dash,
                             "customData": {"from": self.id(r["a"]), "to": self.id(r["b"])}})
            if r["label"]:
                twins = [j for j, o in enumerate(self.arrows) if j != i and {o["a"], o["b"]} == {r["a"], r["b"]}]
                outside = any(ports[(j, 0)][1] + ports[(j, 1)][1] < p0[1] + p1[1] for j in twins)  # a twin runs above
                self._label(r["name"], pts, r["label"], stroke, below=outside)

    def _label(self, aid, pts, label, color, fs=16, below=False):
        (ax, ay), (bx, by) = max(zip(pts, pts[1:]), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
        w, h = text_size(label, fs)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        dx, dy = bx - ax, by - ay
        if abs(dx) >= abs(dy):  # mostly sideways: centered above the line where it runs highest under the label
            slope = abs(dy / dx) if dx else 0
            x, y = mx - w / 2, (my + slope * w / 2 + 6) if below else (my - slope * w / 2 - h - 6)
        else:  # mostly vertical: beside the line, clear of it across the label's height
            run = abs(dx / dy) * h / 2
            x = mx + run + 10 if dx * dy >= 0 else mx - run - w - 10
            y = my - h / 2
        self.els.append({"id": self.id(f"{aid}-label"), "type": "text", "x": x, "y": y, "width": w, "height": h,
                         "text": label, "fontSize": fs, "strokeColor": color, "textAlign": "left",
                         "verticalAlign": "top"})

    def zone(self, name, x, y, w, h, title, fam="gray"):
        """A dotted boundary with its title at the top left. Place it before its contents."""
        stroke = FAM[fam][0]
        self.els.append({"id": self.id(name), "type": "rectangle", "x": self.ox + x, "y": self.oy + y, "width": w,
                         "height": h, "strokeColor": stroke, "backgroundColor": "transparent",
                         "strokeStyle": "dotted", "roundness": SQUARE})
        self._text(f"{name}-title", self.ox + x + 14, self.oy + y + 10, title, 16, stroke)

    def panel(self, name, x, y, title, lines, w=None):
        """A dashed rules panel: a title and one short line per rule. Leading spaces are lost, so no indents."""
        body = "\n".join(f"- {line}" for line in lines)
        tw, th = text_size(body, 16)
        w = w or round(max(tw, text_size(title, 20)[0]) + 40)
        h = round(th + 70)
        self.els.append({"id": self.id(name), "type": "rectangle", "x": self.ox + x, "y": self.oy + y, "width": w,
                         "height": h, "strokeColor": "#868e96", "backgroundColor": "transparent",
                         "strokeStyle": "dashed", "roundness": SQUARE})
        self._text(f"{name}-title", self.ox + x + 20, self.oy + y + 14, title, 20)
        self._text(f"{name}-body", self.ox + x + 20, self.oy + y + 48, body, 16)

    def note(self, name, x, y, text, fam="ink", fs=16):
        return self._text(name, self.ox + x, self.oy + y, text, fs, FAM[fam][0])

    def emit(self):
        self._arrows()
        print(json.dumps(self.els, indent=1))
