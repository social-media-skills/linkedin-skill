#!/usr/bin/env python3
"""Video posts with ffmpeg: fit the user's clip to a LinkedIn shape, burn in captions from the
user's own transcript (SRT), turn photos into a short video, and look at the frames first.

    python3 scripts/video.py fit clip.mov --ratio 4:5 --x 0.5 --start 1.2 --end 40 --out video/post.mp4
    python3 scripts/video.py fit clip.mov --ratio 1:1 --fit pad --bg black --out video/post.mp4
    python3 scripts/video.py captions video/post.mp4 --srt talk.srt --out video/post-captioned.mp4
    python3 scripts/video.py stills a.jpg b.jpg c.jpg --seconds 2 --ratio 4:5 --out video/stills.mp4
    python3 scripts/video.py frames video/post.mp4 --out video/        # frames-sheet.jpg to look at

fit:      crops to the ratio around --x/--y (where the subject is), or pads (--fit pad) with a blurred
          copy or a colour (--bg black). --start/--end trim; --speed 2 for timelapses (drops sound).
captions: burns the SRT's lines into the lower part of the frame (white on a dark box, Inter), so
          the video makes sense muted, which is how most people see it in the feed. Use the user's own
          words: a transcript they have, or lines they wrote. LinkedIn's own captions file isn't sent
          by the posting API, so burned-in captions are the way to have them.
stills:   each photo held --seconds, crossfades (or --fade 0 for hard cuts).
frames:   8 evenly spaced frames on one sheet, the feed crop drawn on each.
Sizes: 4:5 = 1080x1350 (most room in the feed), 1:1 = 1080x1080, 9:16 = 1080x1920, 16:9 = 1920x1080.
"""
import argparse, json, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lilib as P  # noqa: E402

SIZES = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920), "16:9": (1920, 1080)}
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
       "-movflags", "+faststart"]


def need_ffmpeg():
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        sys.exit("ffmpeg is needed for video posts: run python3 scripts/check_setup.py for the install command")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit("ffmpeg failed:\n" + r.stderr[-1500:])


def has_audio(path):
    info = P.ffprobe(path) or {}
    return any(s.get("codec_type") == "audio" for s in info.get("streams", []))


def cmd_fit(a):
    w, h = SIZES[a.ratio]
    trim = []
    if a.start:
        trim += ["-ss", str(a.start)]
    if a.end:
        trim += ["-to", str(a.end)]
    if a.fit == "crop":
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
              f"crop={w}:{h}:(iw-{w})*{a.x}:(ih-{h})*{a.y},setsar=1")
        if a.speed != 1:
            vf += f",setpts=PTS/{a.speed}"
        fc = ["-vf", vf]
    else:
        bg = (f"color=c={a.bg}:s={w}x{h}[bg];" if a.bg != "blur" else
              f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:3,eq=brightness=-0.08[bg];")
        fc = ["-filter_complex", bg +
              f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1{f',setpts=PTS/{a.speed}' if a.speed != 1 else ''}[v]",
              "-map", "[v]"] + (["-map", "0:a?"] if a.speed == 1 else [])
    audio = ["-c:a", "aac", "-b:a", "160k"] if has_audio(a.input) and a.speed == 1 else ["-an"]
    if a.speed != 1 and has_audio(a.input):
        print("note: --speed drops the sound track")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error"] + trim + ["-i", a.input] + fc + ENC + audio + [a.out])
    dur = P.duration(P.ffprobe(a.out))
    print(f"wrote {a.out} ({w}x{h}, {dur:.1f} s)")
    if dur < P.VIDEO_MIN_S:
        print(f"warning: {dur:.1f} s is under LinkedIn's 3 s minimum")


def cmd_stills(a):
    from PIL import Image, ImageOps
    w, h = SIZES[a.ratio]
    tmp = os.path.join(os.path.dirname(os.path.abspath(a.out)), ".stills")
    os.makedirs(tmp, exist_ok=True)
    frames = []
    for i, f in enumerate(a.images):
        im = P.open_image(f)
        im = ImageOps.fit(im, (w, h), P.LANCZOS, centering=(a.x, a.y))
        p = os.path.join(tmp, f"{i:03d}.png")
        im.save(p)
        frames.append(p)
    if len(frames) < 2:
        sys.exit("stills needs at least 2 images")
    fade = max(0.0, min(a.fade, a.seconds / 3))
    if fade == 0:      # hard cuts: text changes cleanly, no ghosted double headlines
        listfile = os.path.join(tmp, "list.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for p in frames:
                f.write(f"file '{os.path.abspath(p).replace(chr(92), '/')}'\nduration {a.seconds:.3f}\n")
            f.write(f"file '{os.path.abspath(frames[-1]).replace(chr(92), '/')}'\n")
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", listfile, "-vf", "fps=30,format=yuv420p"]
            + ENC + ["-an", a.out])
        shutil.rmtree(tmp, ignore_errors=True)
        dur = P.duration(P.ffprobe(a.out))
        print(f"wrote {a.out} ({w}x{h}, {len(frames)} photos, hard cuts, {dur:.1f} s)")
        if dur < P.VIDEO_MIN_S:
            print(f"warning: {dur:.1f} s is under LinkedIn's 3 s minimum; add photos or raise --seconds")
        return
    inputs, chain = [], ""
    for p in frames:
        inputs += ["-loop", "1", "-t", f"{a.seconds + fade:.3f}", "-i", p]
    prev = "[0:v]"
    for i in range(1, len(frames)):
        out = f"[x{i}]" if i < len(frames) - 1 else "[v]"
        # each input lasts seconds+fade; the i-th crossfade starts i*seconds in
        chain += f"{prev}[{i}:v]xfade=transition=fade:duration={fade:.3f}:offset={i * a.seconds:.3f}{out};"
        prev = out
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", chain.rstrip(";"),
         "-map", "[v]"] + ENC + ["-an", a.out])
    shutil.rmtree(tmp, ignore_errors=True)
    dur = P.duration(P.ffprobe(a.out))
    print(f"wrote {a.out} ({w}x{h}, {len(frames)} photos, {dur:.1f} s)")
    if dur < P.VIDEO_MIN_S:
        print(f"warning: {dur:.1f} s is under LinkedIn's 3 s minimum; add photos or raise --seconds")


def parse_srt(path):
    import re
    text = open(path, encoding="utf-8-sig", errors="replace").read().replace("\r", "")
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", block)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        t0 = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        t1 = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        words = " ".join(l.strip() for l in block[m.end():].strip().split("\n") if l.strip())
        words = re.sub(r"\[[^\]]*\]|<[^>]+>", "", words).strip()     # [music], <i> tags
        if words and t1 > t0:
            out.append((t0, t1, words))
    return out


def cmd_captions(a):
    from PIL import Image, ImageDraw, ImageFont
    info = P.ffprobe(a.input) or {}
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        sys.exit("no video stream found")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        try:
            rot = abs(int(float(sd.get("rotation", 0) or 0)))
        except (TypeError, ValueError):
            pass
    if rot % 180 == 90:     # phone video: ffmpeg turns it upright before the overlay
        w, h = h, w
    dur = P.duration(info)
    try:
        cues = parse_srt(a.srt)
    except OSError as e:
        sys.exit(f"can't read {a.srt}: {e}")
    if not cues:
        sys.exit(f"no captions found in {a.srt} (an SRT file: number, 00:00:01,000 --> 00:00:03,000, text)")
    late = [c for c in cues if dur and c[0] >= dur]
    if late:
        print(f"note: {len(late)} caption(s) start after the video ends ({dur:.1f} s) and are left out")
        cues = [c for c in cues if not (dur and c[0] >= dur)]
    fonts = a.font_file or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts", "Inter.ttf")
    if not os.path.exists(fonts):
        sys.exit(f"font file not found: {fonts}")
    size = max(28, round(w * 0.045))
    f = ImageFont.truetype(fonts, size)
    try:
        f.set_variation_by_name("SemiBold")
    except Exception:
        pass
    probe = ImageDraw.Draw(Image.new("L", (size * 4, size * 4)))
    def ink(ch):
        im = Image.new("L", (size * 3, size * 3))
        ImageDraw.Draw(im).text((size // 2, size // 2), ch, font=f, fill=255)
        return im.tobytes()
    notdef = ink("\uffff")
    import re as _re
    emoji = _re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\ufe0f]")
    cues = [(t0, t1, emoji.sub("", t).strip()) for t0, t1, t in cues]
    gone = sorted({ch for _, _, t in cues for ch in t if not ch.isspace() and ink(ch) == notdef})
    if gone:
        sys.exit(f"the caption font can't draw {' '.join(gone[:8])} (they'd show as empty boxes): "
                 "pass --font-file with a font that has them (for example a Noto Sans font for your script)")
    tmp = os.path.join(os.path.dirname(os.path.abspath(a.out)), ".captions")
    os.makedirs(tmp, exist_ok=True)
    plates = []
    maxw = w * 0.84
    for i, (t0, t1, words) in enumerate(cues):
        lines, line = [], ""
        tokens = []
        for word in words.split():
            if probe.textlength(word, font=f) > maxw:    # no spaces (CJK) or one very long word: break by characters
                tokens += list(word)
            else:
                tokens.append(word)
        for word in tokens:
            joiner = "" if (len(word) == 1 and ord(word) > 0x2E80) else " "
            trial = (line + joiner + word).strip() if line else word
            if probe.textlength(trial, font=f) <= maxw or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
        if len(lines) > 2:
            print(f"note: caption {i + 1} runs to {len(lines)} lines; split it in the SRT so it reads at a glance")
        lh = round(size * 1.25)
        bw = int(max(probe.textlength(l, font=f) for l in lines) + size)
        bh = lh * len(lines) + round(size * 0.6)
        plate = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        pd = ImageDraw.Draw(plate)
        pd.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=round(size * 0.35), fill=(0, 0, 0, 170))
        for k, l in enumerate(lines):
            pd.text(((bw - pd.textlength(l, font=f)) / 2, round(size * 0.3) + k * lh), l, font=f, fill=(255, 255, 255, 255))
        p = os.path.join(tmp, f"c{i:04d}.png")
        plate.save(p)
        plates.append((t0, t1, p, max(0, round(h * a.y) - bh)))
    # a batch of captions per ffmpeg pass keeps the command short (Windows) and memory low
    src, step = a.input, 50
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    for start in range(0, len(plates), step):
        batch = plates[start:start + step]
        last = start + step >= len(plates)
        out = a.out if last else os.path.join(tmp, f"pass{start // step}.mp4")
        inputs, chain, prev = [], "", "[0:v]"
        for i, (t0, t1, p, y) in enumerate(batch):
            inputs += ["-i", p]
            lab = f"[v{i}]" if i < len(batch) - 1 else "[v]"
            chain += f"{prev}[{i + 1}:v]overlay=(W-w)/2:{y}:enable='between(t,{t0:.3f},{t1 - 0.001:.3f})'{lab};"
            prev = lab
        audio = ["-map", "0:a?", "-c:a", "aac", "-b:a", "160k"]
        run(["ffmpeg", "-y", "-v", "error", "-i", src] + inputs + ["-filter_complex", chain.rstrip(";"), "-map", "[v]"]
            + ENC + audio + [out])
        src = out
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {a.out} with {len(plates)} captions, bottom edge at {round(a.y * 100)}% of the height")


def cmd_frames(a):
    from PIL import Image, ImageDraw
    dur = P.duration(P.ffprobe(a.input))
    if not dur:
        sys.exit("couldn't read the video's length")
    os.makedirs(a.out, exist_ok=True)
    shots = []
    for i in range(a.n):
        t = dur * (i + 0.5) / a.n
        fr = P.frame_at(a.input, t)
        if fr:
            shots.append((t, fr))
    tw = 240
    sheet = None
    for i, (t, fr) in enumerate(shots):
        th = int(tw * fr.height / fr.width)
        if sheet is None:
            sheet = Image.new("RGB", (len(shots) * (tw + 10) + 10, th + 46), "#EEEEEE")
        im = fr.resize((tw, th), P.LANCZOS)
        d = ImageDraw.Draw(im)
        cw, ch = (tw, int(tw * 1.25)) if th > tw * 1.25 else (int(th / 1.25), th)
        x0, y0 = (tw - cw) // 2, (th - ch) // 2
        d.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], outline="#0A66C2", width=3)
        sheet.paste(im, (10 + i * (tw + 10), 10))
        ImageDraw.Draw(sheet).text((10 + i * (tw + 10), th + 18), f"{t:.1f} s", fill="#333333")
    if sheet is None:
        sys.exit("couldn't read any frames from the video")
    path = os.path.join(a.out, "frames-sheet.jpg")
    sheet.save(path, quality=88)
    json.dump([{"t": round(t, 2)} for t, _ in shots], open(os.path.join(a.out, "frames.json"), "w"))
    print(f"wrote {path}: the blue box is the 4:5 area the feed shows. Open on the frame that tells the story")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("input")
    f.add_argument("--ratio", choices=SIZES, default="4:5")
    f.add_argument("--fit", choices=["crop", "pad"], default="crop")
    f.add_argument("--bg", default="blur", help="pad background: blur (a blurred copy) or a colour like black or #0D1020")
    f.add_argument("--x", type=float, default=0.5)
    f.add_argument("--y", type=float, default=0.5)
    f.add_argument("--start", type=float)
    f.add_argument("--end", type=float)
    f.add_argument("--speed", type=float, default=1.0, help="play faster (2 = twice as fast; drops the sound)")
    f.add_argument("--out", required=True)
    s = sub.add_parser("stills")
    s.add_argument("images", nargs="+")
    s.add_argument("--seconds", type=float, default=1.2)
    s.add_argument("--fade", type=float, default=0.3, help="crossfade seconds; 0 = hard cuts (use when frames carry text)")
    s.add_argument("--ratio", choices=SIZES, default="4:5")
    s.add_argument("--x", type=float, default=0.5)
    s.add_argument("--y", type=float, default=0.5)
    s.add_argument("--out", required=True)
    c = sub.add_parser("captions")
    c.add_argument("input")
    c.add_argument("--srt", required=True)
    c.add_argument("--y", type=float, default=0.86, help="where the caption box ends, as a fraction of the height (clear of the player controls)")
    c.add_argument("--font-file", help="a .ttf/.otf with the characters your captions need (e.g. Noto Sans CJK)")
    c.add_argument("--out", required=True)
    fr = sub.add_parser("frames")
    fr.add_argument("input")
    fr.add_argument("--n", type=int, default=8)
    fr.add_argument("--out", required=True)
    a = ap.parse_args()
    if getattr(a, "speed", 1) <= 0:
        sys.exit("--speed must be above 0")
    for k in ("x", "y"):
        if hasattr(a, k) and not 0 <= getattr(a, k) <= 1:
            sys.exit(f"--{k} is a fraction of the frame, from 0 to 1")
    need_ffmpeg()
    {"fit": cmd_fit, "stills": cmd_stills, "frames": cmd_frames, "captions": cmd_captions}[a.cmd](a)


if __name__ == "__main__":
    main()
