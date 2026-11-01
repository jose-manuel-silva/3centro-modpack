# Update every unpinned mod (your extras + server mods; FO's mods are pinned, see fo_sync.py)
# and report what changed, flagging alpha/beta builds. Usage: python3 -I tools/update.py
# Then review `git diff`; to undo one mod: `git checkout pack/mods/<mod>.pw.toml && packwiz refresh` (in pack/).
import glob, json, os, subprocess, tomllib, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "pack")
PACKWIZ = os.environ.get("PACKWIZ", os.path.expanduser("~/go/bin/packwiz"))


def snapshot():
    out = {}
    for p in glob.glob(os.path.join(PACK, "*", "*.pw.toml")):
        m = tomllib.load(open(p, "rb"))
        out[os.path.relpath(p, PACK)] = m
    return out


before = snapshot()
subprocess.run([PACKWIZ, "-y", "update", "--all"], cwd=PACK, check=True)
after = snapshot()

changed = [p for p in sorted(after) if p not in before or after[p]["filename"] != before[p]["filename"]]
if not changed:
    print("\nEverything is up to date.")
for p in changed:
    m = after[p]
    note = ""
    mr = m.get("update", {}).get("modrinth")
    if mr:
        req = urllib.request.Request(f"https://api.modrinth.com/v2/version/{mr['version']}", headers={"User-Agent": "3centro-pack"})
        vt = json.load(urllib.request.urlopen(req))["version_type"]
        if vt != "release":
            note = f"  <-- {vt.upper()}"
    old = before.get(p, {}).get("filename", "(new)")
    print(f"{p} [{m['side']}]: {old} -> {m['filename']}{note}")
if any(after[p]["side"] in ("server", "both") for p in changed):
    print("\nServer mods changed: stage them with `python3 -I tools/server_sync.py --stage` when ready.")
