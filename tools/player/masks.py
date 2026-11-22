"""Bake visible arcade actors to half-resolution horizontal spans on final video frames."""
import json
import struct
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "worlds/western/opening"
ASSETS = ROOT / "assets/western"
# Restrict extraction to the actor's side of the set. The store silhouette includes its bag.
BOXES = {"wagon": (436, 267, 568, 511), "barrels": (890, 309, 1020, 402),
         "window": (1120, 116, 1196, 245), "roof": (163, 205, 251, 286),
         "store": (432, 240, 556, 533)}
# Hand checked bounds at 320x180, including entry/exit beyond the movie edges.
CLERK = [(8,105,64,106,136),(12,105,61,120,140),(16,105,60,131,143),
         (20,103,60,139,144),(24,104,59,156,150),(28,111,55,178,164),
         (32,135,56,192,166),(36,148,53,214,170),(40,178,57,236,173),
         (44,193,56,262,174),(48,211,57,284,180),(52,248,53,312,180),
         (56,257,51,320,180),(60,299,50,320,180),(63,319,53,320,180)]


def silhouette(image, background, bounds):
    x,y,right,bottom = [int(v // 2) for v in bounds]
    a = image[y:bottom,x:right]
    b = background[y:bottom,x:right]
    if a.size == 0 or min(a.shape[:2]) < 3:
        return []
    delta = cv2.absdiff(cv2.GaussianBlur(a,(3,3),0), cv2.GaussianBlur(b,(3,3),0)).max(axis=2)
    mask = np.where(delta > 15, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype("uint8")
    mask[delta < 6] = cv2.GC_BGD
    mask[delta > 44] = cv2.GC_FGD
    if not np.any(mask == cv2.GC_FGD) or not np.any(mask == cv2.GC_BGD):
        return []
    cv2.grabCut(a.copy(),mask,None,np.zeros((1,65)),np.zeros((1,65)),2,cv2.GC_INIT_WITH_MASK)
    solid = cv2.morphologyEx(mask % 2,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    spans = []
    for dy,line in enumerate(solid):
        ends = np.flatnonzero(np.diff(np.pad(line,(1,1))))
        spans.extend((y+dy,x+lo,x+hi) for lo,hi in zip(ends[::2],ends[1::2]) if hi-lo>=2)
    return spans


def main():
    cv2.setRNGSeed(31)
    level=json.loads((DATA/"level.json").read_text(encoding="utf-8"))
    keys=np.array(CLERK)
    for name,node in level["clips"].items():
        beat=node.get("beat")
        civilian=node.get("civilian",False)
        if beat not in BOXES and not civilian:
            continue
        plate=cv2.imread(str(ASSETS/"kf"/(name[:2]+"_P.png")))
        plate=cv2.resize(plate[6:-6],(640,360),interpolation=cv2.INTER_AREA)
        cap=cv2.VideoCapture(str(ASSETS/"opening_slices"/(name+".mp4")))
        payload=bytearray(b"DCM1"+bytes.fromhex(node["sha256"])+struct.pack("<H",node["frames"]))
        for i in range(node["frames"]):
            ok,frame=cap.read()
            if not ok:
                raise ValueError((name,i))
            spans=[]
            if civilian and keys[0,0]<=i<=keys[-1,0]:
                bounds=[4*np.interp(i,keys[:,0],keys[:,col]) for col in range(1,5)]
            elif beat in BOXES and node["opens"]<=i<node.get("expires",node["frames"]):
                bounds=BOXES[beat]
            else:
                bounds=None
            if bounds:
                spans=silhouette(cv2.resize(frame,(640,360),interpolation=cv2.INTER_AREA),plate,bounds)
            payload.extend(struct.pack("<H",len(spans)))
            for span in spans:
                payload.extend(struct.pack("<3H",*span))
        cap.release()
        (DATA/(name+".mask")).write_bytes(payload)


if __name__=="__main__":
    main()
