# Claude Code StatusLine

A collection of status lines for [Claude Code](https://claude.ai/code). Pick one, copy it into `~/.claude/`, and point `statusLine` in `~/.claude/settings.json` at it.

| Status line | Language | Highlights | Requires |
|---|---|---|---|
| [**Classic**](statuslines/classic/) | Bash, PowerShell | Token count and cost computed from the session transcript, git status | `jq`, `bc` (Bash) |
| [**Adaptive**](statuslines/adaptive/) | Python | Light/dark palettes, context bar, rate limits, wraps on narrow panes, uses Claude Code's built-in cost and context fields | Python 3, Nerd Font |

```
classic   ~/Dev/apeiros/data on develop? [Sonnet 4.5 | 7,599,934 ($3.22)]
adaptive   ~/proj   main ●2 ↑1 │ Opus 5.5 high │ ██░░░░ 41% 82k │  0.12 · 5m │ 5h 30%
```

## Layout

```
statuslines/
  <name>/
    README.md         install, features, customization
    statusline.<ext>  the script
```

## Migrating from the old layout

The scripts moved from the repo root into `statuslines/classic/`. If you installed by URL, update it:

```
…/main/statusline.sh   →  …/main/statuslines/classic/statusline.sh
…/main/statusline.ps1  →  …/main/statuslines/classic/statusline.ps1
```

Already-installed copies keep working, because they were copied locally.

## Contributing

New status lines are welcome. Add a folder under `statuslines/` with its own `README.md`, and add a row to the table above.

## License

MIT License - feel free to use and modify as needed.

## Author

Created with ❤️ by Lev Gelfenbuim for better Claude Code visibility and cost tracking.
