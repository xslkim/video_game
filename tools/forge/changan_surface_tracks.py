"""Refine small moving surfaces that optical flow loses on paper, silk and emissive fire."""

import cv2
import numpy as np


def outline(contour, points=36):
    path = contour[:, 0, :].astype(float)
    path = np.vstack([path, path[0]])
    distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    t = np.arange(points) / points * distance[-1]
    return np.c_[np.interp(t, distance, path[:, 0]), np.interp(t, distance, path[:, 1])]


def refined(frame, number, rule):
    # Annotations use the contact-sheet coordinate system. Work at double that
    # resolution to keep small moving wicks and thin edges distinguishable.
    small = cv2.resize(frame, (448, 252), interpolation=cv2.INTER_AREA)
    marks = np.array(rule["marks"], dtype=float)
    cx, cy = [2 * np.interp(number, marks[:, 0], axis) for axis in marks[:, 1:].T]
    width, height = np.array(rule["radius"]) * 2
    kind = rule["kind"]
    if kind == "surface":
        angles = np.arange(24) * (2 * np.pi / 24)
        shape = np.c_[cx + width * np.cos(angles), cy + height * np.sin(angles)]
    else:
        rx, ry = np.array(rule["search"]) * 2
        x0, x1 = max(0, int(cx - rx)), min(448, int(cx + rx + 1))
        y0, y1 = max(0, int(cy - ry)), min(252, int(cy + ry + 1))
        tile = small[y0:y1, x0:x1].astype(np.int16)
        b, g, r = cv2.split(tile)
        if kind == "paper":
            mask = np.maximum.reduce([b, g, r]) > max(
                43, min(110, np.percentile(tile.max(axis=2), 86) * 0.56)
            )
        elif kind == "canopy":
            mask = (r > 72) & (r > b * 1.22) & (r > g * 1.08)
        else:
            mask = (b > 105) & (g > 72) & (b > r * 1.10) & (g > r * 0.99)
        binary = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = [c for c in contours if cv2.contourArea(c) >= 4]
        if candidates:

            def quality(c):
                x, y, w, h = cv2.boundingRect(c)
                dist = ((x0 + x + w / 2 - cx) / rx) ** 2 + ((y0 + y + h / 2 - cy) / ry) ** 2
                return cv2.contourArea(c) / (1 + 10 * dist)

            best = max(candidates, key=quality)
            if kind in {"paper", "canopy"}:
                # Paper wings can fold into separate bright panels around the dark crease.
                if kind == "paper":
                    chosen = [c for c in candidates if cv2.contourArea(c) > 0.07 * cv2.contourArea(best)]
                    best = cv2.convexHull(np.vstack(chosen))
                else:
                    best = cv2.convexHull(best)
                return np.rint((outline(best) + [x0, y0]) * 1280 / 448).astype(int).tolist()
            moment = cv2.moments(best)
            cx, cy = x0 + moment["m10"] / moment["m00"], y0 + moment["m01"] / moment["m00"]
            _, _, w, h = cv2.boundingRect(best)
            width, height = max(width, w * 0.46), max(height, h * 0.45)
        angles = np.arange(36) * (2 * np.pi / 36)
        shape = np.c_[cx + width * np.cos(angles), cy + height * np.sin(angles)]
    return np.rint(shape * 1280 / 448).astype(int).tolist()
