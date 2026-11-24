"""Run the installed Android game on an identified device and record a full offline campaign."""

import argparse
import atexit
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile


PACKAGE = "com.changan.lanterns"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("serial")
    parser.add_argument("output", type=Path)
    parser.add_argument("--installed", action="store_true", help="Verify and play an already installed APK")
    parser.add_argument("--exercise-decoder-fallback", action="store_true",
                        help="Trigger a real WebView decoder error in the tower and finish from the same cue")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sdk = Path(os.environ.get("ANDROID_HOME", Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk"))
    adb = [str(sdk / "platform-tools/adb.exe"), "-s", args.serial]

    def call(*command):
        return (
            subprocess.check_output([*adb, *command], timeout=240).decode("utf8", errors="replace").strip()
        )

    def save(name, data):
        (args.output / name).write_text(data + "\n", encoding="utf8")

    with zipfile.ZipFile(args.apk) as package:
        chapters = json.loads(package.read("assets/bundle.json"))["campaign"]["chapters"]
    expected = [s["id"] for ch in chapters for s in ch["stages"]][1:] + ["@complete"]
    api = int(call("shell", "getprop", "ro.build.version.sdk"))
    if args.installed:
        package_path = call("shell", "pm", "path", PACKAGE).removeprefix("package:")
        remote = call("shell", "sha256sum", package_path).split()[0]
        with args.apk.open("rb") as src:
            if remote != hashlib.file_digest(src, "sha256").hexdigest():
                raise ValueError("Installed package SHA-256 differs from the release")
        save("install.txt", "Verified installed package " + remote)
    else:
        install = subprocess.run([*adb, "install", "--streaming" if api >= 24 else "--no-streaming",
                                  "-r", str(args.apk.resolve())], capture_output=True, timeout=300)
        save("install.txt", (install.stdout + install.stderr).decode("utf8", errors="replace").strip())
        install.check_returncode()
    call("shell", "am", "force-stop", PACKAGE)
    save(
        "start.txt",
        call("shell", "am", "start", "-W", "-n", PACKAGE + "/.GameActivity", "--es", "qa",
             "codec" if args.exercise_decoder_fallback else "full"),
    )
    def process_id():
        if api >= 24:
            return subprocess.run([*adb, "shell", "pidof", PACKAGE], capture_output=True, timeout=20).stdout.decode().strip()
        for row in call("shell", "ps").splitlines():
            fields = row.split()
            if fields and fields[-1] == PACKAGE:
                return fields[1]
        return ""
    for _ in range(24):
        pid = process_id()
        if pid.isdigit(): break
        time.sleep(0.25)
    if not pid.isdigit():
        raise RuntimeError("Game process did not start")
    # The Android 5 emulator can rotate its log buffer in less than a polling interval.
    # Keep one live reader so a completed checkpoint cannot disappear between samples.
    raw_path = args.output / "device-log.txt"
    raw = raw_path.open("wb")
    flags = ["-v", "epoch", "--pid", pid] if api >= 24 else ["-v", "threadtime"]
    tail = subprocess.Popen([*adb, "logcat", *flags, "-s", "ChanganGame:I"], stdout=raw)
    def close_log():
        if tail.poll() is None:
            tail.terminate()
        tail.wait(timeout=10)
        raw.close()
    atexit.register(close_log)
    call("shell", "dumpsys", "gfxinfo", PACKAGE, "reset")
    started = time.monotonic()
    samples = []
    milestones = set()
    entries = {}
    while time.monotonic() - started < 3300:
        if process_id() != pid:
            raise RuntimeError("Game exited during the campaign")
        output = raw_path.read_bytes().rpartition(b"\n")[0].decode("utf8", errors="replace")
        latest = output if api >= 24 else "\n".join(line for line in output.splitlines() if line.split()[2:3] == [pid])
        entries.update(dict.fromkeys(latest.splitlines()))
        log = "\n".join(entries)
        save("game.log", log)
        if "CHANGAN ERROR" in log:
            raise RuntimeError("Runtime error recorded in game.log")
        elapsed = round(time.monotonic() - started, 2)
        reached = re.findall(r"CHANGAN checkpoint (\S+)", log)
        if not samples or elapsed - samples[-1]["seconds"] >= 45:
            processes = call("shell", "ps", "-A", "-o", "PID,NAME") if api >= 24 else ""
            ids = [pid] + [
                line.split()[0] for line in processes.splitlines() if "webview:sandboxed_process" in line
            ]
            memory = {}
            for proc in ids:
                stats = call("shell", "dumpsys", "meminfo", proc)
                match = re.search(r"TOTAL PSS:\s*([\d,]+)", stats) or re.search(r"^\s*TOTAL\s+([\d,]+)", stats, re.M)
                if match:
                    memory[proc] = int(match[1].replace(",", ""))
            samples.append(
                dict(seconds=elapsed, pss_kib=memory, checkpoint=reached[-1] if reached else None)
            )
            save("memory.json", json.dumps(samples, indent=2))
        for chapter in chapters:
            if chapter["id"] not in milestones and any(s["id"] in reached for s in chapter["stages"]):
                milestones.add(chapter["id"])
                (args.output / (chapter["id"] + ".png")).write_bytes(
                    subprocess.check_output([*adb, "exec-out", "screencap", "-p"])
                )
        if "CHANGAN complete " in log:
            break
        time.sleep(8)
    else:
        raise TimeoutError("Android did not reach the ending")
    if reached != expected:
        raise RuntimeError("The recorded checkpoint order differs from the packaged story")
    if args.exercise_decoder_fallback and "firstFrame filmAtlas" not in log:
        raise RuntimeError("The offline-frame presentation path was not exercised")
    gfx = call("shell", "dumpsys", "gfxinfo", PACKAGE)
    save("gfxinfo.txt", gfx)
    (args.output / "ending.png").write_bytes(subprocess.check_output([*adb, "exec-out", "screencap", "-p"]))
    first = {}
    for kind in ("video", "atlas", "native", "filmAtlas"):
        times = sorted(map(int, re.findall(r"CHANGAN firstFrame " + kind + r" \S+ (\d+)", log)))
        if times:
            first[kind] = dict(
                count=len(times),
                p50_ms=times[math.ceil(len(times) * 0.5) - 1],
                p95_ms=times[math.ceil(len(times) * 0.95) - 1],
                max_ms=times[-1],
            )
    with args.apk.open("rb") as stream:
        summary = dict(
            apk_sha256=hashlib.file_digest(stream, "sha256").hexdigest(),
            serial=args.serial,
            model=call("shell", "getprop", "ro.product.model"),
            api=call("shell", "getprop", "ro.build.version.sdk"),
            resolution=call("shell", "wm", "size"),
            checkpoints=reached,
            seconds=elapsed,
            first_frame=first,
            sampled_peak_pss_kib=max(sum(s["pss_kib"].values()) for s in samples),
        )
    save("result.json", json.dumps(summary, indent=2))
    close_log()
    atexit.unregister(close_log)
    print(f"Completed {len(reached)} stages on {args.serial} in {elapsed}s")


if __name__ == "__main__":
    main()
