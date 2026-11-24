"""Pack the original interactive H3 frames for devices with one video decoder."""

import hashlib
import json
import subprocess

import numpy as np
from PIL import Image


def atlas(source, out, foreground, film_fps=None):
    with source.open("rb") as src:
        digest = hashlib.file_digest(src, "sha256").hexdigest()[:24]
    prefix = (f"film{film_fps}-" if film_fps else "alpha-" if foreground else "street-") + digest
    meta = out / (prefix + ".json")
    if meta.is_file():
        return json.loads(meta.read_bytes())
    w, h = (480, 270) if foreground or film_fps else (640, 360)
    fps = film_fps or (24 if foreground else 12)
    timing = "select=not(mod(n\\,2))" if film_fps == 12 else "null" if film_fps else f"fps={fps}"
    mode = "RGBA" if foreground else "RGB"
    size = w * h * len(mode)
    ff = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-threads",
        "3",
        "-i",
        str(source),
        "-an",
        "-vf",
        f"{timing},scale={w}:{h}:flags=area",
        *(["-fps_mode", "passthrough"] if film_fps else []),
        "-threads",
        "2",
        "-f",
        "rawvideo",
        "-pix_fmt",
        mode.lower() if foreground else "rgb24",
        "pipe:1",
    ]
    description = dict(width=w, height=h, fps=fps, frames=0, pages=[])
    with subprocess.Popen(ff, stdout=subprocess.PIPE) as proc:
        while True:
            page = Image.new(mode, (w * 4, h * 3))
            count = 0
            for i in range(12):
                pixels = proc.stdout.read(size)
                if not pixels:
                    break
                if len(pixels) != size:
                    raise ValueError(f"Truncated frame in {source}")
                if foreground:
                    rgba = np.frombuffer(pixels, np.uint8).reshape(h, w, 4).copy()
                    a = rgba[:, :, 3:4].astype(np.uint16)
                    rgba[:, :, :3] = np.minimum(
                        255, rgba[:, :, :3].astype(np.uint16) * 255 // np.maximum(1, a)
                    )
                    tile = Image.fromarray(rgba)
                else:
                    tile = Image.frombytes(mode, (w, h), pixels)
                page.paste(tile, ((i % 4) * w, (i // 4) * h))
                count += 1
            if not count:
                break
            ext = ".webp" if foreground else ".jpg"
            file = out / (prefix + f"-{len(description['pages']):03d}" + ext)
            if foreground:
                page.save(file, quality=87, method=2)
            else:
                page.save(file, quality=78 if film_fps else 86, subsampling=2 if film_fps else 1)
            description["frames"] += count
            description["pages"].append("media/" + file.name)
        if proc.wait() or not description["frames"]:
            raise ValueError(f"Could not convert {source}")
    tmp = meta.with_suffix(".part.json")
    tmp.write_text(json.dumps(description), encoding="utf8")
    tmp.replace(meta)
    return description
