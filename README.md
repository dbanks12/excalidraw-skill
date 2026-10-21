# excalidraw-skill

An agent skill for Claude Code and Codex. It draws diagrams that explain code, code changes, designs, and concepts on a live Excalidraw canvas. `SKILL.md` sets what to draw and how to compose it. `scripts/place.py` lays out boxes and arrows, and `scripts/lint_diagram.py` checks the result.

## How it works

![The agent reads SKILL.md, builds elements with place.py, draws them on the canvas server, then lints and renders the scene](docs/how-it-works.png)

The agent reads `SKILL.md` to decide what to draw. It chooses box positions on a grid and passes them to `place.py`. `place.py` sizes the boxes, routes the arrows, and prints Excalidraw elements as JSON. The agent pipes that JSON to the `mcp-excalidraw-server` CLI, which draws the elements on a local canvas server.

The agent then exports the scene and runs `lint_diagram.py`. The lint checks the box count, the words per label, the number of colors, and the aspect ratio. It also fails a crooked arrow. When two boxes line up across an arrow, the arrow must be exactly vertical or horizontal, and `place.py` draws it that way. Diagonals and curves pass. When the lint passes, the CLI renders the scene to a PNG without a browser. The agent views the PNG and critiques it against its brief.

![One drawing pass: write a brief, place shapes, lint, render, critique, and loop back on a lint failure or a fix](docs/drawing-pass.png)

Each drawing starts with a four-line brief: the reader, their question, the claim the picture must prove, and the diagram type. A lint failure or a failed critique sends the agent back to change the layout. The pass ends when the picture proves the claim in the brief.

Both diagrams on this page came from this skill.

## Install

Clone the repo and link it into your skills directory:

    git clone https://github.com/dbanks12/excalidraw-skill.git
    ln -s "$(pwd)/excalidraw-skill" ~/.claude/skills/excalidraw-skill
    ln -s "$(pwd)/excalidraw-skill" ~/.codex/skills/excalidraw-skill

The skill needs Node.js with `npx` and Python 3. It runs the canvas through the CLI of the `mcp-excalidraw-server` npm package, version 2.1.2 or later. The first canvas command starts a local server at `http://127.0.0.1:3000`. You do not need to register an MCP server. The skill can use the package's MCP tools if they are registered, but the CLI does the same work.

`place.py` and `lint_diagram.py` are plain Python and run without the package. Drawing, export, and rendering need the package.

## Attribution

This skill started from the `excalidraw-skill` that ships with [mcp-excalidraw-server](https://github.com/yctimlin/mcp_excalidraw) by yctimlin, under the MIT license. See `LICENSE`. The upstream skill teaches the canvas mechanics. It is kept word for word in `references/mechanics.md` and `references/cheatsheet.md`.

This repo adds the guidance on what to draw and how to check it. `SKILL.md` covers diagram choice, the brief, composition, and the lint, render, and critique loop. `place.py` and `lint_diagram.py` are new. `evals/evals.json` keeps one upstream eval and replaces the other four with six evals of diagram judgment.
