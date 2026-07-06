# MLT/Shotcut 后端

`scripts/build_mlt.py` 与 build_draft.py 消费**同一份 decisions.json**，生成 Shotcut（及 Kdenlive/melt）可打开的明文 MLT XML 项目。当用户的剪映是新版加密草稿格式、或用户想要开源工具链时，用这个后端。

```bash
python3 scripts/build_mlt.py work/decisions.json -o work/project.mlt
```

用户用 [Shotcut](https://shotcut.org)（免费开源，macOS/Windows/Linux）打开 project.mlt，所有轨道、片段、动势、蒙版、文字都在时间轴上，可拖拽调节后直接导出 mp4——不存在剪映的加密/导出限制。

## 效果映射表

| decisions.json | MLT 实现 | 保真度 |
|---|---|---|
| broll + motion | affine filter，transition.rect 关键帧（缩放/平移） | 完整 |
| broll.mask 圆形 | qtcrop filter（circle=1，透明填充） | 无羽化（Shotcut 里可补高斯模糊） |
| keyword / card 文字 | 透明 color producer + dynamictext filter（字体/描边/对齐） | 无花字；动画用透明度淡入替代 |
| card 逐行出现 | 每行独立文字片段，自动开新文字轨 | 完整 |
| host_focus | 复制口播片段 + qtcrop 蒙版 + affine 放大关键帧 | 描边发光需手动补 |
| overlay / film_transition | cairoblend_mode filter（mode=screen 滤色）+ brightness alpha 淡入淡出 | 完整 |
| anim_in（剪映动画枚举） | 统一降级为 0.4s 透明度淡入 | 近似 |
| effect / filter（剪映特效枚举） | 无对应，警告后跳过 | 需在 Shotcut 滤镜面板手动加 |
| subtitles (srt) | 不自动导入；提示用户在 Shotcut「字幕」面板一键导入 | 手动一步 |
| 素材比区间短 | 无自动慢放，从头截取并警告 | Shotcut 里对片段改速度补足 |

## 结构约定

- 轨道自下而上：background、口播、B-roll、强调、叠加层、转场层、文字N（按重叠自动增轨）。
- 每个时间轴片段一个独立 `<chain>`/`<producer>`，filter 挂在片段自己的 chain 上，互不影响。
- tractor 里每条上层视频轨配 `mix`（音频）+ `frei0r.cairoblend`（画面合成）transition。
- 时间用时钟串（`00:00:03.200`），素材用绝对路径——**移动素材后需重新生成**（或在 Shotcut 打开时按提示重定位）。
- B-roll 静音通过 `audio_index=-1` 实现。

## 排错

- **Shotcut 打开后轨道为空**：检查 .mlt 里素材绝对路径在当前机器是否存在。
- **文字字体不对**：dynamictext 的 `family` 需要本机安装的字体名（宋体在 macOS 是 `Songti SC`）；Shotcut 里选中文字片段可改。
- **上层轨道不透明**（B-roll 盖不住/文字有黑底）：确认 tractor 里有对应 `frei0r.cairoblend` transition 且 `disable=0`；文字 producer 的 `mlt_image_format` 必须是 `rgba`。
- **验证渲染**：装有 melt 时可 `melt project.mlt -consumer avformat:out.mp4`（Shotcut 自带 melt，在其安装目录内）。
- 属性文档：<https://mltframework.org/plugins/>（FilterDynamictext / FilterQtcrop / FilterAffine）。
