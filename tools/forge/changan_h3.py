"""Submit and record local MiniMax H3 first/last-frame video jobs."""

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen


COMFY = Path.home() / "aivideo/ComfyUI"
URL = "http://127.0.0.1:8194"
BASE = (
    "A continuous photoreal live-action Tang dynasty fantasy film take at the Shangyuan lantern "
    "festival in Chang'an. Locked tripod and fixed lens. Preserve the camera, street geometry, "
    "midnight indigo sky, amber practical lanterns and grounded scale of the supplied references. "
    "Only the intended subject moves, with light incidental motion in the distant festival crowd. "
    "Natural night market ambience and magical foley only. No music, dialogue, titles, graphics, UI "
    "or cuts. "
)


def node(kind, **inputs):
    return {"class_type": kind, "inputs": inputs}


def request(path, payload=None):
    if payload is not None:
        payload = json.dumps(payload).encode()
    with urlopen(Request(URL + path, payload, {"Content-Type": "application/json"}), timeout=45) as resp:
        return json.load(resp)


def workflow(job, inputs, prefix):
    graph = {
        "1": node("UNETLoader", unet_name="minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                  weight_dtype="default"),
        "2": node("LoraLoaderModelOnly",
                  lora_name="minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors",
                  strength_model=1.0, model=["1", 0]),
        "3": node("CLIPLoader", clip_name="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                  type="minimax", device="default"),
        "4": node("VAELoader", vae_name="minimax_h3_video_vae_int8_convrot.safetensors"),
        "5": node("VAELoader", vae_name="minimax_h3_audio_vae_fp32.safetensors"),
        "6": node("MiniMaxH3ImageToVideo", clip=["3", 0], vae=["4", 0],
                  prompt=job.get("prefix", BASE) + job["prompt"],
                  width=1024, height=576, length=job["length"], first_frame=["16", 0]),
        "7": node("RandomNoise", noise_seed=job["seed"]),
        "8": node("KSamplerSelect", sampler_name="res_multistep"),
        "9": node("BasicScheduler", model=["2", 0], scheduler="simple", steps=4, denoise=1.0),
        "10": node("BasicGuider", model=["2", 0], conditioning=["6", 0]),
        "11": node("SamplerCustomAdvanced", noise=["7", 0], guider=["10", 0], sampler=["8", 0],
                   sigmas=["9", 0], latent_image=["6", 1]),
        "12": node("VAEDecode", samples=["11", 0], vae=["4", 0]),
        "13": node("VAEDecodeAudio", samples=["11", 0], vae=["5", 0]),
        "14": node("CreateVideo", images=["12", 0], audio=["13", 0], fps=24),
        "15": node("SaveVideo", video=["14", 0], filename_prefix=prefix, format="auto", codec="auto"),
        "16": node("LoadImage", image=inputs[job["first"]]),
    }
    if "last" in job:
        graph["17"] = node("LoadImage", image=inputs[job["last"]])
        graph["6"]["inputs"]["last_frame"] = ["17", 0]
    if "guide" in job:
        guide, frame = job["guide"]
        graph["20"] = node("LoadImage", image=inputs[guide])
        graph["21"] = node("MiniMaxH3AddGuide", positive=["6", 0], latent=["6", 1], vae=["4", 0],
                           image=["20", 0], frame_idx=frame)
        graph["10"]["inputs"]["conditioning"] = ["21", 0]
    return graph


def generate(job_id, job, anchors, work):
    dest = work / "takes" / job_id
    dest.mkdir(parents=True, exist_ok=True)
    record = dest / "job.json"
    names = {job["first"]}
    if "last" in job:
        names.add(job["last"])
    if "guide" in job:
        names.add(job["guide"][0])
    inputs = {}
    for name in sorted(names):
        src = anchors / (name + ".png")
        key = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
        path = Path("changan_m0") / (name + "_" + key + ".png")
        target = COMFY / "input" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(src, target)
        inputs[name] = path.as_posix()

    graph = workflow(job, inputs, "changan_m0/" + job_id)
    if record.exists():
        prior = json.loads(record.read_text(encoding="utf-8"))
        if prior["workflow"] != graph:
            raise ValueError(f"Use a new candidate ID for changed workflow: {job_id}")
        history = dest / "history.json"
        if ((dest / "source.mp4").is_file() and history.is_file()
                and json.loads(history.read_bytes())["status"]["completed"]):
            return
        prompt = prior["prompt"]
    else:
        prompt = request("/prompt", {"prompt": graph})["prompt_id"]
        prior = {
            "prompt": prompt,
            "comfy_revision": subprocess.check_output(
                ["git", "-C", str(COMFY), "rev-parse", "HEAD"], text=True).strip(),
            "workflow": graph,
        }
        record.write_text(json.dumps(prior, indent=2), encoding="utf-8")

    print(f"{job_id} submitted {prompt}", flush=True)
    for _ in range(360):
        history = request("/history/" + prompt).get(prompt)
        if history:
            break
        time.sleep(4)
    else:
        raise TimeoutError(f"History unavailable for {job_id} ({prompt})")
    (dest / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    if not history["status"]["completed"]:
        raise RuntimeError(f"H3 failed: {dest / 'history.json'}")
    files = [f for o in history["outputs"].values() for values in o.values()
             if isinstance(values, list) for f in values
             if isinstance(f, dict) and f.get("filename", "").endswith(".mp4")]
    if len(files) != 1:
        raise ValueError(f"Expected one MP4: {job_id}, {files}")
    found = files[0]
    shutil.copyfile(COMFY / "output" / found["subfolder"] / found["filename"], dest / "source.mp4")
    print(f"{job_id} complete: {dest / 'source.mp4'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jobs", type=Path)
    parser.add_argument("anchors", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("ids", nargs="+")
    args = parser.parse_args()
    jobs = json.loads(args.jobs.read_text(encoding="utf-8"))
    for job_id in args.ids:
        generate(job_id, jobs[job_id], args.anchors, args.work)


if __name__ == "__main__":
    main()
