# 3 centro modpack

[packwiz](https://packwiz.infra.link/) pack for the 3 centro Fabric server: Fabulously Optimized + extras on the client, the server mods, one source of truth.
Every mod in `pack/` has `side = client | server | both`.

## Playing (friends)

**Prism Launcher (auto-updates):** download `3centro-prism.zip` from the latest [release](../../releases), drag it into Prism, launch.
Every launch syncs the mods/configs to this repo first. Java 25 is picked automatically.

**Other launchers:** import the `.mrpack` from the release (a snapshot, re-import for updates).

## Maintaining

Needs `packwiz` (`go install github.com/packwiz/packwiz@latest`). Run the scripts from the repo root, packwiz commands inside `pack/`.

| Task | Command |
|---|---|
| Update your mods + server mods | `python3 -I tools/update.py` (flags alpha/beta builds), review `git diff`, commit, push |
| Follow a new Fabulously Optimized release | `python3 -I tools/fo_sync.py [version]` (FO's mods are pinned and move only here) |
| Add a mod | `packwiz modrinth add <slug>` (in `pack/`), then set `side` in its `.pw.toml`, `packwiz refresh` |
| GitHub-only mod | `packwiz github add owner/repo --regex '<asset regex>'` |
| Hold a mod back | `packwiz pin <name>` / `packwiz unpin <name>` |
| Change a shipped config | edit/copy it under `pack/config/`, `packwiz refresh` |
| New Minecraft version | `packwiz migrate minecraft <ver>` and `packwiz migrate loader latest`, then `tools/fo_sync.py`; fix the `mc26.3` regex in `mods/inventory-sorter.pw.toml` |
| Server: see what differs from live | `python3 -I tools/server_sync.py` |
| Server: stage the update in `/_new` | `python3 -I tools/server_sync.py --stage` (switch stays manual) |
| Friends' files | `python3 -I tools/build_dist.py`, then `gh release create <version> dist/*` |

Pushing to `main` updates every Prism player on their next launch, so push only what is ready.
Pushing does not touch the server; stage and switch it at the same time so client and server mods match.
`servers.dat` is `preserve = true` in the index: written on first install only.
