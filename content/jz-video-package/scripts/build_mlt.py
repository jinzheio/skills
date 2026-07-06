#!/usr/bin/env python3
"""从 decisions.json 生成 Shotcut/Kdenlive 可打开的 MLT XML 项目文件。

用法:
    python3 build_mlt.py work/decisions.json -o work/project.mlt
    python3 build_mlt.py work/decisions.json --check

与 build_draft.py 消费同一份 decisions.json（schema 见 references/draft-build.md）。
效果映射说明与局限见 references/mlt-build.md。
设计原则：单个效果失败只警告并跳过，不中断项目生成。
"""
import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

SEC = 1_000_000
WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"[警告] {msg}", file=sys.stderr)


def us(t) -> int:
    if isinstance(t, (int, float)):
        return int(t * SEC)
    s = str(t).strip().lower()
    total, num = 0.0, ""
    for unit, mult in (("h", 3600), ("m", 60), ("s", 1)):
        if unit in s:
            part, s = s.split(unit, 1)
            total += float(part or 0) * mult
    return int(total * SEC)


def clock(usec: int) -> str:
    """微秒 → MLT 时钟串 hh:mm:ss.mmm"""
    ms = usec // 1000
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def ffprobe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True, text=True).stdout
    return json.loads(out or "{}")


def media_duration_us(path: str) -> int:
    info = ffprobe(path)
    try:
        return int(float(info["format"]["duration"]) * SEC)
    except Exception:
        return 0


def prop(parent, name, value):
    e = ET.SubElement(parent, "property", {"name": name})
    e.text = str(value)
    return e


def color_hex(rgb, alpha=255) -> str:
    r, g, b = (max(0, min(255, int(round(c * 255)))) for c in rgb)
    return f"#{alpha:02x}{r:02x}{g:02x}{b:02x}"  # #aarrggbb


class MltProject:
    def __init__(self, width, height, fps, total_us):
        self.W, self.H, self.fps, self.total = width, height, fps, total_us
        self.root = ET.Element("mlt", {
            "LC_NUMERIC": "C", "version": "7.24.0",
            "title": "jz-video-package", "producer": "main_bin"})
        ET.SubElement(self.root, "profile", {
            "description": "custom", "width": str(width), "height": str(height),
            "progressive": "1", "sample_aspect_num": "1", "sample_aspect_den": "1",
            "display_aspect_num": str(width), "display_aspect_den": str(height),
            "frame_rate_num": str(fps), "frame_rate_den": "1", "colorspace": "709"})
        main_bin = ET.SubElement(self.root, "playlist", {"id": "main_bin"})
        prop(main_bin, "xml_retain", 1)
        black = ET.SubElement(self.root, "producer",
                              {"id": "black", "in": clock(0), "out": clock(total_us)})
        prop(black, "resource", 0)
        prop(black, "mlt_service", "color")
        prop(black, "mlt_image_format", "rgba")
        bg = ET.SubElement(self.root, "playlist", {"id": "background"})
        ET.SubElement(bg, "entry", {"producer": "black", "in": clock(0), "out": clock(total_us)})
        self.tracks: list[tuple[str, str]] = []  # (playlist_id, 名称)
        self._cursors: dict[str, int] = {}       # playlist_id → 时间线位置（µs）
        self._pid = 0

    def _next_id(self, prefix):
        self._pid += 1
        return f"{prefix}{self._pid}"

    def clip_chain(self, path: str, src_in: int, src_out: int, mute=False) -> ET.Element:
        cid = self._next_id("chain")
        chain = ET.SubElement(self.root, "chain",
                              {"id": cid, "out": clock(max(src_out - 1, 0))})
        prop(chain, "resource", os.path.abspath(path))
        prop(chain, "mlt_service", "avformat-novalidate")
        prop(chain, "shotcut:caption", os.path.basename(path))
        if mute:
            prop(chain, "audio_index", -1)
        return chain

    def text_producer(self, dur: int) -> ET.Element:
        pid = self._next_id("producer")
        p = ET.SubElement(self.root, "producer", {"id": pid, "in": clock(0), "out": clock(dur)})
        prop(p, "length", clock(dur + SEC))
        prop(p, "mlt_service", "color")
        prop(p, "resource", "#00000000")
        prop(p, "mlt_image_format", "rgba")
        return p

    def add_filter(self, parent, service, dur, **props):
        f = ET.SubElement(parent, "filter", {"id": self._next_id("filter"), "out": clock(max(dur - 1, 0))})
        prop(f, "mlt_service", service)
        for k, v in props.items():
            prop(f, k.replace("__", "."), v)
        return f

    def track(self, name: str, is_video=True) -> ET.Element:
        plid = self._next_id("playlist")
        pl = ET.SubElement(self.root, "playlist", {"id": plid})
        prop(pl, "shotcut:video", 1 if is_video else 0)
        prop(pl, "shotcut:name", name)
        self.tracks.append((plid, name))
        self._cursors[plid] = 0
        return pl

    def place(self, pl: ET.Element, producer: ET.Element, start: int, dur: int, src_in=0):
        plid = pl.get("id")
        cursor = self._cursors.get(plid, 0)
        if start < cursor:
            raise ValueError(f"轨道 {plid} 片段重叠：{clock(start)} < {clock(cursor)}")
        if start > cursor:
            ET.SubElement(pl, "blank", {"length": clock(start - cursor)})
        ET.SubElement(pl, "entry", {"producer": producer.get("id"),
                                    "in": clock(src_in), "out": clock(src_in + dur - 1)})
        self._cursors[plid] = start + dur

    def finish(self) -> ET.Element:
        tractor = ET.SubElement(self.root, "tractor", {
            "id": "tractor0", "title": "jz-video-package",
            "in": clock(0), "out": clock(self.total)})
        prop(tractor, "shotcut", 1)
        prop(tractor, "shotcut:projectAudioChannels", 2)
        prop(tractor, "shotcut:projectFolder", 0)
        ET.SubElement(tractor, "track", {"producer": "background"})
        for plid, _ in self.tracks:
            ET.SubElement(tractor, "track", {"producer": plid})
        for i in range(1, len(self.tracks) + 1):
            mix = ET.SubElement(tractor, "transition", {"id": self._next_id("transition")})
            prop(mix, "a_track", 0)
            prop(mix, "b_track", i)
            prop(mix, "mlt_service", "mix")
            prop(mix, "always_active", 1)
            prop(mix, "sum", 1)
            if i > 1:  # 上层视频轨的画面合成
                tb = ET.SubElement(tractor, "transition", {"id": self._next_id("transition")})
                prop(tb, "a_track", 1)
                prop(tb, "b_track", i)
                prop(tb, "version", "0.1")
                prop(tb, "mlt_service", "frei0r.cairoblend")
                prop(tb, "threads", 0)
                prop(tb, "disable", 0)
        return tractor


def rect_kf(W, H, pairs):
    """[(t_us, x, y, w, h, opacity)] → affine transition.rect 动画串"""
    return ";".join(f"{clock(t)}={x:.0f} {y:.0f} {w:.0f} {h:.0f} {o:g}" for t, x, y, w, h, o in pairs)


def motion_filter(proj, chain, motion, dur, base=None):
    """缩放/平移动势 → affine filter。base=(x,y,w,h) 初始摆放，默认全屏。"""
    W, H = proj.W, proj.H
    bx, by, bw, bh = base or (0, 0, W, H)
    if not motion and base is None:
        return
    pairs = []
    s0 = (motion or {}).get("scale_from", 1.0)
    s1 = (motion or {}).get("scale_to", s0)
    px = (motion or {}).get("pan_x", 0.0) * W
    py = (motion or {}).get("pan_y", 0.0) * H
    for t, s, dx, dy in ((0, s0, 0, 0), (dur, s1, px, py)):
        w, h = bw * s, bh * s
        pairs.append((t, bx + (bw - w) / 2 + dx, by + (bh - h) / 2 + dy, w, h, 1))
    proj.add_filter(chain, "affine", dur,
                    background="color:#00000000",
                    transition__fill=1, transition__distort=0,
                    transition__rect=rect_kf(W, H, pairs),
                    shotcut__filter="affineSizePosition")


def mask_filter(proj, chain, mask, dur):
    if not mask:
        return
    W, H = proj.W, proj.H
    size = float(mask.get("size", 0.5))
    cx = W / 2 + float(mask.get("center_x", 0))
    cy = H / 2 + float(mask.get("center_y", 0))
    mtype = mask.get("type", "圆形")
    if mtype == "圆形":
        d = size * min(W, H)
        rect = f"{cx - d/2:.0f} {cy - d/2:.0f} {d:.0f} {d:.0f}"
        proj.add_filter(chain, "qtcrop", dur, rect=rect, circle=1,
                        radius=1, color="#00000000")
    else:  # 矩形/圆角矩形
        w, h = size * W, size * H
        rect = f"{cx - w/2:.0f} {cy - h/2:.0f} {w:.0f} {h:.0f}"
        proj.add_filter(chain, "qtcrop", dur, rect=rect, circle=0,
                        radius=float(mask.get("round_corner", 10)) / 100, color="#00000000")
    if mask.get("feather"):
        warn("MLT qtcrop 不支持羽化，已忽略 feather（可在 Shotcut 里加 Blur: Gaussian 到蒙版边缘）")


def fade_filter(proj, chain, dur, fade_in=0, fade_out=0, level=1.0):
    parts = []
    if fade_in:
        parts += [(0, 0.0), (fade_in, level)]
    else:
        parts += [(0, level)]
    if fade_out:
        parts += [(dur - fade_out, level), (dur, 0.0)]
    kf = ";".join(f"{clock(t)}={v:g}" for t, v in parts)
    proj.add_filter(proj_chain_target(chain), "brightness", dur, alpha=kf, opacity=kf)


def proj_chain_target(chain):
    return chain


def build(data: dict, out_path: str) -> None:
    proj_cfg = data["project"]
    host = proj_cfg["host_video"]
    W, H = proj_cfg["width"], proj_cfg["height"]
    info = ffprobe(host)
    fps = 30
    for st in info.get("streams", []):
        if st.get("codec_type") == "video":
            num, den = (st.get("r_frame_rate") or "30/1").split("/")
            fps = max(1, round(float(num) / float(den)))
    total = media_duration_us(host)
    proj = MltProject(W, H, fps, total)

    decisions = [d for d in data.get("decisions", []) if d.get("type") != "subtitles"]
    todos = []
    for d in decisions:
        mat = d.get("material") or d.get("bg_material")
        if isinstance(mat, str) and mat.startswith("TODO:"):
            todos.append(f"{d['type']} @ {d.get('start', d.get('at'))}: {mat[5:]}")
            d["_skip"] = True
        elif mat and not os.path.exists(mat):
            warn(f"素材不存在，跳过: {mat}")
            d["_skip"] = True
        if d.get("type") == "film_transition":
            at, dur = us(d["at"]), us(d.get("duration", "0.5s"))
            d["_start"], d["_end"] = max(0, at - dur // 2), max(0, at - dur // 2) + dur
        else:
            d["_start"], d["_end"] = us(d["start"]), us(d["end"])

    # 轨道：V1 口播 / V2 B-roll / V3 强调 / V4 叠加 / V5 转场 / 文字若干
    t_host = proj.track("口播")
    t_broll = proj.track("B-roll")
    t_focus = proj.track("强调")
    t_over = proj.track("叠加层")
    t_trans = proj.track("转场层")

    host_chain = proj.clip_chain(host, 0, total)
    proj.place(t_host, host_chain, 0, total)

    text_lanes: list[tuple[ET.Element, int]] = []  # (playlist, cursor 由 place 维护)

    def place_text(item, start, end):
        dur = end - start
        p = proj.text_producer(dur)
        geo_x = (item.get("x", 0.0)) * W / 2
        geo_y = (item.get("y", 0.0)) * H / 2
        size_px = int(item.get("size", 8.0) / 100 * H)  # 剪映字号≈画面高度百分比
        f = proj.add_filter(p, "dynamictext", dur,
                            argument=item["text"], geometry=f"{geo_x:.0f} {geo_y:.0f} {W} {H}",
                            family=item.get("font_family", "Songti SC" if item.get("font") == "宋体" else "Sans"),
                            size=size_px, weight=700,
                            fgcolour=color_hex(item.get("color", [1, 1, 1])),
                            bgcolour="#00000000",
                            halign="centre", valign="middle",
                            shotcut__filter="dynamicText",
                            shotcut__usePointSize=0)
        if item.get("border_color") is not None:
            prop(f, "olcolour", color_hex(item["border_color"]))
            prop(f, "outline", max(1, size_px // 30))
        if item.get("anim_in"):
            fade_filter(proj, p, dur, fade_in=min(us("0.4s"), dur // 3),
                        fade_out=min(us("0.3s"), dur // 4) if item.get("anim_out") else 0)
        if item.get("motion"):
            motion_filter(proj, p, item["motion"], dur)
        for pl, _ in text_lanes:
            try:
                proj.place(pl, p, start, dur)
                return
            except ValueError:
                continue
        pl = proj.track(f"文字{len(text_lanes) + 1}")
        text_lanes.append((pl, 0))
        proj.place(pl, p, start, dur)

    for d in sorted(decisions, key=lambda x: x["_start"]):
        if d.get("_skip"):
            continue
        t, start, end = d["type"], d["_start"], d["_end"]
        dur = end - start

        if t in ("broll", "overlay", "film_transition"):
            mat_dur = media_duration_us(d["material"])
            src_in = us(d.get("source_start", 0))
            if src_in + dur > mat_dur:
                if mat_dur < dur:
                    warn(f"{os.path.basename(d['material'])} 比区间短，MLT 端按素材原速循环不可用，"
                         f"已从头截取（Shotcut 里可对片段设置慢速补足）")
                src_in = 0
                dur_clip = min(dur, mat_dur)
            else:
                dur_clip = dur
            chain = proj.clip_chain(d["material"], src_in, src_in + dur_clip,
                                    mute=d.get("mute", True))
            if t == "broll":
                motion_filter(proj, chain, d.get("motion"), dur_clip)
                mask_filter(proj, chain, d.get("mask"), dur_clip)
                if d.get("anim_in"):
                    fade_filter(proj, chain, dur_clip, fade_in=min(us("0.4s"), dur_clip // 3))
                proj.place(t_broll, chain, start, dur_clip, src_in)
            else:
                proj.add_filter(chain, "cairoblend_mode", dur_clip, mode="screen")
                alpha = d.get("alpha", 1.0)
                fade = us(d.get("fade", "0.3s")) if t == "overlay" else dur_clip // 3
                fade_filter(proj, chain, dur_clip, fade_in=fade, fade_out=fade, level=alpha)
                proj.place(t_over if t == "overlay" else t_trans, chain, start, dur_clip, src_in)

        elif t == "host_focus":
            chain = proj.clip_chain(host, start, end, mute=True)
            mask_filter(proj, chain, d.get("mask"), dur)
            if d.get("scale_to") or d.get("x") or d.get("y"):
                motion_filter(proj, chain,
                              {"scale_from": d.get("scale_from", 1.0),
                               "scale_to": d.get("scale_to", d.get("scale_from", 1.0)),
                               "pan_x": d.get("x", 0.0), "pan_y": d.get("y", 0.0)}, dur)
            proj.place(t_focus, chain, start, dur, src_in=start)

        elif t == "keyword":
            place_text(d, start, end)

        elif t == "card":
            if d.get("bg_material") and not d.get("_skip"):
                bw, bh = W * d.get("bg_scale", 1.0), H * d.get("bg_scale", 1.0)
                bx = W / 2 + d.get("bg_x", 0.0) * W / 2 - bw / 2
                by = H / 2 + d.get("bg_y", 0.0) * H / 2 - bh / 2
                chain = proj.clip_chain(d["bg_material"], 0, dur, mute=True)
                motion_filter(proj, chain, d.get("motion"), dur, base=(bx, by, bw, bh))
                proj.place(t_focus, chain, start, dur)
            stagger = us(d.get("line_stagger", "0.8s"))
            spacing = d.get("line_spacing", 0.12)
            for i, line in enumerate(d.get("lines", [])):
                item = dict(d, text=line, y=d.get("y", 0.0) + i * spacing)
                place_text(item, min(start + i * stagger, end - SEC // 2), end)

        elif t in ("effect", "filter"):
            warn(f"{t} '{d.get('name')}' 是剪映特效枚举，MLT 无对应实现，请在 Shotcut 滤镜面板手动添加")

    proj.finish()
    ET.indent(proj.root)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    ET.ElementTree(proj.root).write(out_path, encoding="utf-8", xml_declaration=True)
    print(f"\n✅ MLT 项目已生成: {out_path}（用 Shotcut 打开）")
    if data["project"].get("srt"):
        print(f"ℹ️ 字幕请在 Shotcut 的「字幕」面板导入: {data['project']['srt']}")
    if todos:
        print("\n⏳ TODO 素材待补充（已跳过）：")
        for x in todos:
            print("  - " + x)
    if WARNINGS:
        print(f"\n⚠️ {len(WARNINGS)} 条警告，见上方输出。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("decisions")
    ap.add_argument("-o", "--output", default="work/project.mlt")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    with open(args.decisions, encoding="utf-8") as f:
        data = json.load(f)
    if args.check:
        n = len(data.get("decisions", []))
        missing = [str(d.get("material") or d.get("bg_material"))
                   for d in data["decisions"]
                   if (d.get("material") or d.get("bg_material"))
                   and not str(d.get("material") or d.get("bg_material")).startswith("TODO:")
                   and not os.path.exists(str(d.get("material") or d.get("bg_material")))]
        print(f"{n} 条决策；缺失素材 {len(missing)} 个")
        for m in missing:
            print("  缺失 - " + m)
        return
    build(data, args.output)


if __name__ == "__main__":
    main()
