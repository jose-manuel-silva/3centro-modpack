# Sync the pack with a Fabulously Optimized release.
# Usage (from the repo root):  python3 -I tools/fo_sync.py [FO version number, default: newest for the pack's MC]
#
# FO-managed files are listed in tools/fo.json. They are pinned, so `packwiz update --all` leaves them alone
# and they only move here, to exactly the versions FO ships. Files the pack also needs on the server
# (see SHARED) are left to `packwiz update --all` instead.
# Override files (FO's default configs) are copied only if FO changed them since the previous synced
# release, so local config tweaks survive. Review everything with `git diff` before committing.
import hashlib, io, json, os, subprocess, sys, tomllib, urllib.parse, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "pack")
STATE = os.path.join(ROOT, "tools", "fo.json")
PACKWIZ = os.environ.get("PACKWIZ", os.path.expanduser("~/go/bin/packwiz"))
FO = "1KVo5zza"
# Modrinth project ids also used on the server: managed by `packwiz update`, not by FO.
SHARED = {"P7dR8mSH", "gvQqBUqZ", "uXXizFIs", "9s6osm5g"}  # fabric-api, lithium, ferrite-core, cloth-config
UA = {"User-Agent": "3centro-pack/fo_sync"}


def api(path, body=None):
    url = "https://api.modrinth.com/v2/" + path
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(UA, **({"Content-Type": "application/json"} if data else {}))
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data, headers)))


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()


def packwiz(*args):
    subprocess.run([PACKWIZ, "-y", *args], cwd=PACK, check=True)


def fo_version(mc, number):
    q = urllib.parse.urlencode({"game_versions": json.dumps([mc]), "loaders": json.dumps(["fabric"])})
    versions = api(f"project/{FO}/version?{q}")
    if number:
        versions = [v for v in versions if v["version_number"] == number]
    if not versions:
        sys.exit(f"no FO version {number or ''} for {mc}")
    return versions[0]


def mrpack(version):
    f = next(f for f in version["files"] if f["primary"]) if any(f["primary"] for f in version["files"]) else version["files"][0]
    return zipfile.ZipFile(io.BytesIO(fetch(f["url"])))


def pack_files():
    """Modrinth project id -> metafile path (relative to pack/)."""
    out = {}
    for d, _, fs in os.walk(PACK):
        for n in fs:
            if n.endswith(".pw.toml"):
                p = os.path.join(d, n)
                meta = tomllib.load(open(p, "rb"))
                mid = meta.get("update", {}).get("modrinth", {}).get("mod-id")
                if mid:
                    out[mid] = os.path.relpath(p, PACK)
    return out


def pin_client(rel):
    """Make a metafile client-only and pinned (what `packwiz pin` writes)."""
    p = os.path.join(PACK, rel)
    out = []
    for l in open(p).read().splitlines():
        if l.startswith("side = "):
            out += ['side = "client"', "pin = true"]
        elif not l.startswith("pin = "):
            out.append(l)
    open(p, "w").write("\n".join(out) + "\n")


def main():
    mc = tomllib.load(open(os.path.join(PACK, "pack.toml"), "rb"))["versions"]["minecraft"]
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"version": None, "projects": []}
    new = fo_version(mc, sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"FO {state['version']} -> {new['version_number']} ({new['id']})")
    z = mrpack(new)
    index = json.loads(z.read("modrinth.index.json"))
    if index["dependencies"].get("minecraft") != mc:
        sys.exit(f"FO {new['version_number']} is for {index['dependencies'].get('minecraft')}, pack is {mc}; run `packwiz migrate minecraft` first")

    by_sha1 = {f["hashes"]["sha1"]: f for f in index["files"]}
    known = api("version_files", {"hashes": list(by_sha1), "algorithm": "sha1"})
    missing = [f["path"] for h, f in by_sha1.items() if h not in known]
    if missing:
        sys.exit(f"not on Modrinth, add by hand: {missing}")

    have = pack_files()
    fo_projects = {}
    for h, v in known.items():
        fo_projects[v["project_id"]] = v["id"]
    for pid, vid in sorted(fo_projects.items()):
        if pid in SHARED and pid in have:
            continue
        if pid in have:
            meta = tomllib.load(open(os.path.join(PACK, have[pid]), "rb"))
            if meta["update"]["modrinth"]["version"] == vid:
                continue
            if pid not in state["projects"]:
                print(f"  skip {have[pid]}: not FO-managed (pack has its own version)")
                continue
            os.remove(os.path.join(PACK, have[pid]))
        packwiz("modrinth", "add", "--project-id", pid, "--version-id", vid)
        have = pack_files()
        rel = have[pid]
        if pid not in SHARED:
            pin_client(rel)
        print(f"  {rel} -> {vid}")

    for pid in state["projects"]:
        if pid not in fo_projects and pid in have:
            print(f"  FO dropped {have[pid]}; removing")
            os.remove(os.path.join(PACK, have[pid]))

    # Overrides FO changed since the last synced release.
    old = {}
    if state["version"]:
        oz = mrpack(api(f"version/{state['version']}"))
        old = {n: oz.read(n) for n in oz.namelist() if n.startswith("overrides/") and not n.endswith("/")}
    for n in z.namelist():
        if not n.startswith("overrides/") or n.endswith("/"):
            continue
        data, rel = z.read(n), n[len("overrides/"):]
        dest = os.path.join(PACK, rel)
        if old.get(n) == data or (os.path.exists(dest) and open(dest, "rb").read() == data):
            continue
        if not state["version"] and os.path.exists(dest):
            continue  # first sync: keep the configs already in the pack
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(data)
        print(f"  override {rel}")

    packwiz("refresh")
    json.dump({"version": new["id"], "version_number": new["version_number"],
               "projects": sorted(p for p in fo_projects if p not in SHARED)}, open(STATE, "w"), indent=1)
    print("done; review with `git diff`")


main()
