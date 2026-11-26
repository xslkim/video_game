"""Isolate the moving silk tassels on the sword casket and grade them a common pale jade."""

import json
import shutil

import cv2
import numpy as np

import linyuan_media as media
import linyuan_tune_video as tune


# Hand-rotoscoped on the first 1280x720 decoded frame. Include the folded far-side hanging silk.
OUTLINES = (
 "34,566 38,566 40,573 38,577 45,606 44,610 29,611 31,585 34,576",
 "58,565 62,565 63,571 59,575 64,607 62,610 50,610 51,592 55,578",
 "77,562 81,562 81,570 80,601 69,603 70,590 74,573",
 "95,558 99,558 99,563 98,568 100,594 86,594 87,582 93,565",
 "112,551 117,551 116,560 114,567 116,588 102,589 102,581 109,559",
 "128,550 132,550 132,558 132,585 120,584 123,573",
 "145,548 151,548 151,554 149,560 149,582 136,582 138,570",
 "164,547 169,547 168,555 167,579 165,582 152,582 153,576 162,553",
 "171,571 176,560 178,561 174,584 172,600 161,598 162,593",
)


def points():
    return [np.float32([[int(v) for v in xy.split(",")] for xy in row.split()]) for row in OUTLINES]


def color(picture,shapes):
    h,w=picture.shape[:2]
    mask=np.zeros((h,w),np.uint8)
    # The three tan silk panels share the surrounding casket hue and need their tracked contours.
    cv2.fillPoly(mask,[np.int32(np.round(shapes[i])) for i in (2,5,8)],255,lineType=cv2.LINE_AA)
    # Red and teal fibers have distinct chroma. Key those directly even when the free tip
    # blows far to the left of the traced first-frame outline.
    bw,bh=int(w*177/1280),int(h*622/720)
    dy,dx=np.ogrid[:bh,:bw]
    colors=cv2.cvtColor(picture[:bh,:bw],cv2.COLOR_BGR2HSV)
    hue,sat,val=cv2.split(colors)
    blue,green,_=cv2.split(picture[:bh,:bw].astype(np.int16))
    crimson=((hue<=1)|(hue>=165))&(blue>=green-2)&(sat>=85)&(val>=49)
    fringe=cv2.dilate(crimson.astype(np.uint8),np.ones((13,13),np.uint8)).astype(bool)
    crimson |= fringe&((hue<=8)|(hue>=161))&(sat>=86)&(val>=37)&(blue>=green-20)
    turquoise=(hue>=75)&(hue<=102)&(sat>=61)&(val>=37)
    silk=crimson|turquoise
    top=(566-(dx*1280/w-31)*.145)*h/720
    silk &= dy>top
    # A thin trace catches antialiased boundaries and yarn shadow at full source resolution.
    silk=cv2.morphologyEx(silk.astype(np.uint8)*255,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    contours,_=cv2.findContours(silk,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(silk,contours,-1,255,cv2.FILLED)
    n,labels,stats,_=cv2.connectedComponentsWithStats(silk)
    for label in range(1,n):
        if stats[label,cv2.CC_STAT_AREA]<8:
            silk[labels==label]=0
    mask[:bh,:bw]=np.maximum(mask[:bh,:bw],cv2.dilate(silk,np.ones((2,2),np.uint8)))
    x,y,bw,bh=cv2.boundingRect(mask)
    if not bw or not bh:
        raise ValueError("Empty tassel matte")
    roi=picture[y:y+bh,x:x+bw]
    matte=cv2.GaussianBlur(mask[y:y+bh,x:x+bw],(3,3),.55).astype(np.float32)/255
    hsv=cv2.cvtColor(roi,cv2.COLOR_BGR2HSV).astype(np.float32)
    strength=np.clip((hsv[:,:,2]-15)/33,.12,1)
    hsv[:,:,0]=84
    hsv[:,:,1]=np.clip(87-hsv[:,:,2]*.105,47,90)
    hsv[:,:,2]=np.minimum(246,hsv[:,:,2]*.87+68*strength)
    dye=cv2.cvtColor(np.uint8(hsv),cv2.COLOR_HSV2BGR)
    roi[:]=np.uint8(np.clip(roi*(1-matte[:,:,None])+dye*matte[:,:,None],0,255))
    return picture


def track(previous,current,shapes,flow_engine):
    x0,y0,x1,y1=0,480,230,655
    a=cv2.cvtColor(previous[y0:y1,x0:x1],cv2.COLOR_BGR2GRAY)
    b=cv2.cvtColor(current[y0:y1,x0:x1],cv2.COLOR_BGR2GRAY)
    flow=flow_engine.calc(a,b,None)
    result=[]
    for shape in shapes:
        local=shape.round().astype(int)-[x0,y0]
        shift=np.asarray([np.median(flow[max(0,y-1):y+2,max(0,x-1):x+2],axis=(0,1)) for x,y in local])
        result.append(shape+shift)
    return result


def main():
    slot="c1_04_noodle"
    dest=media.ART/"drama"/(slot+".mp4")
    original=tune.AUDIT/"c1_04_noodle_v11_before_silk.mp4"
    if not original.exists():
        shutil.copyfile(dest,original)
    raw=list(tune.read_frames(original))
    poses=points()
    engine=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    output=[]
    review=[]
    for n,frame in enumerate(raw):
        if n:
            poses=track(raw[n-1],frame,poses,engine)
        revised=color(frame.copy(),poses)
        output.append(revised)
        if n in (0,40,85,119):
            review.append(np.vstack([cv2.resize(im[494:625,:201],(280,183)) for im in (frame,revised)]))
    key=media.KEYS/"KF_C1_04_EIGHT.png"
    master=cv2.imread(str(key))
    h,w=master.shape[:2]
    original_720=cv2.resize(master,(1280,720),interpolation=cv2.INTER_AREA)
    # Transfer the matte from the first H3 frame to its original illustrated input.
    on_key=track(raw[0],original_720,points(),engine)
    on_key=[shape*np.float32([w/1280,h/720]) for shape in on_key]
    cv2.imwrite(str(media.KEYS/"KF_C1_04.png"),color(master,on_key))
    cv2.imwrite(str(tune.AUDIT/"tassels_before_after.jpg"),np.hstack(review))
    tune.selection(slot,output,{"silk_source_sha256":media.hash_file(original),
        "silk_keyframe_sha256":media.hash_file(media.KEYS/"KF_C1_04.png"),
        "editor_notes":"Eight sword hilts, individual guards. Pale jade silk isolated by rotoscope on all 120 source frames."})
    manifest=json.loads((media.PRODUCTION/"selections"/(slot+".json")).read_bytes())
    patch=media.PRODUCTION/"tuning_binding_patch.json"
    delta=json.loads(patch.read_bytes())
    delta["videos"][slot].update(sha256=manifest["sha256"],frames=manifest["frames"])
    media.write_json(patch,delta)
    print(manifest["sha256"])


if __name__=="__main__":
    main()
