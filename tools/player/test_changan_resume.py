"""Interrupt a packaged offline campaign at an atomic checkpoint, then complete it."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile


def read(path):
    if os.name == "nt":
        # Let MoveFileEx replace a checkpoint while this monitor still has it open.
        import ctypes
        from ctypes import wintypes
        import msvcrt
        open_shared = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
        open_shared.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        open_shared.restype = wintypes.HANDLE
        handle = open_shared(str(path), 0x80000000, 7, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        with os.fdopen(msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY), "rb") as stream:
            return json.load(stream)
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--after", default="west_market_opens")
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    game = work / "game"
    with zipfile.ZipFile(args.archive) as archive:
        archive.extractall(game)
    evidence = work / "play"
    cmd = [str(game / "Changan.exe"), "--smoke", str(evidence)]
    unrelated = Path(os.environ.get("TEMP", work))
    with subprocess.Popen(cmd, cwd=unrelated) as first:
        checkpoint = evidence / "checkpoint.json"
        try:
            for _ in range(7200):
                if first.poll() is not None:
                    raise RuntimeError("Game exited before requested checkpoint")
                if checkpoint.exists():
                    try:
                        state = read(checkpoint)
                    except (FileNotFoundError, PermissionError):
                        time.sleep(0.05)
                        continue
                    if state["next"] == args.after:
                        break
                time.sleep(0.25)
            else:
                raise TimeoutError(args.after)
        finally:
            if first.poll() is None:
                first.terminate()
        first.wait()
    (work / "interrupted.json").write_text(json.dumps(state, indent=2), encoding="utf8")
    subprocess.run(cmd, cwd=unrelated, timeout=2700, check=True)
    timeline = read(evidence / "timeline.json")
    final = read(checkpoint)
    if timeline[0]["stage"] != state["next"] or final["next"] != "@complete" or len(final["scores"]) != 5:
        raise RuntimeError("Incorrect resume location or incomplete campaign")
    prior = timeline[0]["chapter"]
    for key, score in state["scores"].items():
        if key != prior and final["scores"][key] != score:
            raise RuntimeError("Completed chapter was counted twice")
    with args.archive.open("rb") as stream:
        result = dict(
            archive_sha256=hashlib.file_digest(stream, "sha256").hexdigest(),
            resumed=timeline[0]["stage"],
            stages_after_resume=len(timeline),
            final=final,
        )
    (work / "result.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print("Restored", result["resumed"], "and reached", final["next"])


if __name__ == "__main__":
    main()
