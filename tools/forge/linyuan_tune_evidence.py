"""Inspect and measure the actual decoded release MPEGs for the targeted art revision."""

import json
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np

import linyuan_media as media
import linyuan_tune_grade as grade
import linyuan_tune_video as tune


OUT = media.PRODUCTION / "tuning_review"


def tile(image,width,height,label):
    photo = cv2.resize(image,(width,height),interpolation=cv2.INTER_AREA)
    cv2.rectangle(photo,(0,0),(min(width,len(label)*8+12),19),(20,20,20),-1)
    cv2.putText(photo,label,(4,14),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1,cv2.LINE_AA)
    return photo


def save(name,picture):
    cv2.imwrite(str(OUT/name),picture,[cv2.IMWRITE_JPEG_QUALITY,90])


def decoded(name,drama=False):
    return list(tune.read_frames(media.ART/("drama" if drama else "bamboo")/(name+".mp4")))


def error(a,b):
    return round(float(np.abs(a.astype(np.int16)-b).mean()),3)


def static_shift(reference,picture):
    # Same 1280x720 geometry in all clips. Both ROIs are outside the left-foreground flight path.
    answer=[]
    for x,y,w,h in ((920,182,185,112),(850,533,275,101)):
        gray_a=cv2.cvtColor(reference[y:y+h,x:x+w],cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray_b=cv2.cvtColor(picture[y:y+h,x:x+w],cv2.COLOR_BGR2GRAY).astype(np.float32)
        shift,confidence=cv2.phaseCorrelate(gray_a,gray_b,cv2.createHanningWindow((w,h),cv2.CV_32F))
        answer.append(np.round([*shift,confidence],4).tolist())
    return answer


def grove_proof(report):
    fox=decoded("c1_w_fox_grove")
    rows=[np.hstack([tile(fox[i],208,117,f"approach {i}") for i in (0,6,13,24,36,62)])]
    shifts=[]
    for i in range(40):
        shifts.append(static_shift(fox[0],fox[i]))
    handoffs=[]
    for anchor in (13,24,36):
        response=decoded("c1_w_fox_grove_kill_"+str(anchor))
        rows.append(np.hstack([tile(p,208,117,t) for p,t in (
            (fox[anchor],f"anchor {anchor}"),(response[0],"entry 0"),(response[3],"recoil 3"),
            (response[9],"retreat 9"),(response[15],"retreat 15"),(response[-1],"clear 21"))]))
        handoffs.append({"anchor":anchor,"duration_frames":len(response),
            "decoded_entry_vs_parent_rgb_mae_8bit":error(fox[anchor],response[0]),
            "decoded_exit_vs_empty_rgb_mae_8bit":error(fox[0],response[-1])})
        shifts.extend(static_shift(fox[0],p) for p in response)
    shifts=np.asarray(shifts)
    report["grove"]={"handoffs":handoffs,"registration_coverage":"full open window and every frame of all three branches",
        "static_roi_xywh":[[920,182,185,112],[850,533,275,101]],
        "phase_correlation_max_abs_dx_dy_px":np.round(np.max(np.abs(shifts[:,:,:2]),axis=0),4).tolist(),
        "phase_correlation_median_abs_dx_dy_px":np.round(np.median(np.abs(shifts[:,:,:2]),axis=0),4).tolist()}
    save("grove_anchors.jpg",np.vstack(rows))


def story_proof(report):
    entry=decoded("c1_10_talon",True)[84]
    rows=[]
    outcomes={}
    for i in ("hit","miss"):
        scene=decoded("c1_11_"+i,True)
        rows.append(np.hstack([tile(scene[n],240,135,i+" "+str(n)) for n in (0,12,29,46,71)]))
        outcomes[i]=scene[-1]
        report.setdefault("story",{}).setdefault("decoded_entry_vs_hover_mae",{})[i]=error(entry,scene[0])
    save("rescue_outcomes.jpg",np.vstack(rows))
    report["story"]["common_landing_decoded_crossbranch_mae"]=error(outcomes["hit"],outcomes["miss"])
    geometry=json.loads((media.PRODUCTION/"tuning_talon_geometry.json").read_bytes())
    report["story"]["visible_glass_area_px_source72_to95"]=[
        round(cv2.contourArea(np.int32(row["polygon"]))) for row in geometry["regions"]["sac"]]
    shutil.copyfile(tune.AUDIT/"talon_regions_review.jpg",OUT/"talon_regions.jpg")
    shots=decoded("c1_04_noodle",True)
    rows=[tile(shots[0],840,472,"noodle stall, full frame")]
    details=[tile(shots[n][455:660,:230],210,186,f"source {n}") for n in (0,36,78,119)]
    rows.append(np.hstack(details))
    save("noodle_casket.jpg",np.vstack(rows))
    shutil.copyfile(tune.AUDIT/"tassels_before_after.jpg",OUT/"tassels_grade.jpg")


def grade_proof(report):
    rows=[]
    measurements={}
    for name,frames,curve in (("c1_w_fox_shrine",[27,41,52,62,75],grade.SHRINE),
                               ("c1_w_suanni_steps",[35,40,45,50,58],grade.STEPS)):
        before=list(tune.read_frames(tune.BASE/(name+".mp4")))
        after=decoded(name)
        line=[]
        sample=[]
        for f in frames:
            points=grade.interpolate(curve,f)
            x,y=points.mean(axis=0).astype(int)
            radius=int(max(42,np.linalg.norm(points[1]-points[0])+25))
            x0,y0=np.round(points[0]).astype(int)
            sample.append({"frame":f,"eye_center_xy":[int(x0),int(y0)],
                           "rgb_before":before[f][y0,x0,::-1].tolist(),"rgb_after":after[f][y0,x0,::-1].tolist()})
            line.append(np.vstack([tile(frame[y-2*radius//3:y+2*radius//3,x-radius:x+radius],193,120,st+" "+str(f))
                                   for st,frame in (("before",before[f]),("after",after[f]))]))
        rows.append(np.hstack(line))
        measurements[name]=sample
    report["eye_samples"]=measurements
    save("hostile_eyes.jpg",np.vstack(rows))
    rows=[]
    for name,f in (("c1_w_suanni_steps",25),("c1_w_raft",28)):
        before=list(tune.read_frames(tune.BASE/(name+".mp4")))[f]
        after=decoded(name)[f]
        rows.append(np.hstack([tile(i[63:377,652:1240],460,245,t) for i,t in ((before,"before "+name),(after,"after "+name))]))
        report.setdefault("beam_luma_samples",{})[name]={
            "frame":f,"roi_xywh":[961,104,61,62],
            "before":round(float(cv2.cvtColor(before[104:166,961:1022],cv2.COLOR_BGR2GRAY).mean()),2),
            "after":round(float(cv2.cvtColor(after[104:166,961:1022],cv2.COLOR_BGR2GRAY).mean()),2)}
    save("daylight_source_positions.jpg",np.vstack(rows))


def main():
    OUT.mkdir(exist_ok=True)
    patch=json.loads((media.PRODUCTION/"tuning_binding_patch.json").read_bytes())
    report={"production":"ImageGen keyframes, local H3 render and localized image finishing",
            "human_review":"not performed","videos":{}}
    for name,record in patch["videos"].items():
        path=media.ROOT/record["file"]
        ff=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-of","json",str(path)]))
        video=next(s for s in ff["streams"] if s["codec_type"]=="video")
        audio=next(s for s in ff["streams"] if s["codec_type"]=="audio")
        assert media.hash_file(path)==record["sha256"] and int(video["nb_frames"])==record["frames"],name
        assert (video["codec_name"],video["width"],video["height"],video["r_frame_rate"],video["has_b_frames"])==(
            "h264",1280,720,"24/1",0),name
        assert (audio["codec_name"],audio["channels"],audio["sample_rate"])==("aac",2,"48000"),name
        report["videos"][name]={"sha256":record["sha256"],"frames":record["frames"]}
    grove_proof(report)
    story_proof(report)
    grade_proof(report)
    report["release_streams"]="H.264 1280x720 24 fps, no B frames; AAC stereo 48 kHz"
    media.write_json(media.PRODUCTION/"tuning_media_review.json",report)


if __name__=="__main__":
    main()
