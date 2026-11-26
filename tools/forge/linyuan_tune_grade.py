"""Local photographic grade of production MPEGs. Reuses source coordinates and original picture timing."""

import json

import cv2
import numpy as np

import linyuan_media as media
import linyuan_tune_video as tune


# Centers picked on the decoded original. The first eye of the shrine fox is in profile.
SHRINE = np.array([
    [27,319,327,335,326],[33,318,331,336,330],[35,340,337,357,337],[37,354,341,373,340],
    [39,377,343,398,342],[41,402,344,425,344],[43,426,388,452,388],[45,457,393,487,391],
    [47,494,349,527,347],[49,541,334,577,333],[51,592,350,633,350],[53,640,395,686,394],
    [55,683,422,731,418],[57,715,434,771,429],[59,742,424,797,417],[61,763,401,818,395],
    [63,772,384,828,375],[65,779,361,837,354],[67,780,342,840,338],[69,780,328,843,324],
    [71,781,322,844,318],[73,782,317,844,313],[75,781,314,844,311],[79,781,313,842,310],
    [82,776,311,838,311],[85,776,311,838,311]])

STEPS = np.array([
    [10,902,187,918,186],[15,862,183,881,182],[20,839,249,859,247],[25,822,279,846,278],
    [30,813,304,839,303],[35,785,319,816,319],[40,742,248,790,252],[43,701,232,763,228],
    [45,660,262,734,259],[47,630,287,709,289],[50,588,296,683,295],[55,567,237,664,236],
    [59,565,222,662,218],[62,565,216,660,213],[65,565,219,660,219]])


def interpolate(coords,frame):
    return np.float32([np.interp(frame,coords[:,0],coords[:,k]) for k in range(1,5)]).reshape(2,2)


def eyes(image,points,scale):
    """Grade existing cyan/hostile pixels only, restricted to the selected eye sockets."""
    for i,(x,y) in enumerate(points):
        rx,ry = max(5,int(scale*(.78 if i else 1))),max(4,int(scale*.73))
        x0,x1 = max(0,int(x)-rx*2),min(image.shape[1],int(x)+rx*2+1)
        y0,y1 = max(0,int(y)-ry*2),min(image.shape[0],int(y)+ry*2+1)
        if x1<=x0 or y1<=y0:
            continue
        roi=image[y0:y1,x0:x1]
        gyy,gxx=np.ogrid[y0:y1,x0:x1]
        dist=((gxx-x)/rx)**2+((gyy-y)/ry)**2
        fade=np.float32(np.clip((1.75-dist)/.7,0,1))
        source=roi.astype(np.float32)
        b,g,r=cv2.split(source)
        cyan=np.clip((np.minimum(b,g)-r-5)/30,0,1)*np.clip((b-77)/68,0,1)
        red=np.clip((r-np.maximum(b,g)-18)/48,0,1)*np.clip((r-80)/70,0,1)
        alpha=cyan*fade
        peak=np.maximum(g,b)
        # Exchange the original emissive channels. Existing white-hot cores remain white,
        # and desaturated reflected light on nearby ceramic retains its original low chroma.
        tint=np.stack((.88*r+.04*peak,.93*r,np.minimum(255.,peak*1.07+5)),axis=-1)
        corrected=source*(1-alpha[...,None])+tint*alpha[...,None]
        strength=(red*fade)[...,None]
        corrected+=strength*np.array([-10,-15,27],np.float32)
        roi[:]=np.uint8(np.clip(corrected,0,255))


def matte(row):
    result=np.zeros((720,1280),np.uint8)
    if row:
        polys=row.get("rings",[row.get("polygon",[])])
        cv2.fillPoly(result,[np.int32(p) for p in polys if len(p)>2],255)
    return result


class Sun:
    def __init__(self):
        y,x=np.ogrid[:720,:1280]
        # Backlight crosses the stone stair and termination of the bamboo rope.
        self.field=np.float32(np.exp(-.5*(((x-961)/182)**2+((y-191)/129)**2)))
        self.field[:, :440]=0

    def grade(self,image,body,weak,rope=False):
        src=image.astype(np.float32)
        b,g,r=cv2.split(src)
        light=np.clip((np.maximum(r,g)-58)/106,0,1)
        warm=np.clip((np.minimum(g,r)-b+17)/57,.08,1)
        reserve=cv2.GaussianBlur(body,(7,7),1.2).astype(np.float32)/255
        correction=self.field*light*warm*(1-reserve)
        src*=1-correction[...,None]*np.array([.18,.28,.33],np.float32)
        # Amber canisters and natural rope retain their original material and silhouette.
        accent=(weak.astype(np.float32)/255)*np.clip((r-b+8)/95,.0,1.)
        src+=accent[...,None]*np.array([-7,7,19] if not rope else [-3,4,9],np.float32)
        return np.uint8(np.clip(src,0,255))


def next_points(prev,now,points):
    tracked,ok,_=cv2.calcOpticalFlowPyrLK(prev,now,points.reshape(-1,1,2),None,
        winSize=(21,21),maxLevel=3,criteria=(cv2.TERM_CRITERIA_COUNT|cv2.TERM_CRITERIA_EPS,16,.03))
    return np.where(ok.reshape(-1,1)>0,tracked.reshape(-1,2),points)


def run(groups=None):
    bindings=json.loads((media.PRODUCTION/"bindings.json").read_bytes())["videos"]
    sun=Sun()
    anchors_out={}
    for group,labels in (("c1_w_fox_shrine",("early","mid","late")),("c1_w_suanni_steps",("early","mid","late")),
                         ("c1_w_raft",("early","late"))):
        binding=bindings[group]
        if groups and group not in groups:
            continue
        bodies={r["frame"]:r for r in binding["regions"]}
        weak={r["frame"]:r for r in binding.get("weak_regions",binding["regions"])}
        anchors=[w[2] for w in binding["hit_windows"]]
        slots=[(group,None)]
        slots += [(f"c1_raft_drop_{a}" if group.endswith("raft") else f"{group}_kill_{label}",a)
                  for label,a in zip(labels,anchors)]
        for slot,at in slots:
            old=json.loads((tune.BASE/"selections"/(slot+".json")).read_bytes())
            raw=tune.BASE/(old["id"]+".mp4")
            scene=list(tune.read_frames(raw))
            coords=SHRINE if "shrine" in group else STEPS
            points=None if at is None else interpolate(coords,at)
            prevgray=None
            examples=[]
            for f,picture in enumerate(scene):
                original=picture.copy()
                key=f if at is None else at
                body=matte(bodies.get(key)) if at is None or f==0 else np.zeros((720,1280),np.uint8)
                accent=matte(weak.get(key)) if at is None or f==0 else np.zeros_like(body)
                if at is not None and f and group.endswith("steps"):
                    hsv=cv2.cvtColor(picture,cv2.COLOR_BGR2HSV)
                    # A retreat can move beyond its primary-shot masks. Protect only its bright fiery amber.
                    amber=cv2.inRange(hsv,(5,120,185),(25,255,255))
                    body=cv2.dilate(amber,np.ones((13,13),np.uint8))
                    accent=amber
                if "shrine" not in group:
                    picture=sun.grade(picture,body,accent,group.endswith("raft"))
                    if group.endswith("raft"):
                        # Existing red eyes in both distant statues. Leave everything except red emissive pixels alone.
                        hsv=cv2.cvtColor(original,cv2.COLOR_BGR2HSV)
                        red=((hsv[:,:,0]<6)|(hsv[:,:,0]>164))&(hsv[:,:,1]>97)&(hsv[:,:,2]>140)
                        red[:110]=False;red[550:]=False;red[:,:337]=False
                        values=picture[red].astype(np.int16)
                        picture[red]=np.uint8(np.clip(values+[-7,-12,24],0,255))
                if not group.endswith("raft"):
                    gray=cv2.cvtColor(original,cv2.COLOR_BGR2GRAY)
                    if at is None:
                        points=interpolate(coords,f)
                    elif prevgray is not None:
                        points=next_points(prevgray,gray,points)
                    span=np.linalg.norm(points[1]-points[0])
                    if coords[0,0]<=key<=coords[-1,0] and (at is None or f<12):
                        eyes(picture,points,scale=np.clip(span*(.58 if "shrine" in group else .36),6,39))
                    prevgray=gray
                if at is not None and f==0:
                    picture=anchors_out[(group,at)].copy()
                if at is None and f in anchors:
                    anchors_out[(group,f)]=picture.copy()
                scene[f]=picture
                if at is None and f in ([41,52,62,77] if "shrine" in group else [21,37,48,55]):
                    examples.append(np.hstack((cv2.resize(original,(390,219)),cv2.resize(picture,(390,219)))))
            if examples:
                cv2.imwrite(str(tune.AUDIT/(group+"_grade.jpg")),np.vstack(examples))
            dest=tune.selection(slot,scene,{"grade_source_sha256":old["sha256"],
                "editor_notes":"Photographic local grade on decoded original. Source camera, timing, and target coordinates retained."})
            if at is None:
                for lab,idx in zip(labels,anchors):
                    media.extract(group,lab,dest,idx)


if __name__=="__main__":
    import sys
    run(set(sys.argv[1:]))
