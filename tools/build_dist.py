# Build the files to give friends (in dist/, not committed; attach them to a GitHub release):
#   3centro-prism.zip       Prism Launcher instance that auto-updates from the pack on every launch (preferred)
#   3centro-<version>.mrpack  one-off snapshot for other launchers (no auto-update)
# Usage: python3 -I tools/build_dist.py
import json, os, subprocess, tomllib, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "pack")
DIST = os.path.join(ROOT, "dist")
PACKWIZ = os.environ.get("PACKWIZ", os.path.expanduser("~/go/bin/packwiz"))
PACK_URL = "https://raw.githubusercontent.com/jose-manuel-silva/3centro-modpack/main/pack/pack.toml"
BOOTSTRAP = "https://github.com/packwiz/packwiz-installer-bootstrap/releases/download/v0.0.3/packwiz-installer-bootstrap.jar"
UA = {"User-Agent": "3centro-pack/build_dist"}


def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()


pack = tomllib.load(open(os.path.join(PACK, "pack.toml"), "rb"))
mc, loader = pack["versions"]["minecraft"], pack["versions"]["fabric"]
os.makedirs(DIST, exist_ok=True)

mrpack = os.path.join(DIST, f"3centro-{pack['version']}.mrpack")
subprocess.run([PACKWIZ, "modrinth", "export", "-o", mrpack], cwd=PACK, check=True)

lwjgl = next(r for r in json.loads(fetch(f"https://meta.prismlauncher.org/v1/net.minecraft/{mc}.json"))["requires"] if r["uid"] == "org.lwjgl3")
lwjgl_v = lwjgl.get("suggests") or lwjgl.get("equals")
mmc_pack = {"formatVersion": 1, "components": [
    {"uid": "org.lwjgl3", "version": lwjgl_v, "dependencyOnly": True},
    {"uid": "net.minecraft", "version": mc, "important": True},
    {"uid": "net.fabricmc.intermediary", "version": mc, "dependencyOnly": True},
    {"uid": "net.fabricmc.fabric-loader", "version": loader},
]}
command = f'"$INST_JAVA" -jar packwiz-installer-bootstrap.jar {PACK_URL}'
instance_cfg = "\n".join([
    "[General]",
    "ConfigVersion=1.3",
    "InstanceType=OneSix",
    f"name={pack['name']}",
    "iconKey=default",
    "AutomaticJava=true",
    "OverrideCommands=true",
    "PreLaunchCommand=" + '"' + command.replace("\\", "\\\\").replace('"', '\\"') + '"',
    "",
])
prism = os.path.join(DIST, "3centro-prism.zip")
with zipfile.ZipFile(prism, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("instance.cfg", instance_cfg)
    z.writestr("mmc-pack.json", json.dumps(mmc_pack, indent=4))
    z.writestr("minecraft/packwiz-installer-bootstrap.jar", fetch(BOOTSTRAP))
print(f"{prism}\n{mrpack}")
