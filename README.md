# Anima 中文提示词转换器

给 [ComfyUI](https://www.comfy.org/) 本地部署的 **Anima** 模型写提示词用的小工具：粘贴一段中文描述，输出规范化的 Danbooru tag，按「动作姿势 / 场景背景 / 补充细节」三组分开。

**完全离线、零第三方依赖、不调用任何大模型。**

[Anima](https://huggingface.co/circlestone-labs/Anima) 是 CircleStone Labs / Comfy Org 的二次元文生图模型，在 Danbooru 标签体系上训练。它同时接受 Danbooru tag、自然语言和两者混合，但用 **模型真正认识的 tag** 效果最稳 —— 这个工具解决的就是「中文 → 有效 tag」这一段。

![折叠态](docs/界面-折叠.png)

<details>
<summary>展开分类的样子</summary>

![展开态](docs/界面-展开分类.png)

</details>

## 三条铁律

1. **只翻译，不脑补。** 你写什么就转什么。没提到的概念，一个字都不会被加进去。
2. **不编造。** 中文词在词典里找不到对应 tag 时，原样列进「未命中」区，不猜、不替换。
3. **不联网。** 没有任何网络请求。

## 特性

- **三分类输出**：动作姿势 / 场景背景 / 补充细节
- **折叠 / 展开**：折叠给完整 prompt，展开追加分组明细
- **每张卡片自带复制按钮**，边框显示该卡的 tag 数与字数
- **词典经真实校验**：331 条英文 tag 全部逐条比对 Anima 官方 tag 表，0 条在表外
- **两层词库**：手工核心词典（精确）＋ 33 万条扩展词库（覆盖长尾），扩展命中的 tag 带 `~` 标记
- **中英混输**：英文 tag 若词典认识会自动归到对应分组
- **零依赖**：仅用 Python 标准库（`tkinter` / `re` / `json` / `sqlite3`）
- **可打包成 exe**：`python tools/build_exe.py`

## 快速开始

### 1. 环境

- Python 3.9+（需含 `tkinter`，Windows 官方安装包默认自带）
- 无需 `pip install` 任何东西

### 2. 两个数据文件（一个随仓库带，一个要自备）

程序有两层词库，依赖两个不同的数据文件——**授权情况不一样，别搞混**：

| 文件 | 作用 | 授权 | 是否随仓库 |
| --- | --- | --- | --- |
| `data/tags.sqlite` | **扩展词库**，33 万条 Danbooru 中英对照，覆盖核心词典之外的长尾词 | MIT | ✅ 已包含 |
| `data/Anima-preview.csv` | **Anima 官方 tag 表**，用来校验 tag 是否被模型认识 | GPL-3.0 | ❌ 需自备 |

**关于 `Anima-preview.csv`**：它出自 GPL-3.0 许可的 [comfyui-good-anima](https://github.com/ComfyNodePRs/PR-Comfyui-Anima-tools-a0fe04bd) 技能包，打包进来会给本项目引入 GPL 传染，所以不放仓库。

工具会按这个顺序自动找它：

1. 命令行的 `--tags <路径>`
2. 环境变量 `ANIMA_TAGS`
3. `data/Anima-preview.csv`（推荐放这里）
4. 本机常见的 ComfyUI 技能包目录

把文件放进 `data/` 即可。

> **没有它也能用**，但**扩展词库会被自动关闭**，只保留核心词典那 331 条。
> 这是刻意的：扩展词库里的 tag 必须拿 Anima 表校验过才能进 prompt，
> 没有校验依据时宁可少给，也不把模型不认识的死词塞进去。

### 3. 运行

```bash
python anima_prompt.py
```

窗口里：粘贴中文 → 点「转换」→ 用卡片上的复制按钮取结果。`Ctrl+Enter` 触发转换，`Esc` 关窗口。

也可以用命令行：

```bash
python anima_prompt.py "一个女孩坐在教室窗边，回头看镜头微笑，午后阳光照进来，穿着校服，长发，逆光"
```

## 输出长什么样

输入：

```
一个女孩站在天台边缘，风吹起短发，手里拿着饮料，夜空中星星闪烁，霓虹灯的光打在她脸上
```

折叠态（默认）给完整 prompt：

```
masterpiece, very aesthetic, best quality, score_9, score_8, highres, absurdres, newest,
1girl, standing, holding_drink, rooftop, wind, starry sky, short hair, sparkle, neon lights
```

展开态追加分组明细：

| 分组 | 内容 |
| --- | --- |
| 动作姿势 | `1girl, standing, holding_drink` |
| 场景背景 | `rooftop, wind, starry sky` |
| 补充细节 | `short hair, sparkle, neon lights` |
| 未命中 | `边缘`、`吹起` |

## 分类口径

分类不看主观感觉，看 **Danbooru 官方 tag group**：

| 分组 | 收录内容 |
| --- | --- |
| 动作姿势 | 站坐躺跪、手臂手部、腿部、运动、动作产物、表情 |
| 场景背景 | 地点、房间、家具、天气、时间、环境物 |
| 补充细节 | 光影、服装、发型外貌、镜头视角、画质风格 |

`standing` / `sitting` 属 Action，`classroom` / `window` 属 Setting —— 这是 Danbooru 的既定分组。

## tag 是校验过的（这个项目最值钱的部分）

词典里 **331 条**英文 tag，全部逐条比对过 Anima 官方 tag 表：

```bash
python tools/check_tags.py
# 期望输出：不在 tag 表里的：0
```

**为什么必须校验**：Anima 的表是**筛选过的**，和完整 Danbooru 词表（33 万条）不是一回事。按常识写会踩大量坑：

| 常识写法 | Anima 表里有吗 | 实际应该用 |
| --- | --- | --- |
| `sofa` | 没有 | `couch` |
| `bangs` | 没有 | `blunt_bangs` / `parted_bangs` |
| `open_eyes` | 没有 | —— |
| `hand on hip` | 没有 | `hand_on_own_hip` |
| `swimming pool` | 没有 | `pool` |
| `from front` | 没有 | —— |
| `quiet` / `warm` / `romantic` / `cute` | **整个氛围词类别都没有** | —— |

本项目第一版词典按常识写了 340 条，拿去比对发现 **44 条 Anima 根本不认识**（13%）。靠 `tools/suggest_fixes.py` 反查候选、逐条替换或删除，才收敛到 0。**所以你拿到的每个 tag，模型都认识。**

### 格式约定

Anima 官方规范是**小写 + 空格**（不写下划线）：

```
looking at viewer     ✅
looking_at_viewer     ❌
```

工具输出的就是这个形式。

## 两层词库

程序按两层匹配，越靠前越权威：

| 层 | 规模 | 来源 | 标记 |
| --- | --- | --- | --- |
| **核心词典** | 331 条 | `anima_prompt.py` 里手工维护，逐条比对过 Anima 表 | 无标记 |
| **扩展词库** | 334048 行 / 330744 个英文 tag | `data/tags.sqlite`，来自 ffdkj 的中英对照表 | 输出带 `~` |

扩展层补的是核心词典没覆盖的长尾词。实测：

```
输入：双马尾少女穿着和服在樱花树下弹吉他，戴着耳机，午后的阳光洒落

补充细节：twintails, kimono, playing_guitar ~, earphones ~, sunlight
```

`twintails` / `kimono` / `sunlight` 来自核心词典，`playing_guitar` / `earphones` 来自扩展词库（带 `~`）。

### 扩展层只收 Anima 认识的 tag

33 万条里，绝大多数 tag 是 Anima **没见过**的。实测覆盖率：

| post_count 段 | 在 Anima 表内的比例 |
| --- | --- |
| ≥ 10000 | **98.7%** |
| ≥ 5000 | **98.4%** |
| ≥ 1000 | 93.1% |
| ≥ 100 | 27.1% |
| 全部 | 6.5% |

所以扩展层拿到的每个 tag 都要过一遍 Anima 表，**不在表里的一律丢弃**。这是它和核心词典共用同一条底线：进 prompt 的 tag，模型必须认识。

也正因如此，**没有 `Anima-preview.csv` 时扩展层会自动关闭**——没有校验依据，宁可只用核心词典，也不赌运气。

复验覆盖率：

```bash
python tools/stats_coverage.py
```

### 重建扩展词库

`data/tags.sqlite` 是从 ffdkj 的原始数据加工来的（建索引 + 拆分多译名）：

```bash
python tools/build_tagdb.py                    # 用默认路径
python tools/build_tagdb.py --src <tag.sqlite> # 指定源文件
```

### 再补自己的映射

扩了两层还是会漏。编辑 `data/user_dict.json` 手工补：

```json
{
  "中文词": ["分组", "english tag"],
  "温暖的感觉": ["补充细节", "warm lighting"],
  "猫娘": "cat girl"
}
```

只写英文 tag 字符串时默认归入「补充细节」。改完重启工具生效。

**加之前建议先验一下**：不在 Anima 表里的 tag 写了也白写。

```bash
python tools/check_tags.py        # 校验核心词典
python tools/suggest_fixes.py     # 为表外的 tag 反查近似候选
python tools/stats_coverage.py    # 统计扩展词库的 Anima 覆盖率
```

## 打包成 exe

```bash
python tools/build_exe.py                    # 打包到 dist/
python tools/build_exe.py --onefile          # 单文件（启动会慢几秒）
python tools/build_exe.py --clean            # 先清掉 build/dist
```

产物是 `dist/Anima提示词转换器/`，约 60 MB，含 Python 运行时和数据：

```
dist/Anima提示词转换器/
├─ Anima提示词转换器.exe     双击即用，不需要装 Python
└─ data/
   ├─ tags.sqlite           扩展词库
   └─ Anima-preview.csv     若本机有就一并复制（启用扩展层校验）
```

用 onedir 而非 onefile：onefile 每次启动都要把几十 MB 解压到临时目录，冷启动要好几秒；onedir 是普通目录启动，快得多。

**打包版会写一份 `anima_debug.txt`**（就在 exe 同级目录）。这是刻意留的：exe 是 `--windowed`，没有 stderr，一旦数据文件放错位置就完全静默——只表现为「扩展层用不了」。日志会写清它实际找到了哪些路径：

```
frozen  = True
exe     = ...\Anima提示词转换器.exe
tag 表  = ...\data\Anima-preview.csv
扩展库  = ...\data\tags.sqlite  exists=True
```

排查完删掉即可。源码运行时不写，除非设了 `ANIMA_DEBUG=1`。

## 项目结构

```
anima-prompt-tool/
├─ anima_prompt.py          # 主程序：核心词典 + 匹配引擎 + 界面
├─ tagdb.py                 # 扩展词库查询层（SQLite + 热数据缓存）
├─ LICENSE                  # MIT
├─ README.md
├─ assets/
│  ├─ icon.ico              # 应用图标
│  └─ icon.png
├─ data/
│  ├─ tags.sqlite           # 扩展词库（334048 行，33 万中英对照）
│  ├─ user_dict.json        # 你自己的补充映射
│  └─ Anima-preview.csv     # 需自备，见上文
├─ docs/                    # 界面截图 + 词典收敛记录
└─ tools/
   ├─ build_tagdb.py        # 加工原始对照表 -> data/tags.sqlite
   ├─ build_exe.py          # 打包成 exe
   ├─ check_tags.py         # 校验核心词典 tag 是否都在 Anima 表内
   ├─ suggest_fixes.py      # 为表外的 tag 反查候选
   ├─ stats_coverage.py     # 统计扩展词库的 Anima 覆盖率
   ├─ _tagtable.py          # tag 表定位器（多脚本共用）
   ├─ make_icon.py          # 生成应用图标
   ├─ ui_shot.py            # 抓界面截图（PrintWindow，被遮挡也能抓）
   └─ verify_shortcut.py    # 验证桌面快捷方式真能启动
```

如果想知道**词典为什么长成现在这样**，看 [`docs/词典收敛记录.md`](docs/词典收敛记录.md) —— 里面有 44 条 tag 的逐条取舍。

## 界面设计口径

不是随手配色，是按「长时间阅读中文文本」+「避免 LLM 默认审美」两条约束走的：

- **浅色冷灰基底**。不用纯黑，也不在浅色页里突然插深色块。文字色 `#1B2733` 比纯黑柔和。
- **只有一个强调色**：深青绿 `#0F5257`。分类卡的三个色是它的深浅变体，不引入第二个色相。
- **没有渐变、没有 AI 紫蓝**。「紫蓝渐变 + Inter + slate-900」是最典型的 AI 设计指纹，刻意避开。
- **字体分级**：中文用微软雅黑 UI，tag 与数字用 Consolas 等宽。
- **自绘控件**：系统 `Checkbutton` 会带一个 Web 蓝方块选择器，与配色打架，所以开关、按钮、卡片全部用 Canvas 画（圆角走平滑多边形近似）。

想换配色，改 `anima_prompt.py` 顶部的 `C` 字典，一个色值全局生效。

## 已知边界

- 中文分词靠**最长匹配**，不是真正的分词器。罕见表达会被拆成「部分命中 + 未命中」，未命中区会如实报出来。
- 复合短语如「天台边缘」只能命中「天台」，「边缘」进未命中。要精确匹配就往 `user_dict.json` 里加整条。
- 核心词典 331 条覆盖高频视觉概念；再往外的长尾词靠扩展词库，但扩展层只收 Anima 认识的 tag，所以低频段覆盖有限（见上文覆盖率表）。
- 扩展层对译名严格精确匹配，所以「午后」查不到（表里的译名是「下午」）。别名要靠 `user_dict.json` 补。
- 氛围词（安静的、温馨的、浪漫的）在 Anima 表里没有对应 tag，会落进未命中。Anima 支持自然语言，这类描述适合用英文短句写在 prompt 末尾。
- 窗口尺寸和位置不做记忆。

## 资源占用

实测开销（`data/tags.sqlite` 35 MB，334048 行）：

| 阶段 | 耗时 |
| --- | --- |
| 导入 + 读 Anima tag 表（24655 条） | ~55 ms |
| 加载扩展词库（预载前 4 万条热数据） | ~42 ms |
| 转换一次输入 | ~0.4 ms |

启动只预载高频段，其余走 SQLite 索引冷查询（`cn = ?` 实测 0.02 ms/次），结果带缓存。所以磁盘上 35 MB 的词库并不需要全塞进内存。

纯 Python 标准库（`tkinter` / `re` / `json` / `sqlite3`），**不占显存**。相比本地跑一个 LLM 做翻译，这是两个数量级的差距。

## 相比现成方案

查过一圈，现成的都只解决「点选 / 补全」：

- [ai-prompt-supermarket](https://github.com/BFRKQSB7/ai-prompt-supermarket) — 单文件 HTML，内置 31.7 万条中英对照，点选生成
- [小河的 Danbooru 标签助手](https://xhoxye.github.io/BooruTagCart/) — 浏览器端标签浏览
- [ffdkj 的 Danbooru 中英对照表](https://github.com/ffdkj/ffdkj-Danbooru_Tag-Chinese-English-Translation-Table) — 33 万条 sqlite / csv，MIT
- [Comfyui-Anima-Tools](https://github.com/ComfyNodePRs/PR-Comfyui-Anima-tools-a0fe04bd) — Anima 专用视觉提示词套件

它们都是「给你一个词库，你自己挑」。而本工具是「丢一段中文进去，直接出分类好的 prompt」，中间的分词、分类、未命中隔离没人做。

## 致谢

这个工具站在别人的数据上，明确记一笔：

- **[amenorira/danbooru-tags-data-zh](https://github.com/amenorira/danbooru-tags-data-zh)** — Danbooru 标签的中文翻译数据库，收录图片数 > 50 的标签，译名以社区通用叫法为准，同时发布在 GitHub 与 HuggingFace。**本项目的词库扩展方向依赖这份数据**（用于把覆盖量从当前的 331 条提升一个量级）。
- **[ffdkj/ffdkj-Danbooru_Tag-Chinese-English-Translation-Table](https://github.com/ffdkj/ffdkj-Danbooru_Tag-Chinese-English-Translation-Table)** — 每日更新的 Danbooru tag 中英对照表，33 万+ 条，含 `category`（标签分类）与 `post_count`，MIT 许可。**感谢作者持续维护这份数据并免费开放。**
- **[ComfyUI Good Anima](https://github.com/ComfyNodePRs/PR-Comfyui-Anima-Tools-a0fe04bd)** — 提供了 Anima 官方 tag 表 `Anima-preview.csv`，本项目的词典校验完全建立在它之上。
- **[Danbooru](https://danbooru.donmai.us/)** — 所有 tag 语义与分类的源头。
- **[CircleStone Labs](https://huggingface.co/circlestone-labs/Anima) / Comfy Org** — Anima 模型本身。

本项目的代码是 MIT，但上述数据的版权归各自作者所有，使用时请遵守其许可。

## 许可

[MIT](LICENSE)。

Anima 官方 tag 表 `Anima-preview.csv` 不包含在本仓库内，其版权归原项目所有，使用前请遵守其许可（GPL-3.0）。
