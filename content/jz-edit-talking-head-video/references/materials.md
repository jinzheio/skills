# 素材获取

三个通道按优先级使用：本地素材库（最快、质量稳定）→ 免版权素材站（全自动但少电影感）→ AI 推荐片单（最贴合但需用户手动下载）。每个 B-roll 需求先过通道 1，未命中再走 2 或 3；必须要电影质感的段落（金句、强情绪）直接走通道 3。

## 通道 1：本地素材库

路径来自 `~/.config/skills/jz-edit-talking-head-video/config.yml` 的 `material_library`。推荐目录约定：

```text
<素材库>/
  emotions/        # 按情绪分类的电影片段
    痛苦/  喜悦/  沉思/  挣扎/  释然/  ...
  transitions/     # 胶片烧灼、漏光素材
  overlays/        # 白点粒子、尘埃、光斑
  backgrounds/     # 卡片用的动态背景
  index.csv        # 可选：filename,tags,source,notes
```

检索方式：有 `index.csv` 时按 tags 匹配情绪标签；没有时按目录名 + 文件名匹配。命中多个时用 `ffprobe` 看时长和分辨率，优先选 ≥1080p、时长 ≥ 需求时长的。

用户没有素材库时，建议按上述结构建一个——每次做视频攒下来的素材放进去，库会越用越好用。

## 通道 2：免版权素材站

```bash
python3 <skill-dir>/scripts/fetch_stock.py "man thinking silhouette" -n 3 -o work/materials/
```

- API key 放 `~/.config/skills/jz-edit-talking-head-video/.env`：`PEXELS_API_KEY=...`（[申请](https://www.pexels.com/api/)，免费）、`COVERR_API_KEY=...`（[申请](https://coverr.co/developers)，可选）、`PIXABAY_API_KEY=...`（可选 fallback）。
- 关键词用**英文**，素材站英文索引远好于中文。情绪标签 → 关键词的转换示例：痛苦 → "man crying rain cinematic"；沉思 → "person window contemplating moody"；挣扎 → "silhouette struggle dark"。
- 加 "cinematic"、"moody"、"film" 等词过滤掉图库味。
- 默认 `auto` 按 Pexels → Coverr → Pixabay fallback；指定素材源可加 `--source coverr`。
- 下载后逐个用 ffprobe + 抽一帧查看，色调不统一的淘汰。Pexels/Pixabay/Coverr 许可允许商用，无需署名，但**不要**用含可识别人脸的素材做负面语境配图。

## 通道 3：AI 推荐片单

对需要电影画面的段落，直接根据你对电影的知识推荐片单，输出到 `work/materials.md`：

```markdown
## 待下载片单
| 段落 | 情绪需求 | 电影 | 场景 | 大致位置 |
|---|---|---|---|---|
| 00:12-00:15 | 痛苦/崩溃 | 《海边的曼彻斯特》 | Lee 在警局崩溃 | 约 1/3 处 |
| 00:31-00:34 | 顿悟 | 《楚门的世界》 | 楚门触到天空布景 | 结尾 |
```

- 推荐**知名**电影——用户更容易找到片源，观众也更容易被画面唤起情绪。
- 场景描述要具体到"谁在做什么"，让用户能快速定位。
- 提醒用户：电影画面用于自媒体配图属于灰色地带，各平台判定不同，商用项目建议只走通道 1/2。
- 片单素材路径在 decisions.json 里先用 `"material": "TODO:<描述>"` 占位，用户下载后填入真实路径再跑 build_draft.py（脚本遇到 TODO 会列出清单并跳过该条目，不会报错中断）。

## 特殊素材

- **胶片转场/叠加层**：素材站搜 "film burn transition"、"dust particles overlay"、"light leaks"。这类素材通常是黑底，配合滤色混合模式使用。下载一次存进本地库 `transitions/`、`overlays/`，长期复用。
- **卡片背景**：搜 "abstract background loop dark"、"paper texture"。要有缓慢动势的，不要纯静止。
