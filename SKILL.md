---
name: excalidraw-skill
description: Excalidraw diagrams that explain code, code changes, designs, and concepts, drawn on a live canvas. Use when an agent needs to (1) draw or lay out a diagram, (2) refine one by rendering and critiquing its own work, (3) export/import .excalidraw files or PNG/SVG images, (4) save/restore canvas snapshots, (5) convert Mermaid to Excalidraw, or (6) perform element-level CRUD, alignment, grouping, or locking. Drives the mcp-excalidraw-server CLI, which auto-starts the canvas server; MCP tools and a REST API are equivalent alternatives.
---

# Excalidraw diagrams

A diagram earns its place when a cold reader sees a mechanism faster than prose could tell it: where data flows, what a change adds or removes, which parts talk. Every step below serves one **claim**, the sentence the picture must prove.

Canvas mechanics (CLI, element format, arrows, snapshots, file I/O, errors) live in `references/mechanics.md`. Read it before the first canvas command in a session. Use `npx -y mcp-excalidraw-server@2.1.2` or later; screenshots and `render` work headless, with no browser tab.

## 1. Decide what to draw

Pick the type from the reader's question:

| Reader's question | Type |
|---|---|
| Where does this system sit? | Context: the system as one box, its neighbors around it |
| What are the parts and how do they talk? | Container or component boxes with labeled arrows |
| In what order do things happen across parts? | Sequence: one lane per actor, time runs down |
| Where does data go, and what boundaries does it cross? | Data flow with zones for trust or process boundaries |
| What did this change do? | Code change, one layout (see section 6) |
| Which of two designs? | Same layout twice, with the differing edge in the accent color |
| What states can this be in? | State machine |
| What should I do in my case? | Decision tree: questions as diamonds or boxes, answers on the arrows |

Then pick the scope:

- **One diagram** is the default. Most subjects fit in about 7 boxes: a state machine, a design comparison, a code change, a sequence, a decision tree, a small system. Keep it concise. Draw a dense, detailed diagram only when the user asks for one.
- **Overview, then deep dive** for a big subject: an architecture or system whose working detail needs more than about 7 boxes. These are two separate diagrams, each exported and rendered to its own file. The **overview** shows the whole idea in at most 7 boxes, readable in five seconds. The **deep dive** adds the parts, groups, and rules a person needs to work on it. Reuse the overview's names, colors, and relative positions, so the reader carries one map into the other.
- **A sentence instead** when the claim has no spatial relationship (a rename, a list, a one-line fix, a regex).

Done when: you named a type and a scope.

## 2. Write the brief

Write four lines before any canvas command, and show them to the user with the result:

```text
Reader:   reviewer of PR #412, knows the service, not this module
Question: what does the retry queue change about write ordering?
Claim:    writes now pass through RetryQueue, so a failed write retries after newer writes.
Type:     code change, one diagram
```

Read the code first. Use the names the code uses, and draw only parts that exist.

Done when: the claim is one sentence that names what the picture shows.

## 3. Compose the drawing

Every drawing has these parts:

- **A title** at the top left, fontSize 28: the subject and scope, such as "Order jobs: attempt lifecycle".
- **Color with meaning.** Color by kind, layer, or outcome: success green, failure red, waiting or external gray, the claim's subject in the accent. `place.py` takes the families gray, blue, green, orange, purple, red, and teal. Domain textures: `references/style-system.md` in the slide-deck skill, if it is installed. A drawing in one gray says nothing with color.
- **Short box labels.** A name of at most 4 words, plus an optional second line with a file path or type.
- **Labeled arrows** that say what moves or happens (`claims`, `error, timeout`, `emits OrderCreated`). Leave an arrow unlabeled only when the label adds nothing, such as a parent link in a commit graph.
- **At most one rules panel**, only when the reader needs detail that does not fit on a mark: invariants, timeouts, edge cases. Keep it to a few short lines. `place.py` draws it.
- **Dotted groups** for real boundaries (a process, a package, a trust zone), so the reader sees the high level and the parts at once.
- **A compact shape.** Aim for 4:3 to 16:9. Lint fails a drawing wider than 3:1. Wrap a long flow into two rows, or run it top-down.

Sizes: about 7 boxes in an overview or a small diagram, at most 15 in any diagram.

## 4. Place the shapes

Choose positions on a grid yourself, and let `scripts/place.py` build the elements. It sizes boxes to their labels, routes arrows between facing sides, spreads arrows that share a side, and puts each arrow label beside its line. Its header shows the full API.

```python
import sys; sys.path.insert(0, "<skill>/scripts")
from place import Diagram

d = Diagram("jobs", "Order jobs: attempt lifecycle")
d.start("s", -40, 122)
d.box("queued", 80, 100, "queued")
d.box("running", 340, 100, "running", fam="blue")
d.box("complete", 640, 0, "complete", fam="green")
d.box("failed", 640, 120, "failed", fam="red")
d.arrow("s", "queued", "enqueue")
d.arrow("queued", "running", "claim")
d.arrow("running", "complete", "ok")
d.arrow("running", "failed", "error, timeout")
d.panel("rules", 0, 300, "Rules", ["Retry is manual: a new attempt n+1"])
d.emit()
```

```bash
python3 jobs.py | timeout 120 npx -y mcp-excalidraw-server@2.1.2 add
```

Grid rules:

- Put the main path or the hub in the middle row, with the start at the left or top.
- Leave 80–120px between boxes, and 130px or more where an arrow carries a 3-word label.
- An arrow too short for its label puts the label on a box. Lint catches it. Widen the gap.
- `box(..., change="added")` takes the code-change palette in section 6. `fam` takes a color family.
- `zone()` draws a dotted boundary. Place it before its contents.
- `arrow(..., route="elbow")` turns one corner. `via=[(x, y)]` adds bend points around an obstacle.
- When two boxes overlap across an arrow, `place.py` makes the arrow exactly vertical or horizontal. It also lines up an arrow's end with its first or last `via` point. Lint fails any arrow that is almost straight but not exact.

By type:

- **Decision tree:** questions in `diamond()`, with straight edges and sharp corners. Outcomes in colored boxes. Join each parent to its children with `arrow(..., route="tree")`. All of a parent's tree arrows leave one point, meet a shared bar, and drop into each child, with rounded bends. Answers (`yes`, `SSD`) go beside each drop.
  - Grow the tree down when the rest of the page is wide, or right when it is tall or has many outcomes per question. `place.py` picks the direction from where you put the children.
  - Down: put each child row 120px or more below its parent. Spread the children so each sits clear of its siblings.
  - Right: put each child column 120px or more to the right of its parent, and stack the children.
- **State machine:** a `start()` dot, states left to right in the order a run visits them, outcomes colored by result. Draw a retry as a dashed arrow back, or as a separate "next attempt" state.
- **Sequence:** lanes 220px apart, lifelines as dashed `via` arrows or lines, one message every 60px, each label above its arrow.
- **Comparison:** the same positions in both options, with only the differing edges in the accent color.

Apply style-system textures after placement with `update <id> --set '{"fillStyle": "cross-hatch"}'`.

Done when: the drawing is on the canvas.

## 5. Lint, render, critique

1. Export the scene, then run `python3 <skill>/scripts/lint_diagram.py scene.excalidraw`. Fix every FAIL, then rerun. For an overview and deep dive, `clear` between them, and export, lint, and render each one on its own.
2. Render the exported file: `timeout 120 npx -y mcp-excalidraw-server@2.1.2 render scene.excalidraw --scale 2 --out view-N.png`. Use a new file name for each render, so you never view a stale image. View it.
3. Write the critique, three lines:
   - **Squint:** what the eye lands on first. It should be the claim's subject.
   - **Remove:** one box, arrow, or word that can go. Remove it, or say why it stays.
   - **Claim:** restate the claim from the picture alone. It should match the brief.
4. Check hygiene in the same image: no clipped or wrapped label, no overlap, no label on a line or arrowhead.

Fix, then repeat from step 1.

Done when: lint passes, and all three critique lines match the brief.

## 6. Code-change diagrams

Draw the change inside its unchanged neighbors, in one layout. Set `change` on nodes and edges:

| `change` | Look |
|---|---|
| `added` | green stroke, green fill |
| `changed` | amber stroke, amber fill |
| `removed` | red dashed stroke, no fill |
| `context` | gray stroke, no fill |

Put the file path in `sub` on changed nodes, or in the zone title when every node shares one file. Put the one-sentence claim in the title. Keep detail that exists only in the lines (a condition, an off-by-one, a regex) in the diff.

## Canvas gotchas

- **Own canvas:** set `PORT=<p> EXPRESS_SERVER_URL=http://127.0.0.1:<p>` on every command to run a private canvas. The default port 3000 is often the user's live canvas.
- **Glyphs:** the hand font lacks `→`, `≤`, `§`, `•`, and subscripts. These fall back to another font. Write `->`, `<=`, `-`, and `n1`.
- **Spaces:** free text loses leading spaces, so indented lines render flush left. Write each rule or bullet on one line.
- **Titles and labels:** lint treats text with id `<id>-label` as the label of element `<id>`. Name a zone or panel title `<id>-title`.
- **Arrows:** a bound arrow (`startElementId`/`endElementId`) ignores `points` and runs straight. Use an unbound arrow for a routed path.
- **Patches:** `apply` runs deletes after creates. Do not delete and recreate one id in a single patch.
- **Deletes:** deleting a shape leaves its bound arrows. Delete them too.
