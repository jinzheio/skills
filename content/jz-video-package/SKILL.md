---
name: jz-video-package
description: 给已有口播视频做后期包装，生成剪映草稿或 Shotcut/MLT 项目：自动转录分段、标注情绪与重点词，在口播间歇插入 B-roll 情绪配图，叠加关键词放大、文字卡片、人物蒙版框选、动势关键帧、胶片转场和叠加层。当用户提到给口播/talking-head 视频加配图、加包装、加卡片、加 B-roll、生成剪映草稿或 Shotcut 项目、"视频太单调想加点效果"、模仿某个博主的视频包装风格时使用——即使用户没有明确提到剪映、Shotcut 或 pyJianYingDraft。
---

# 口播视频后期包装

输入一条口播视频，输出一个可在剪辑软件中直接打开的时间轴项目（Shotcut/MLT 或剪映草稿）：B-roll、文字卡片、蒙版、关键帧、转场、叠加层都已摆好，用户只需微调和导出。

## 为什么有效

高完成度的口播包装是公式化的：**情绪配图 + 关键词可视化 + 画面动势**。文案说到抽象概念（性格、认知、痛苦）时插入贴合情绪的电影画面让内容具象化；说到重点词时放大展示；出现对比或连续举例时用并列卡片挨个出现；所有静止素材都加缓慢缩放/移动的关键帧避免画面死板。把这套公式应用到任何口播视频上，就能得到"专业包装过"的观感。详细手法字典见 `references/design-language.md`。

## 架构：决策与执行分离

创意判断（哪里插图、插什么情绪的图、哪个词做卡片）由你完成，写入一份 `decisions.json`；草稿生成由 `scripts/build_draft.py` 确定性完成。不要手写 draft_content.json，也不要在没有决策文件的情况下直接调 pyJianYingDraft——决策文件是用户审阅和返工的界面，跳过它会让返工变成重跑全流程。

## 阶段 0——确认（一轮问题，之后按默认值推进）

1. 输入视频路径？（必需）
2. 输出后端？（`剪映草稿`或 `Shotcut/MLT`。默认：读配置 `backend`；都没有时先探测剪映草稿库——若是新版加密格式则直接推荐 Shotcut/MLT 后端，明文格式才走剪映）
3. 剪映后端时：草稿文件夹路径？（默认：读 `~/.config/skills/jz-video-package/config.yml` 的 `draft_folder`；没有则询问并写入配置。一般形如 `.../JianyingPro Drafts`）
4. 本地素材库路径？（默认：读配置 `material_library`；没有则跳过本地库通道）
5. 包装密度？（默认：`标准`——每 8~15 秒一个包装动作；`密集`——每 4~8 秒；`克制`——只在段落转折处）
6. 有没有参考风格？（默认：电影感情绪配图风格，即本 skill 内置的设计语言）

确认剪映版本：草稿生成支持剪映 5 及以上所有版本；批量自动导出仅 Windows + 剪映 ≤6；macOS 上用户需在剪映中手动打开草稿导出。提前告知，避免用户期待全自动出片。

依赖检查：`pip install pyJianYingDraft`、`ffmpeg`、转录后端（faster-whisper 或已有 srt）。

## 阶段 1——拆解输入视频

1. `ffprobe` 拿到时长、分辨率、fps。
2. 转录：`python3 scripts/transcribe.py <视频> -o work/transcript.json`（同时产出 `.srt`）。用户已有带时间戳文案或 srt 时直接用，跳过转录。
3. 抽帧看人物位置：`ffmpeg -i <视频> -vf fps=1/5 work/frames/%03d.jpg`，查看几帧，记录人物在画面中的位置和占比（蒙版框选的 center 参数要用）。
4. 写**分段表**到 `work/segments.md`：按语义把文案切成段，每段记录——起止时间、内容概括、情绪标签（喜/怒/哀/惧/痛苦/坚定/迷茫…）、重点词、结构特征（对比？连续举例？金句？转折？）。

分段表是后面所有决策的依据，必须先写下来再继续。最常见的失败模式是跳过分段表直接选素材，结果配图和语境对不上。

## 阶段 2——素材

读 `references/materials.md`。三个通道按优先级：

1. **本地素材库**——按分段表的情绪标签检索用户素材库，命中的直接引用。
2. **免版权素材站**——`python3 scripts/fetch_stock.py "<英文关键词>" -n 3 -o work/materials/`（需要 Pexels/Pixabay API key）。
3. **AI 推荐片单**——对必须要电影质感的段落，输出"电影名 + 场景描述 + 大致时间点"清单让用户自行下载，路径留空待填。

每个需要 B-roll 的段落在 `work/materials.md` 里记一行：段落时间、情绪需求、选中素材路径（或待办）。胶片转场素材、白点粒子叠加层素材也在这一步落实。

## 阶段 3——剪辑决策

读 `references/design-language.md`（手法选择规则）和 `references/draft-build.md`（decisions.json 完整 schema），写 `work/decisions.json`。要点：

- 每个决策条目 = 时间区间 + 手法类型 + 参数。手法类型：`broll`（间歇插全屏配图）、`keyword`（重点词放大）、`card`（文字卡片/并列展示）、`host_focus`（人物蒙版框选强调）、`film_transition`（胶片转场）、`overlay`（叠加层）、`effect`/`filter`（特效滤镜）、`subtitles`（字幕）。
- 静止素材必须带 `motion`（缓慢缩放或平移关键帧）——没有动势的静止画面是最大的廉价感来源。
- 密度按阶段 0 的选择控制；宁少勿滥，包装服务于文案，不抢戏。

把 decisions.json 的人话版摘要（时间轴上每个动作一行）发给用户确认后再生成草稿。

## 阶段 4——生成项目/草稿

**Shotcut/MLT 后端**（推荐；开源、明文、无版本封锁）——读 `references/mlt-build.md`：

```bash
python3 scripts/build_mlt.py work/decisions.json -o work/project.mlt
```

用户用 Shotcut 打开 project.mlt，时间轴上直接调节并导出。

**剪映后端**（仅当用户剪映是明文草稿格式，如 5.9）——读 `references/draft-build.md`：

```bash
python3 scripts/build_draft.py work/decisions.json --draft-folder "<剪映草稿文件夹>"
```

脚本会校验时间不重叠、素材文件存在、枚举名有效，然后生成草稿；保存后自动清理缺失素材引用并刷新 `draft_meta_info.json`，避免剪映草稿箱显示 `0.0B / 00:00` 或报"草稿内容已损坏"。

如果检测到剪映草稿库是新版加密格式（`draft_info.json` / `Timelines`），**不要生成旧格式草稿**——首选改用 MLT 后端；用户坚持要剪映时退而用导入包（`python3 scripts/build_import_package.py work/decisions.json -o work/import-package`，裁好 B-roll、复制字幕、生成 `timeline.csv` 供用户在剪映中手动摆放），或建议安装剪映 5.9 并关闭自动升级。

## 阶段 5——验证与交付

1. 让用户在对应软件中打开项目（Shotcut 直接打开 .mlt；剪映可能需重启刷新草稿列表），逐轨检查。
2. 明确告知哪些效果需要手动补——剪映：人物蒙版的**描边+发光**（用阴影更自然）、**金属花字**；Shotcut：srt 在「字幕」面板一键导入、蒙版羽化（加高斯模糊）、剪映特效枚举无对应需在滤镜面板自选。
3. 把 `work/` 目录（分段表、素材清单、decisions.json）留在项目里，用户改文案或换素材后可只改 decisions.json 重跑阶段 4，两个后端随时可切换。

## Reference 索引

| 你在做… | 读取 |
|---|---|
| 选手法：哪里插图、什么情绪、卡片怎么排 | `references/design-language.md` |
| 找素材：本地库约定、素材站 API、AI 片单格式 | `references/materials.md` |
| 写 decisions.json、剪映排错、pyJianYingDraft 能力边界 | `references/draft-build.md` |
| Shotcut/MLT 后端：效果映射、保真度、排错 | `references/mlt-build.md` |

## 完成前检查清单

- [ ] 分段表基于实际转录时间戳写出，情绪标签逐段标注
- [ ] 每个静止素材都有动势关键帧
- [ ] decisions.json 摘要经用户确认后才生成项目/草稿
- [ ] 后端脚本（build_mlt.py 或 build_draft.py）校验通过，无素材缺失
- [ ] 已告知用户需手动补的效果和导出方式（按所选后端）
- [ ] work/ 目录留在项目里供返工
