#!/usr/bin/env python3
"""从 decisions.json 生成剪映草稿。

用法:
    python3 build_draft.py work/decisions.json --draft-folder "<剪映草稿文件夹>"
    python3 build_draft.py work/decisions.json --check   # 只校验不生成

schema 见 references/draft-build.md。
设计原则：单个效果失败（枚举名不存在等）只警告并跳过，不中断草稿生成。
"""
import argparse
import json
import os
import sys

SEC = 1_000_000

WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"[警告] {msg}", file=sys.stderr)


def us(t) -> int:
    """秒数(float/int)或 '3.2s' 字符串 → 微秒。"""
    if isinstance(t, (int, float)):
        return int(t * SEC)
    import pyJianYingDraft as draft  # noqa: F401
    from pyJianYingDraft import tim
    return tim(t)


def enum_lookup(enum_cls, name: str):
    """容错查找枚举成员：先 from_name，再按属性名。找不到返回 None。"""
    if not name:
        return None
    try:
        if hasattr(enum_cls, "from_name"):
            return enum_cls.from_name(name)
    except Exception:
        pass
    member = getattr(enum_cls, name, None)
    if member is None:
        warn(f"{enum_cls.__name__} 里找不到 '{name}'，已跳过该效果")
    return member


def add_keyframes(seg, motion: dict, dur: int, kf_enum):
    """给片段加动势关键帧。motion: scale_from/scale_to 或 pan_x/pan_y。"""
    def prop(*candidates):
        for c in candidates:
            m = getattr(kf_enum, c, None)
            if m is not None:
                return m
        return None

    if not motion:
        return
    if "scale_to" in motion:
        p = prop("uniform_scale", "scale_x")
        if p is None:
            warn("关键帧属性 uniform_scale/scale_x 不存在，跳过缩放动势")
            return
        seg.add_keyframe(p, 0, motion.get("scale_from", 1.0))
        seg.add_keyframe(p, dur, motion["scale_to"])
        if p.name == "scale_x":  # 无 uniform_scale 时补 y
            py = prop("scale_y")
            if py:
                seg.add_keyframe(py, 0, motion.get("scale_from", 1.0))
                seg.add_keyframe(py, dur, motion["scale_to"])
    for axis in ("x", "y"):
        key = f"pan_{axis}"
        if key in motion:
            p = prop(f"position_{axis}", f"transform_{axis}")
            if p is None:
                warn(f"关键帧属性 position_{axis} 不存在，跳过平移动势")
                continue
            seg.add_keyframe(p, 0, 0.0)
            seg.add_keyframe(p, dur, motion[key])


def add_mask(seg, mask: dict, MaskType):
    if not mask:
        return
    mt = enum_lookup(MaskType, mask.get("type", "圆形"))
    if mt is None:
        return
    kwargs = {k: mask[k] for k in ("center_x", "center_y", "size", "rotation", "feather", "round_corner") if k in mask}
    try:
        seg.add_mask(mt, **kwargs)
    except Exception as e:
        warn(f"加蒙版失败: {e}")


def make_video_segment(draft, path, start, end, source_start=None, mute=False, clip=None):
    from pyJianYingDraft import ClipSettings
    span = end - start
    tr = draft.Timerange(start, span)
    mat = draft.VideoMaterial(path)
    if source_start is not None and us(source_start) + span <= mat.duration:
        src = draft.Timerange(us(source_start), span)
    elif mat.duration < span:
        # 素材比目标区间短：用整段素材自动慢放填满（source+target 同时指定时速度自动计算）
        warn(f"{os.path.basename(path)} 时长 {mat.duration/SEC:.1f}s < 区间 {span/SEC:.1f}s，已自动慢放适配")
        src = draft.Timerange(0, mat.duration)
    else:
        if source_start is not None:
            warn(f"{os.path.basename(path)} source_start 越界，已改从头截取")
        src = draft.Timerange(0, span)
    cs = ClipSettings(**clip) if clip else None
    kwargs = {"source_timerange": src}
    if cs is not None:
        kwargs["clip_settings"] = cs
    try:
        seg = draft.VideoSegment(path, tr, volume=0.0 if mute else 1.0, **kwargs)
    except TypeError:  # 旧版本无 volume 参数
        seg = draft.VideoSegment(path, tr, **kwargs)
        if mute:
            warn(f"当前 pyJianYingDraft 版本不支持 volume 参数，请在剪映中手动静音: {os.path.basename(path)}")
    return seg


def make_text_segment(draft, item, start, end):
    from pyJianYingDraft import TextStyle, ClipSettings, FontType
    tr = draft.Timerange(start, end - start)
    style = TextStyle(size=item.get("size", 8.0), color=tuple(item.get("color", [1, 1, 1])),
                      align=1, auto_wrapping=False)
    cs = ClipSettings(transform_x=item.get("x", 0.0), transform_y=item.get("y", 0.0))
    font = enum_lookup(FontType, item.get("font", "")) if item.get("font") else None
    kwargs = dict(style=style, clip_settings=cs)
    if font is not None:
        kwargs["font"] = font
    text = item["text"]
    if item.get("border_color") is not None:
        try:
            from pyJianYingDraft import TextBorder
            kwargs["border"] = TextBorder(color=tuple(item["border_color"]))
        except Exception:
            warn("当前版本不支持 TextBorder，描边已跳过")
    try:
        return draft.TextSegment(text, tr, **kwargs)
    except TypeError as e:
        warn(f"TextSegment 参数不兼容({e})，改用最简样式")
        return draft.TextSegment(text, tr, style=style, clip_settings=cs)


def add_text_anims(seg, item, TextIntro, TextOutro):
    for key, enum_cls in (("anim_in", TextIntro), ("anim_out", TextOutro)):
        if item.get(key):
            m = enum_lookup(enum_cls, item[key])
            if m is not None:
                try:
                    seg.add_animation(m)
                except Exception as e:
                    warn(f"文字动画 {item[key]} 添加失败: {e}")


def validate(data: dict) -> tuple[list, list]:
    """返回 (可用决策, TODO 清单)。校验必填字段、素材存在、同类型时间重叠。"""
    todos, usable = [], []
    proj = data.get("project", {})
    for key in ("draft_name", "width", "height", "host_video"):
        if key not in proj:
            sys.exit(f"[错误] project.{key} 缺失")
    if not os.path.exists(proj["host_video"]):
        sys.exit(f"[错误] 口播视频不存在: {proj['host_video']}")

    by_type: dict[str, list] = {}
    for i, d in enumerate(data.get("decisions", [])):
        t = d.get("type")
        if t not in ("broll", "keyword", "card", "host_focus", "film_transition", "overlay", "effect", "filter", "subtitles"):
            warn(f"decisions[{i}] 未知类型 '{t}'，跳过")
            continue
        mat = d.get("material") or d.get("bg_material")
        if isinstance(mat, str) and mat.startswith("TODO:"):
            todos.append(f"decisions[{i}] ({t} @ {d.get('start', d.get('at'))}): {mat[5:]}")
            continue
        if mat and not os.path.exists(mat):
            warn(f"decisions[{i}] 素材不存在，跳过: {mat}")
            continue
        if t == "film_transition":
            at = us(d["at"]); dur = us(d.get("duration", "0.5s"))
            d["_start"], d["_end"] = max(0, at - dur // 2), max(0, at - dur // 2) + dur
        elif t != "subtitles":
            d["_start"], d["_end"] = us(d["start"]), us(d["end"])
            if d["_end"] <= d["_start"]:
                warn(f"decisions[{i}] end <= start，跳过")
                continue
        by_type.setdefault(t, []).append(d)
        usable.append(d)

    for t, items in by_type.items():
        # 文字类由动态轨道池处理重叠；特效/滤镜/字幕在独立轨道
        if t in ("effect", "filter", "subtitles", "keyword", "card"):
            continue
        items.sort(key=lambda x: x["_start"])
        for a, b in zip(items, items[1:]):
            if b["_start"] < a["_end"]:
                sys.exit(f"[错误] 两个 {t} 条目时间重叠: {a['_start']/SEC:.1f}s-{a['_end']/SEC:.1f}s 与 {b['_start']/SEC:.1f}s 起。同轨片段不能重叠，请调整区间。")
    return usable, todos


def build(data: dict, draft_folder: str) -> None:
    import pyJianYingDraft as draft
    from pyJianYingDraft import (TrackType, KeyframeProperty, MaskType, IntroType,
                                 TextIntro, TextOutro,
                                 VideoSceneEffectType, FilterType)

    usable, todos = validate(data)
    proj = data["project"]
    folder = draft.DraftFolder(draft_folder)
    script = folder.create_draft(proj["draft_name"], proj["width"], proj["height"])

    tracks = [("口播", TrackType.video, 1), ("B-roll", TrackType.video, 2),
              ("强调", TrackType.video, 3), ("叠加层", TrackType.video, 4),
              ("转场层", TrackType.video, 5)]
    for name, tt, idx in tracks:
        script.add_track(tt, name, relative_index=idx)

    # 文字轨道池：卡片多行文字同屏保留必然在时间上重叠，重叠时自动开新轨
    text_tracks: list[tuple[str, list]] = []  # (轨道名, [(start,end),...])

    def add_text_to_pool(seg, start, end):
        for name, intervals in text_tracks:
            if all(end <= s or start >= e for s, e in intervals):
                intervals.append((start, end))
                script.add_segment(seg, name)
                return
        name = f"文字{len(text_tracks) + 1}"
        script.add_track(TrackType.text, name, relative_index=10 + len(text_tracks))
        text_tracks.append((name, [(start, end)]))
        script.add_segment(seg, name)

    # 口播底层
    host = proj["host_video"]
    host_mat = draft.VideoMaterial(host)
    host_seg = draft.VideoSegment(host_mat, draft.Timerange(0, host_mat.duration))
    script.add_segment(host_seg, "口播")

    def screen_mix(seg):
        """滤色混合模式仅 GitHub 版 pyJianYingDraft 支持（PyPI 0.2.x 无）。"""
        try:
            from pyJianYingDraft import MixModeType
            seg.set_mix_mode(MixModeType.滤色)
        except Exception:
            warn("当前 pyJianYingDraft 版本不支持混合模式，请在剪映中手动把叠加层/转场层片段设为「滤色」"
                 "（或安装 GitHub 版: pip install git+https://github.com/GuanYixuan/pyJianYingDraft.git）")

    for d in usable:
        t = d["type"]
        if t == "broll":
            seg = make_video_segment(draft, d["material"], d["_start"], d["_end"],
                                     source_start=d.get("source_start"), mute=d.get("mute", True))
            add_keyframes(seg, d.get("motion"), d["_end"] - d["_start"], KeyframeProperty)
            add_mask(seg, d.get("mask"), MaskType)
            if d.get("anim_in"):
                m = enum_lookup(IntroType, d["anim_in"])
                if m is not None:
                    seg.add_animation(m)
            script.add_segment(seg, "B-roll")

        elif t == "host_focus":
            clip = {"transform_x": d.get("x", 0.0), "transform_y": d.get("y", 0.0),
                    "scale_x": d.get("scale_from", 1.0), "scale_y": d.get("scale_from", 1.0)}
            seg = make_video_segment(draft, host, d["_start"], d["_end"],
                                     source_start=d["_start"] / SEC, mute=True, clip=clip)
            add_mask(seg, d.get("mask"), MaskType)
            if d.get("scale_to"):
                add_keyframes(seg, {"scale_from": d.get("scale_from", 1.0), "scale_to": d["scale_to"]},
                              d["_end"] - d["_start"], KeyframeProperty)
            script.add_segment(seg, "强调")

        elif t == "keyword":
            seg = make_text_segment(draft, d, d["_start"], d["_end"])
            add_text_anims(seg, d, TextIntro, TextOutro)
            add_text_to_pool(seg, d["_start"], d["_end"])

        elif t == "card":
            if d.get("bg_material"):
                clip = {"transform_x": d.get("bg_x", 0.0), "transform_y": d.get("bg_y", 0.0),
                        "scale_x": d.get("bg_scale", 1.0), "scale_y": d.get("bg_scale", 1.0)}
                bg = make_video_segment(draft, d["bg_material"], d["_start"], d["_end"], mute=True, clip=clip)
                add_keyframes(bg, d.get("motion"), d["_end"] - d["_start"], KeyframeProperty)
                script.add_segment(bg, "强调")
            stagger = us(d.get("line_stagger", "0.8s"))
            spacing = d.get("line_spacing", 0.12)
            for i, line in enumerate(d.get("lines", [])):
                start = min(d["_start"] + i * stagger, d["_end"] - SEC // 2)
                item = dict(d, text=line, y=d.get("y", 0.0) + i * spacing)
                seg = make_text_segment(draft, item, start, d["_end"])
                add_text_anims(seg, d, TextIntro, TextOutro)
                add_text_to_pool(seg, start, d["_end"])

        elif t in ("overlay", "film_transition"):
            track = "叠加层" if t == "overlay" else "转场层"
            seg = make_video_segment(draft, d["material"], d["_start"], d["_end"], mute=True,
                                     clip={"alpha": d.get("alpha", 1.0)})
            screen_mix(seg)
            fade = us(d.get("fade", "0.3s")) if t == "overlay" else 0
            if fade:
                p = getattr(KeyframeProperty, "alpha", None)
                if p is not None:
                    dur = d["_end"] - d["_start"]
                    a = d.get("alpha", 1.0)
                    for tt_, v in ((0, 0.0), (fade, a), (dur - fade, a), (dur, 0.0)):
                        seg.add_keyframe(p, tt_, v)
            script.add_segment(seg, track)

        elif t == "effect":
            m = enum_lookup(VideoSceneEffectType, d["name"])
            if m is not None:
                if not any(tr[0] == "特效" for tr in tracks):
                    script.add_track(draft.TrackType.effect, "特效")
                    tracks.append(("特效", None, None))
                script.add_effect(m, draft.Timerange(d["_start"], d["_end"] - d["_start"]),
                                  track_name="特效", params=d.get("params"))

        elif t == "filter":
            m = enum_lookup(FilterType, d["name"])
            if m is not None:
                if not any(tr[0] == "滤镜" for tr in tracks):
                    script.add_track(draft.TrackType.filter, "滤镜")
                    tracks.append(("滤镜", None, None))
                script.add_filter(m, draft.Timerange(d["_start"], d["_end"] - d["_start"]),
                                  track_name="滤镜", intensity=d.get("intensity", 100))

    if proj.get("srt") and os.path.exists(proj["srt"]):
        try:
            script.import_srt(proj["srt"], track_name="字幕")
        except Exception as e:
            warn(f"字幕导入失败: {e}")

    script.save()
    print(f"\n✅ 草稿已生成: {proj['draft_name']}（在剪映中打开；列表未刷新时进出一次任意草稿）")
    if todos:
        print("\n⏳ 以下素材待补充（TODO 占位，已跳过）：")
        for x in todos:
            print("  - " + x)
    if WARNINGS:
        print(f"\n⚠️ 共 {len(WARNINGS)} 条警告，见上方输出。需要手动在剪映中补齐对应效果。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("decisions", help="decisions.json 路径")
    ap.add_argument("--draft-folder", help="剪映草稿文件夹（形如 .../JianyingPro Drafts）")
    ap.add_argument("--check", action="store_true", help="只校验不生成")
    args = ap.parse_args()

    with open(args.decisions, encoding="utf-8") as f:
        data = json.load(f)

    if args.check:
        usable, todos = validate(data)
        print(f"校验通过：{len(usable)} 条可用决策，{len(todos)} 条 TODO，{len(WARNINGS)} 条警告")
        for x in todos:
            print("  TODO - " + x)
        return

    if not args.draft_folder:
        sys.exit("[错误] 需要 --draft-folder（或先 --check 校验）")
    try:
        import pyJianYingDraft  # noqa: F401
    except ImportError:
        sys.exit("[错误] 未安装 pyJianYingDraft: pip install pyJianYingDraft")
    build(data, args.draft_folder)


if __name__ == "__main__":
    main()
