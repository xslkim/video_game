"""Assemble the long Zhuque Street encounter and its runtime assets."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import cv2
import numpy as np

from changan_a1 import ANCHORS, END, NAMES, START
from changan_market import SIZE, decode, digest, info, write_json

ROOT = Path(__file__).resolve().parents[2]
WORLD = Path("worlds/changan")
MEDIA = Path("assets/changan")
ROUTE = ["rabbit", "swallow", "fish", "moth", "lotus", "rabbit", "moth", "fish", "swallow"]


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def extend_street(work, destination):
    intro = decode(ROOT / MEDIA / "m0/once/street.mp4")
    breeze = decode(work / "takes/a1_awning_breeze_01/source.mp4")
    reference = breeze[0].astype(np.int16)
    mask = np.zeros(reference.shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.array([(0,119),(108,140),(185,178),(237,200),(210,223),(10,189),(0,193)]),
                        np.array([(722,193),(810,137),(957,55),(1023,60),(1023,162),(870,203),(754,235)])], 255)
    weight = cv2.GaussianBlur(mask,(0,0),5).astype("float32")[:,:,None] / 255
    tail = []
    for i, frame in enumerate(breeze):
        envelope = min(1., i/10, (len(breeze)-1-i)/10)
        difference = (frame.astype(np.int16)-reference)*weight*envelope
        delta = cv2.resize(difference,SIZE,interpolation=cv2.INTER_LINEAR)
        tail.append(np.uint8(np.clip(intro[-1]+delta,0,255)))
    total = 24*48
    cmd=["ffmpeg","-nostdin","-v","error","-y","-f","rawvideo","-s","1280x720","-pix_fmt","bgr24",
         "-r","24","-i","pipe:0","-f","lavfi","-i","anullsrc=r=48000:cl=stereo","-t","48",
         "-c:v","libx264","-bf","0","-g","24","-crf","17","-pix_fmt","yuv420p","-c:a","aac",
         "-threads","4","-movflags","+faststart",str(destination)]
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
        try:
            for i in range(total):
                if i < len(intro):
                    frame = intro[i]
                else:
                    offset = i-len(intro)
                    phase = offset%(len(tail)-1)
                    if (offset//(len(tail)-1))%2:
                        phase = len(tail)-1-phase
                    frame = tail[phase]
                    if total-i <= 12:
                        frame = cv2.addWeighted(frame,(total-i-1)/12,intro[-1],1-(total-i-1)/12,0)
                proc.stdin.write(memoryview(frame))
        finally:
            proc.stdin.close()
        if proc.wait():
            raise RuntimeError("Street encode failed")
    return total


def assemble(work, stage):
    world=stage/WORLD/"a1"
    media=stage/MEDIA/"a1/once"
    source=ROOT/WORLD/"m0"
    level=read(source/"level.json")
    ledger=read(source/"production/media.json")
    masks={}
    for clip, spec in level["clips"].items():
        if spec.get("impact_frame",-1) >= 0:
            spec["warning_frame"] = spec.get("start",0)
        shutil.copy2(ROOT/MEDIA/"m0/once"/(clip+".mkv"),media/(clip+".mkv"))
        if spec.get("windows"):
            shutil.copy2(source/(clip+".mask"),world/(clip+".mask"))
        for window in spec.get("windows",[]):
            window["node"] += len(ROUTE)
    bank={}
    for prefix in ["threat","response"]:
        bank.update(read(world/(prefix+"-clips.json")))
        ledger.update(read(world/(prefix+"-media.json")))
    base_nodes=level["nodes"]
    stage_ids=[f"wave_{i+1:02}_{name}" for i,name in enumerate(ROUTE)]
    next_ids=stage_ids[1:]+[level["first"]]
    level.update(title="长安灯妖录",location="朱雀大街  /  巡灯",first=stage_ids[0],
                 briefing="沿朱雀大街巡灯。看清灯妖，当心穿过街心的百姓。",cleared="长街灯静",
                 selectable_difficulty=True)
    level["nodes"]=[dict(id=k,label="净化"+NAMES[n],hp=1,score=100) for k,n in zip(stage_ids,ROUTE)]+base_nodes
    for i,(node,name,following) in enumerate(zip(stage_ids,ROUTE,next_ids)):
        windows=[]
        crossings = {3: "seller_crossing", 7: "seller_return"}
        destination = crossings.get(i, following)
        for anchor,begin,end in zip(ANCHORS,[START,35,49],[35,49,END]):
            action=f"{name}_purify_{anchor}"
            response=f"{node}_hit_{anchor}"
            windows.append(dict(begin=begin,end=end,kind="target",node=i,hit=response))
            level["clips"][response]=dict(**bank[action],media=action,in_anchor=f"{name}_at_{anchor}",
                                           out_anchor="street",next=destination)
        level["clips"][node]=dict(**bank[name],media=name,in_anchor="street",out_anchor="street",
                                  start=8,warning_frame=START,impact_frame=END,windows=windows,next=node)
        masks[node]=name
    for name, index, minimum in [("seller_crossing",4,"normal"),("seller_return",8,"hard")]:
        following = stage_ids[index]
        level["clips"][name]=dict(**bank["civilian"],media="civilian",in_anchor="street",
            out_anchor="street",next=following,minimum_difficulty=minimum,
            windows=[dict(begin=START,end=83,node=index,kind="civilian",hit=following)])
        masks[name]="civilian"
    for clip,sheet in masks.items():
        shutil.copy2(world/(sheet+".mask"),world/(clip+".mask"))
    with tempfile.TemporaryDirectory(dir=media) as tmp:
        staged=Path(tmp)/"street.mp4"
        count=extend_street(work,staged)
        staged.replace(media/"street.mp4")
    sha=digest(media/"street.mp4")
    level["street"]=dict(frames=count,sha256=sha)
    ledger["street"]={**info(work,"a1_awning_breeze_01"),"opening_take":ledger["street"],"final_sha256":sha}
    (world/"production").mkdir(exist_ok=True)
    write_json(world/"production/media.json",ledger)
    write_json(world/"level.json",level)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work",type=Path)
    parser.add_argument("stage",type=Path)
    args=parser.parse_args()
    assemble(args.work,args.stage)
