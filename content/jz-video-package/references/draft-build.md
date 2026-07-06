# decisions.json 与草稿生成

## decisions.json schema

```jsonc
{
  "project": {
    "draft_name": "口播包装-20260703",     // 剪映里显示的草稿名
    "width": 1080, "height": 1920,        // 与口播视频一致，竖屏 1080x1920 / 横屏 1920x1080
    "host_video": "<绝对路径>",            // 口播原片
    "srt": "work/transcript.srt"          // 可选；提供则自动导入字幕轨
  },
  "decisions": [ /* 按 start 排序的决策条目，见下 */ ]
}
```

时间值统一支持两种写法：秒数 `3.2` 或字符串 `"3.2s"` / `"1m5s"`。

### 决策条目类型

```jsonc
// broll——间歇插全屏配图（覆盖在口播上层）
{ "type": "broll", "start": "12.0s", "end": "15.5s",
  "material": "<路径或 TODO:描述>",
  "source_start": "8s",                   // 可选，素材从第几秒开始截
  "mute": true,                            // 默认 true
  "motion": { "scale_from": 1.0, "scale_to": 1.08 },   // 或 {"pan_x": 0.04} / {"pan_y": -0.03}
  "anim_in": "渐显",                       // 可选，pyJianYingDraft IntroType 名称
  "mask": { "type": "圆形", "size": 0.6, "center_x": 0, "center_y": 0, "feather": 10 } // 可选
}

// keyword——重点词放大
{ "type": "keyword", "start": "5.0s", "end": "7.2s",
  "text": "认知", "size": 12.0,            // size 为剪映字号
  "font": "宋体", "color": [1.0, 1.0, 1.0],
  "x": 0.0, "y": 0.35,                     // 位置，画面中心为 (0,0)，范围 -1~1
  "anim_in": "渐显", "anim_out": "渐隐",   // TextIntro / TextOutro 名称
  "border_color": [0,0,0]                  // 可选描边
}

// card——文字卡片（背景素材 + 多行文字逐条出现）
{ "type": "card", "start": "20s", "end": "26s",
  "bg_material": "<背景素材路径>",          // 可选；缺省则纯文字卡
  "bg_scale": 0.55, "bg_x": -0.4, "bg_y": 0,  // 背景片的大小与位置
  "lines": ["Twitter", "Uber", "OpenSea"],
  "line_stagger": "0.8s",                  // 每行出现间隔
  "size": 8.0, "font": "宋体", "color": [1,1,1],
  "x": 0.35, "y": 0.0, "line_spacing": 0.12,
  "anim_in": "向上滑动", "motion": { "pan_x": -0.02 } }

// host_focus——复制口播片段到上层轨，加蒙版+放大关键帧
{ "type": "host_focus", "start": "30s", "end": "34s",
  "mask": { "type": "圆形", "size": 0.55, "center_x": 0, "center_y": -100, "feather": 6 },
  "scale_from": 1.0, "scale_to": 1.12,
  "x": 0.0, "y": 0.0 }                     // 可把框选后的人物挪到一侧

// film_transition——胶片素材叠在剪辑点上
{ "type": "film_transition", "at": "18s", "duration": "0.5s",
  "material": "<胶片素材路径>" }

// overlay——叠加层（白点/尘埃/光斑，滤色混合）
{ "type": "overlay", "start": "20s", "end": "26s",
  "material": "<路径>", "alpha": 0.7, "fade": "0.3s" }

// effect / filter——独立轨道上的画面特效或滤镜
{ "type": "effect", "start": "0s", "end": "3s", "name": "胶片闪切", "params": [50, null, 80] }
{ "type": "filter", "start": "0s", "end": "50s", "name": "哈苏蓝", "intensity": 60 }
```

## 轨道布局（build_draft.py 自动创建，自下而上）

1. `口播`——host_video 整条
2. `B-roll`——broll 条目
3. `强调`——host_focus 复制层、card 背景
4. `文字`——keyword、card 文字
5. `叠加层`——overlay、film_transition（滤色混合）
6. `字幕`——srt 导入（文本轨）
7. `特效` / `滤镜`——独立特效滤镜轨

## pyJianYingDraft 能力边界（写决策前必读）

- **草稿生成**支持剪映 5+ 所有版本；**模板模式**（读已有草稿、提取花字/贴纸 resource_id）仅剪映 ≤5.9（6+ 草稿加密）；**自动导出**仅 Windows + 剪映 ≤6。macOS 只生成草稿，用户手动导出。
- 剪映 6+ 的本地草稿通常使用 `draft_info.json` + `Timelines/` 加密格式。pyJianYingDraft 生成的是明文 `draft_content.json` 旧格式；在这类草稿库里会被剪映判为“草稿内容已损坏”。`build_draft.py` 会检测并拒绝生成，改用 `build_import_package.py`。
- 动画/特效/滤镜/蒙版/字体都用**中文枚举名**（如 `IntroType.渐显`、`MaskType.圆形`、`FontType.宋体`）。脚本用 `from_name` 容错匹配，名字不存在时**警告并跳过该效果**（草稿其余部分仍生成）。不确定名字时宁可留空，让用户在剪映里手动加。
- 视频片段**没有原生描边/发光**参数——host_focus 的描边发光让用户在剪映里补（选中片段 → 蒙版 → 描边；发光用阴影更自然）。
- 花字/气泡需要 resource_id（模板模式提取，或用户从旧草稿里给）；拿不到时用 TextStyle 描边+阴影近似。
- **滤色混合模式**（overlay/film_transition 用）在 PyPI 0.2.x 不可用，脚本会警告；用户可在剪映中手动设置，或安装 GitHub 版：`pip install git+https://github.com/GuanYixuan/pyJianYingDraft.git`。
- 曲线变速、特效参数关键帧不支持。
- 文本关键帧只支持位置/大小类属性。

## 排错

- **草稿在剪映里看不到**：进入再退出任一已有草稿，或重启剪映刷新列表。
- **草稿箱显示 `0.0B / 00:00`，打开像空草稿**：新版剪映列表页依赖 `draft_meta_info.json` 里的时长、素材大小、素材列表和封面。`build_draft.py` 会在 `script.save()` 后自动刷新这些字段，并从口播视频抽一帧生成 `draft_cover.jpg`。如果仍显示为空，先重启剪映；再检查草稿目录里的 `draft_content.json` 是否有轨道、`draft_meta_info.json` 的 `tm_duration` 是否大于 0。
- **提示“无法打开草稿 / 草稿内容已损坏”**：先检查 `draft_content.json` 里是否有片段引用了不存在的 material。`build_draft.py` 会自动删除这类缺失的 `extra_material_refs`；常见来源是某些 pyJianYingDraft 版本给文本/字幕写入字体或样式引用，但没有把对应素材写进 `materials`。
- **打开崩溃或片段黑屏**：多为素材路径失效（草稿里存的是绝对路径，素材移动后即失效）——素材应放固定目录再生成草稿。
- **`from_name` 找不到枚举**：`python3 -c "from pyJianYingDraft import IntroType; print([m.name for m in IntroType])"` 列出当前版本可用名称。
- **时间重叠报错**：build_draft.py 校验同轨片段不得重叠；调整 decisions.json 的区间，或把重叠条目换到不同手法类型（不同轨道）。
