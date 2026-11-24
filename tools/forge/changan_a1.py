"""Conform the authored market encounters from local H3 takes into 720p foregrounds."""

import argparse
from pathlib import Path
import struct
import subprocess
import tempfile

import cv2
import numpy as np

from changan_assets import spans
from changan_market import SIZE, decode, digest, info, write_json
from changan_once import encode_layer, foreground


# Position guides sampled from the original 1024x576 takes in 152x86 preview
# coordinates. They select the body for hit testing, independently of its light.
FRAMES = (16, 24, 32, 40, 48, 56, 64, 72, 80, 88)
GUIDES = {
    "swallow": [(11,30),(19,31),(30,32),(42,33),(53,36),(63,40),(78,42),(89,46),(90,48),(80,35)],
    "rabbit": [(103,76),(95,70),(91,72),(88,73),(85,73),(87,73),(90,73),(90,73),(94,73),(101,74)],
    "fish": [(99,42),(84,43),(72,44),(66,44),(71,44),(78,44),(80,43),(82,43),(88,44),(108,43)],
    "moth": [(8,5),(42,13),(57,17),(65,12),(69,16),(71,22),(70,22),(64,19),(59,18),(49,12)],
    "lotus": [(115,48),(111,47),(107,43),(103,38),(99,32),(97,29),(92,23),(87,17),(83,10),(78,4)],
    "civilian": [(31,51),(35,51),(40,51),(43,51),(45,51),(45,51),(45,51),(41,51),(36,51),(32,51)],
}
RADII = {"rabbit":(12,10),"fish":(26,12),"lotus":(19,15),"moth":(23,11),
         "swallow":(20,12),"civilian":(8,11)}
NAMES = {"swallow":"纸燕","rabbit":"玉兔灯","lotus":"莲灯","moth":"青绢蛾","fish":"小金鲤"}
ANCHORS = (28,42,56)
START, END = 22, 60


def body_mask(name, index, frame, clean):
    guide=np.asarray(GUIDES[name])
    x,y=[np.interp(index, FRAMES, axis) for axis in guide.T]
    h,w=frame.shape[:2]
    rx,ry=RADII[name]
    if name!="civilian":
        rx*=1.55
        ry*=1.5
    x0,x1=max(0,int((x-rx)*w/152)),min(w,int((x+rx)*w/152))
    y0,y1=max(0,int((y-ry)*h/86)),min(h,int((y+ry)*h/86))
    roi=np.s_[y0:y1,x0:x1]
    diff=cv2.absdiff(frame[roi],clean[roi]).max(axis=2)
    change=frame[roi].astype("int16")-clean[roi]
    shape=np.uint8(diff > 26) if name=="civilian" else np.uint8(
        (change.max(axis=2)>47) & (frame[roi].max(axis=2)>145))
    shape=cv2.morphologyEx(shape,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    contours,_=cv2.findContours(shape,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    result=np.zeros((h,w),np.uint8)
    if not contours:
        return result
    cx,cy=x*w/152-x0,y*h/86-y0
    def score(contour):
        distance=max(0,-cv2.pointPolygonTest(contour,(cx,cy),True))
        return cv2.contourArea(contour)/(1+distance/10)**2
    selected=max(contours,key=score)
    if cv2.contourArea(selected)>20:
        cv2.drawContours(result[roi],[selected],-1,255,-1)
    return result


def sound_source(src, dst, seconds):
    subprocess.run(["ffmpeg","-v","error","-nostdin","-y","-i",str(src),"-vn","-af",
                    f"atempo={seconds[0]/seconds[1]:.8f},apad","-t",str(seconds[1]),
                    "-ar","48000","-ac","2","-c:a","aac",str(dst)],check=True)


def render(work, media, world, name, anchor=None):
    base_id="a1_"+("civilian_crossing" if name=="civilian" else name)+"_01"
    job=base_id if anchor is None else f"{name}_at_{anchor}_purify_01"
    source=work/"takes"/job/"source.mp4"
    frames=decode(source)
    if anchor is not None:
        # End on the clean plate, leaving room for the next target's approach.
        indices=np.linspace(0,len(frames)-1,24).round().astype(int)
    else:
        indices=np.arange(len(frames))
    clip=name if anchor is None else f"{name}_purify_{anchor}"
    clean=frames[0] if anchor is None else frames[-1]
    big_clean=cv2.resize(clean,SIZE,interpolation=cv2.INTER_CUBIC).astype("float32")
    expanded=cv2.dilate(big_clean,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
    mask_rows=bytearray()
    def pictures():
        for i,fi in enumerate(indices):
            frame=frames[fi]
            image=cv2.resize(frame,SIZE,interpolation=cv2.INTER_CUBIC)
            layer=foreground(clip,i,image,big_clean,expanded)
            opacity=body_mask(name,fi if anchor is None else anchor,frame,clean)
            if anchor is not None:
                opacity *= np.uint8(i < 7)
            opacity=cv2.GaussianBlur(cv2.resize(opacity,SIZE),(5,5),0)
            weight=(opacity.astype("float32")/255)[:,:,None]
            layer[:,:,:3]=np.rint(image*weight+layer[:,:,:3]*(1-weight)).astype("uint8")
            layer[:,:,3]=np.rint(opacity+layer[:,:,3]*(1-weight[:,:,0])).astype("uint8")
            if anchor is None:
                active=START<=i<(83 if name=="civilian" else END)
                region=cv2.resize(opacity,(640,360),interpolation=cv2.INTER_AREA)>150
                rows=spans(np.uint8(region)) if active else []
                if active and not rows:
                    raise ValueError(f"Empty target in {clip} at {i}")
                mask_rows.extend(struct.pack("<H",len(rows)))
                for row in rows:
                    mask_rows.extend(struct.pack("<3H",*row))
            yield layer
    target=media/(clip+".mkv")
    with tempfile.TemporaryDirectory(dir=media) as temp:
        temp=Path(temp)
        audio=temp/"sound.m4a"
        sound_source(source,audio,(len(frames)/24,len(indices)/24))
        encode_layer(temp/target.name,audio,pictures())
        (temp/target.name).replace(target)
    sha=digest(target)
    if anchor is None:
        (world/(clip+".mask")).write_bytes(b"DCM1"+bytes.fromhex(sha)+struct.pack("<H",len(indices))+mask_rows)
    print(clip,len(indices),flush=True)
    return dict(frames=len(indices),sha256=sha), {**info(work,job),"final_sha256":sha}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("work",type=Path)
    ap.add_argument("output",type=Path)
    ap.add_argument("--passes",choices=["threat","response","both"],default="both")
    args=ap.parse_args()
    world=args.output/"worlds/changan/a1"
    media=args.output/"assets/changan/a1/once"
    world.mkdir(parents=True,exist_ok=True)
    media.mkdir(parents=True,exist_ok=True)
    cv2.setNumThreads(2)
    metadata={}
    ledger={}
    for name in GUIDES:
        anchors=[]
        if args.passes!="response":
            anchors.append(None)
        if args.passes!="threat" and name!="civilian":
            anchors.extend(ANCHORS)
        for anchor in anchors:
            key=name if anchor is None else f"{name}_purify_{anchor}"
            metadata[key],ledger[key]=render(args.work,media,world,name,anchor)
    write_json(world/(args.passes+"-clips.json"), metadata)
    write_json(world/(args.passes+"-media.json"), ledger)


if __name__=="__main__":
    main()
