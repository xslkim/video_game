"""Build a locally signed, offline Android release using the installed Windows SDK."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def launcher_art(poster, resource):
    resource.mkdir(parents=True)
    font = Path(os.environ["WINDIR"]) / "Fonts/msyh.ttc"
    with Image.open(poster) as still:
        for name, size, title, font_size in [
            ("lantern_banner", (320, 180), "长安灯妖录", 36),
            ("lantern_icon", (192, 192), "灯", 102),
        ]:
            image = ImageOps.fit(still.convert("RGB"), size, method=Image.Resampling.LANCZOS)
            ink = ImageDraw.Draw(image, "RGBA")
            ink.rectangle((0, 0, *size), fill=(10, 17, 25, 82))
            ink.text(
                (size[0] / 2, size[1] / 2),
                title,
                font=ImageFont.truetype(str(font), font_size),
                fill=(255, 228, 174),
                stroke_width=1,
                stroke_fill=(57, 36, 18),
                anchor="mm",
            )
            image.save(resource / (name + ".png"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assets", type=Path)
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    sdk = Path(os.environ.get("ANDROID_HOME", Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk"))
    java = Path(os.environ.get("JAVA_HOME", "C:/Program Files/Android/Android Studio/jbr")) / "bin"
    if not (java / "javac.exe").exists():
        java = Path("C:/Program Files/Android/Android Studio/jbr/bin")
    bt = sdk / "build-tools/36.0.0"
    platform = sdk / "platforms/android-36/android.jar"
    source = ROOT / "apps/changan_android"
    assets = args.assets.resolve()
    bundle = json.loads((assets / "bundle.json").read_bytes())
    members = {
        "bundle.json",
        "poster.jpg",
        *bundle["regions"].values(),
        *bundle["films"].values(),
        *bundle["audio"].values(),
    }
    for name, bank in bundle["banks"].items():
        for layer in bank["layers"].values():
            members.update(layer["pages"])
            members.add(layer["audio"])
        members.update(bank["street"]["pages"])
        members.update(
            "masks/" + name + "/" + key + ".mask"
            for key, clip in bank["level"]["clips"].items()
            if clip.get("windows")
        )
    for film in bundle.get("legacyFilms", {}).values():
        members.update(film["pages"])
        members.add(film["audio"])
    build = ROOT / "build/android-changan"
    build.mkdir(parents=True, exist_ok=True)
    store = Path.home() / ".android/debug.keystore"
    if not store.exists():
        store = build / "local-signing.keystore"
        if not store.exists():
            run(
                java / "keytool.exe",
                "-genkeypair",
                "-keystore",
                store,
                "-alias",
                "androiddebugkey",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "10000",
                "-storepass",
                "android",
                "-keypass",
                "android",
                "-dname",
                "CN=ChangAn Local Build",
            )
    args.apk.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build) as tmp:
        work = Path(tmp)
        if not (source / "node_modules/@babel/core").is_dir():
            run("npm.cmd", "ci", "--prefix", source, "--ignore-scripts", "--no-fund", "--no-audit")
        game_script = work / "player.js"
        run("node", source / "build_web.cjs", game_script)
        classes, dex = work / "classes", work / "dex"
        classes.mkdir()
        dex.mkdir()
        run(
            java / "javac.exe",
            "--release",
            "8",
            "-encoding",
            "UTF-8",
            "-classpath",
            platform,
            "-d",
            classes,
            *source.glob("*.java"),
        )
        run(
            java / "java.exe",
            "-cp",
            bt / "lib/d8.jar",
            "com.android.tools.r8.D8",
            "--min-api",
            "21",
            "--lib",
            platform,
            "--output",
            dex,
            *classes.rglob("*.class"),
        )
        unsigned, aligned = work / "unsigned.apk", work / "aligned.apk"
        launcher_art(assets / "poster.jpg", work / "res/drawable-xhdpi")
        compiled = work / "launcher.zip"
        run(bt / "aapt2.exe", "compile", "--dir", work / "res", "-o", compiled)
        run(
            bt / "aapt2.exe",
            "link",
            "-o",
            unsigned,
            "-I",
            platform,
            "--manifest",
            source / "AndroidManifest.xml",
            compiled,
        )
        with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as apk:
            apk.write(dex / "classes.dex", "classes.dex")
            for file in sorted((source / "web").iterdir()):
                if file.suffix != ".js":
                    apk.write(file, "assets/" + file.name)
            apk.write(game_script, "assets/player.js")
            for dependency, license_file in (("core-js", "LICENSE"), ("@babel/core", "LICENSE")):
                apk.write(source / "node_modules" / dependency / license_file,
                          "assets/licenses/" + dependency.replace("/", "-") + ".txt")
            for rel in sorted(members):
                compression = zipfile.ZIP_STORED if rel.endswith((".mp4", ".m4a")) else zipfile.ZIP_DEFLATED
                apk.write(assets / rel, "assets/" + rel, compress_type=compression)
        run(bt / "zipalign.exe", "-f", "4", unsigned, aligned)
        run(
            java / "java.exe",
            "-jar",
            bt / "lib/apksigner.jar",
            "sign",
            "--ks",
            store,
            "--ks-pass",
            "pass:android",
            "--key-pass",
            "pass:android",
            "--out",
            args.apk,
            aligned,
        )
        run(java / "java.exe", "-jar", bt / "lib/apksigner.jar", "verify", args.apk)
    with args.apk.open("rb") as stream:
        print(args.apk, hashlib.file_digest(stream, "sha256").hexdigest())


if __name__ == "__main__":
    main()
