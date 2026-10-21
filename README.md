# excalidraw-skill

An agent skill for Claude Code and Codex. It draws diagrams that explain code, code changes, designs, and concepts on a live Excalidraw canvas. `SKILL.md` sets what to draw and how to compose it. `scripts/place.py` lays out boxes and arrows, and `scripts/lint_diagram.py` checks a diagram's word budget.

## Install

Clone the repo and link it into your skills directory:

    git clone https://github.com/dbanks12/excalidraw-skill.git
    ln -s "$(pwd)/excalidraw-skill" ~/.claude/skills/excalidraw-skill
    ln -s "$(pwd)/excalidraw-skill" ~/.codex/skills/excalidraw-skill

The skill needs Node.js with `npx`. It runs the canvas through `npx -y mcp-excalidraw-server@2.1.2` or later, which starts a canvas server at `http://127.0.0.1:3000`. The scripts need Python 3.

## Attribution

This skill started from the `excalidraw-skill` that ships with [mcp-excalidraw-server](https://github.com/yctimlin/mcp_excalidraw) by yctimlin, under the MIT license. `references/mechanics.md` and `references/cheatsheet.md` are upstream text. `evals/evals.json` extends the upstream evals. `SKILL.md` and `scripts/` are new. See `LICENSE`.
