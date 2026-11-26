"""Track the visible fuel glass and Yunyi's hand-traced silhouette in the selected rescue take."""

import cv2
import numpy as np

import linyuan_tune_video as tune
import linyuan_media as media


# Source frame 72 in 1280 x 720 source space, clockwise from the top of the head.
SILHOUETTE = """
604,250 626,246 643,249 653,262 664,272 670,274 667,281 674,294 665,306 651,307 650,318 676,316 686,312
710,315 720,319 745,312 759,307 765,298 781,289 796,284 807,289 813,300 831,300 841,300 849,304 856,312
875,320 881,325 891,328 902,343 898,353 893,361 890,355 891,345 884,337 887,350 878,361 876,354 878,346
873,338 874,348 867,355 865,349 866,338 854,325 845,320 837,322 818,328 806,333 799,341 790,343 779,343
767,339 750,343 724,352 710,364 697,375 693,385 702,414 712,436 745,444 772,449 779,458 749,453 733,453
770,475 799,497 792,508 768,490 790,517 784,523 746,486 720,474 736,510 753,532 745,541 721,549 711,570
696,580 677,580 660,601 644,620 635,645 628,655 619,657 611,652 609,643 613,628 609,614 623,601 627,591
641,567 622,570 611,579 600,600 592,614 592,626 586,633 579,635 571,628 567,617 572,601 584,579 587,564
595,547 595,530 586,521 586,514 595,504 600,480 596,472 602,451 610,428 620,413 620,405 598,394 585,394
575,403 558,410 545,409 525,402 505,390 489,381 478,375 470,368 466,363 473,365 469,354 470,350 479,357
473,346 475,343 486,355 493,357 489,346 491,343 500,352 505,364 516,375 536,381 549,383 558,380 574,363
592,348 604,337 610,329 590,330 569,350 556,360 564,346 543,353 538,350 548,339 564,334 586,332 594,324
575,329 563,322 557,310 558,294 565,284 575,276 587,276 592,262
"""


def glass(image):
    x,y,width,height = 826,137,105,105
    hsv = cv2.cvtColor(image[y:y+height,x:x+width],cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,(4,127,116),(39,255,255))
    # Exclude the brass mounting tabs beyond the glass rim. The near wing is neutral white.
    pane = np.zeros_like(mask)
    cv2.ellipse(pane,(869-x,188-y),(29,29),0,0,360,255,-1)
    mask = cv2.bitwise_and(mask,pane)
    mask = cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    curve = max(contours,key=cv2.contourArea)[:,0,:] + [x,y]
    curve = np.roll(curve,-np.argmin(curve[:,0]+.01*curve[:,1]),axis=0)
    curve = np.concatenate((curve,curve[:1]))
    cumulative = np.r_[0,np.cumsum(np.linalg.norm(np.diff(curve,axis=0),axis=1))]
    targets = np.linspace(0,cumulative[-1],40,endpoint=False)
    return np.int32(np.round(np.column_stack([np.interp(targets,cumulative,curve[:,k]) for k in (0,1)])))


def main():
    frames = list(tune.read_frames(media.ART/"drama/c1_10_talon.mp4"))[72:96]
    polygons = np.asarray([[int(v) for v in xy.split(",")] for xy in SILHOUETTE.split()],np.float32)
    regions = {"sac":[],"yunyi":[]}
    engine = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    evidence = []
    prev_gray = None
    for n,image in enumerate(frames):
        gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            flow = engine.calc(prev_gray,gray,None)
            centers = polygons.round().astype(int)
            polygons += np.array([np.median(flow[y-2:y+3,x-2:x+3],axis=(0,1)) for x,y in centers])
        prev_gray = gray
        person = polygons.round().astype(np.int32)
        sac = glass(image)
        for key,points in (("sac",sac),("yunyi",person)):
            regions[key].append({"frame":72+n,"polygon":points.tolist()})
        if n in (0,3,5,6,12,17,23):
            proof = image.copy()
            cv2.polylines(proof,[sac],True,(0,255,255),2,cv2.LINE_AA)
            cv2.polylines(proof,[person],True,(216,40,234),2,cv2.LINE_AA)
            view = cv2.resize(proof[138:666,443:934],(306,330))
            cv2.putText(view,str(n+72),(10,25),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),2)
            evidence.append(view)
        print(n+72,round(cv2.contourArea(sac)))
    evidence.append(np.zeros_like(evidence[-1]))
    cv2.imwrite(str(tune.AUDIT/"talon_regions_review.jpg"),np.vstack((np.hstack(evidence[:4]),np.hstack(evidence[4:]))))
    destination = media.PRODUCTION/"tuning_talon_geometry.json"
    media.write_json(destination,{"file":"assets/linyuan/drama/c1_10_talon.mp4",
        "sha256":media.hash_file(media.ART/"drama/c1_10_talon.mp4"),"window_start":72,"regions":regions})


if __name__ == "__main__":
    main()
