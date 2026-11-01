# Compare the pack's server-side mods with the live server, and optionally stage them in /_new.
# Usage: python3 -I tools/server_sync.py           dry run: show what differs from the live /mods and /server.jar
#        python3 -I tools/server_sync.py --stage   also upload the full set to /_new/mods (+ /_new/server.jar if needed)
# Staging never touches the live server; switching is still the manual step in CLAUDE.md ("How to update", step 5).
# API key: $PTERO_KEY, or read from 1Password.
import glob, hashlib, io, json, os, subprocess, sys, tomllib, urllib.parse, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "pack")
CACHE = os.path.join(ROOT, "build", "server")
API = "https://panel.foxomy.com/api/client/servers/dd5be907"
OP_REF = "op://Personal/hom7xqst7aiyz3l5mlupvuyy2q/Panel/api key"
UA = "3centro-pack/server_sync"


def key():
    if os.environ.get("PTERO_KEY"):
        return os.environ["PTERO_KEY"]
    return subprocess.run(["op", "read", OP_REF], capture_output=True, text=True, check=True).stdout.strip()


KEY = None


def api(method, path, body=None):
    global KEY
    KEY = KEY or key()
    req = urllib.request.Request(API + path, json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json",
                                          "Content-Type": "application/json", "User-Agent": UA})
    data = urllib.request.urlopen(req).read()
    return json.loads(data) if data else None


def ls(directory):
    try:
        r = api("GET", "/files/list?directory=" + urllib.parse.quote(directory))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return {f["attributes"]["name"] for f in r["data"] if f["attributes"]["is_file"]}


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA})).read()


def upload(path, directory):
    url = api("GET", "/files/upload")["attributes"]["url"]
    subprocess.run(["curl", "-sSf", "-o", "/dev/null", "-F", f"files=@{path}",
                    url + "&directory=" + urllib.parse.quote(directory)], check=True)


def server_mods():
    out = {}
    for p in glob.glob(os.path.join(PACK, "mods", "*.pw.toml")):
        m = tomllib.load(open(p, "rb"))
        if m["side"] in ("server", "both"):
            out[m["filename"]] = m["download"]
    return out


def cached(name, dl):
    path = os.path.join(CACHE, "mods", name)
    if not os.path.exists(path) or hashlib.new(dl["hash-format"], open(path, "rb").read()).hexdigest() != dl["hash"]:
        data = fetch(dl["url"])
        if hashlib.new(dl["hash-format"], data).hexdigest() != dl["hash"]:
            sys.exit(f"hash mismatch for {name}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(data)
    return path


def jar_versions(data):
    props = zipfile.ZipFile(io.BytesIO(data)).read("install.properties").decode()
    kv = dict(l.split("=", 1) for l in props.splitlines() if "=" in l)
    return kv.get("game-version"), kv.get("fabric-loader-version")


def fabric_server_jar(mc, loader):
    installer = next(i["version"] for i in json.loads(fetch("https://meta.fabricmc.net/v2/versions/installer")) if i["stable"])
    path = os.path.join(CACHE, f"fabric-server-{mc}-{loader}-{installer}.jar")
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        open(path, "wb").write(fetch(f"https://meta.fabricmc.net/v2/versions/loader/{mc}/{loader}/{installer}/server/jar"))
    return path


def main():
    stage = "--stage" in sys.argv
    want = server_mods()
    live = ls("/mods") or set()
    live_jars = {n for n in live if n.endswith(".jar")}
    add, remove = sorted(set(want) - live_jars), sorted(live_jars - set(want))
    for n in add:
        print(f"+ {n}")
    for n in remove:
        print(f"- {n}")

    versions = tomllib.load(open(os.path.join(PACK, "pack.toml"), "rb"))["versions"]
    url = api("GET", "/files/download?file=%2Fserver.jar")["attributes"]["url"]
    live_v = jar_versions(fetch(url))
    want_v = (versions["minecraft"], versions["fabric"])
    jar_change = live_v != want_v
    if jar_change:
        print(f"server.jar: MC/loader {live_v} -> {want_v}")
    if not add and not remove and not jar_change:
        print("Live server already matches the pack.")
        return
    if not stage:
        print("\nDry run. Re-run with --stage to upload to /_new.")
        return

    paths = {n: cached(n, dl) for n, dl in want.items()}
    if ls("/_new") is None:
        api("POST", "/files/create-folder", {"root": "/", "name": "_new"})
    staged = ls("/_new/mods")
    if staged is None:
        api("POST", "/files/create-folder", {"root": "/_new", "name": "mods"})
        staged = set()
    stale = sorted(staged - set(want))
    if stale:
        api("POST", "/files/delete", {"root": "/_new/mods", "files": stale})
    for n, p in sorted(paths.items()):
        if n not in staged:
            print(f"uploading {n}")
            upload(p, "/_new/mods")
    if jar_change:
        jar = fabric_server_jar(*want_v)
        tmp = os.path.join(CACHE, "server.jar")
        open(tmp, "wb").write(open(jar, "rb").read())
        print("uploading server.jar")
        upload(tmp, "/_new")
    print("\nStaged in /_new (jars only: if live /mods has other files or folders, copy them over before switching).")
    print("Switch per CLAUDE.md step 5.")


main()
