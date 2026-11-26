"""Print candidate frame counts and build a same-time contact sheet for editorial decisions."""

import argparse

import cv2
from PIL import Image, ImageDraw

from linyuan_media import WORK, catalog


def compare(name, frames):
    candidates = sorted((WORK / "takes").glob(f"linyuan_{name}__v*/source.mp4"))
    if not candidates:
        raise FileNotFoundError(f"No completed H3 candidates for {name}")
    width, height = 208, 117
    sheet = Image.new("RGB", (width * len(frames), (height + 18) * len(candidates)))
    draw = ImageDraw.Draw(sheet)
    for row, path in enumerate(candidates):
        cap = cv2.VideoCapture(str(path))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(path.parent.name, count)
        for col, wanted in enumerate(frames):
            number = min(max(0, wanted if wanted >= 0 else count + wanted), count - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, number)
            ok, picture = cap.read()
            if not ok:
                raise ValueError(f"Missing {path}, frame {number}")
            img = Image.fromarray(cv2.cvtColor(picture, cv2.COLOR_BGR2RGB)).resize(
                (width, height)
            )
            corner = (width * col, (height + 18) * row)
            sheet.paste(img, corner)
            draw.text(
                (corner[0] + 4, corner[1] + height),
                f"{path.parent.name.split('__')[-1]} frame {number}",
            )
        cap.release()
    output = WORK / (name + "_compare.jpg")
    sheet.save(output, quality=91)
    print(output)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("ids", nargs="+", choices=catalog())
    cli.add_argument(
        "--frames", nargs="+", type=int, default=[0, 10, 22, 34, 46, 58, 72, -1]
    )
    args = cli.parse_args()
    for item in args.ids:
        compare(item, args.frames)
