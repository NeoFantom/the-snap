# 响指 / the-snap

**一个响指之后，只有一部分文件能留下——由你来决定是哪些。**

**「响指」专门找出那些只存在于待重置机器上的文件。** 它给待抹掉的机器和一台参照机
（你的新电脑／备份／NAS）各建一份索引，按**文件名 + 内容 hash** 比对，所以一个只是
**挪了位置**的文件不会被误判、更不会被重复拷贝；接着在浏览器目录树里把这些「只此一份」
的文件列给你，点击决定保留或丢弃，最后拷贝幸存者并逐个校验。源端与参照端是 Windows、
macOS、Linux 还是 WSL 都行。

🇬🇧 **English → [README.md](./README.md)**

> 一套可复现的工作流，用于在多台机器之间迁移、核对、精简文件——为「电脑马上要重置，
> 我是不是忘了什么？」这个场景而生，也适用于任何文件整理杂活。

**状态**：从一次真实的一次性迁移中提炼而来，1.0 之前 API 可能变动。

## 它做什么

给定两个根目录（source 源 与 reference 参照）——通常是*旧机器*和*新机器*——本工具集：

1. **建索引（Index）**：把两边各扫成 TSV（路径、大小、mtime），不递归进系统／缓存／
   依赖等黑名单目录。源端、参照端任意操作系统皆可。
2. **比对（Compare）**：按**文件名 + 内容 hash**。同名且 size 相同的**小文件**用 sha256
   确认内容（抓出「同名同 size 但内容不同」的危险情况）；**大文件**（超过 `hash_max_bytes`）
   只比 name + size——大文件几乎不可能恰好同 size 而内容不同，且 hash 它最贵。每个文件归为
   `present`（参照侧已有）、`changed`（内容不同）或 `unique`（仅源侧有）。hash 在各机本地算，
   文件绝不为了比对而传输。
3. **精筛（Refine）**：从待迁清单里剥掉噪音（编译产物、第三方 clone、隐藏配置目录、
   用户声明丢弃的项）。
4. **网页审阅（Serve）**：在 `http://localhost:<哈希端口>/` 起一个交互式目录树，点选即排除
   某个前缀，选择**实时**落盘到 JSON，刷新／重开不丢。
5. **拷贝（Copy）**：保住非 ASCII（中文／emoji）文件名（Windows 源用 tar-over-ssh，
   unix 源用 rsync）。
6. **校验（Verify）**：逐个文件按大小与清单核对。

适用：重置前迁移；C 盘清理；按项目／主题归集文件；找回被文件同步工具（因排除了共享数据根）
漏掉的东西。

## 为什么需要它

文件同步工具（FreeFileSync、robocopy、rsync）只镜像目录树，但不告诉你*哪些是独有的、
哪些别处已有*。磁盘可视化工具（WinDirStat、TreeSize）只显示大小，真正核对时容易迷失。
AI agent 能驱动整个流程，但需要一份结构化的 skill 来照着走——这正是 `SKILL.md` 提供的。

本工具集专门规避的两个坑（详见 `METHODOLOGY.md`）：

- **黑名单根目录很危险**。按名整片排除 `ProgramData` 或 `AppData`，会埋掉用户手放在里面的
  便携程序（比如旧版应用残留的好几 GB 聊天记录）。
- **Windows 上 `tar -T` 用系统 ANSI 代码页读文件清单**（中文环境通常是 GBK），不是 UTF-8。
  中文路径要存活，必须先 `iconv -t GBK` 转换清单。

## 目录结构

```
.
├── README.md           # 英文版
├── README.zh-CN.md     # 本文件
├── LICENSE             # MIT
├── SKILL.md            # 给 AI agent 的分步工作流
├── METHODOLOGY.md      # 原理 + 经过验证的模式（已匿名）
├── scripts/            # 跨平台：PowerShell 索引器 + Python pipeline
│   ├── config.example.json   # 复制成 config.json 再编辑
│   └── check-no-pii.sh       # 守卫：私有数据泄漏即报错
├── web/                # 交互式目录树排除 UI（免构建，打开即用）
│   └── tree.json.example     # 匿名示例数据
├── docs/               # platforms.md——各操作系统与 WSL／跨 VM 配方
└── plugins/            # claude-code / codex / opencode 的适配清单
```

## 快速上手

```bash
# 0. 配置（主机、ssh 用户、盘符、排除项）——逐行读内联注释
cp scripts/config.example.json scripts/config.json && $EDITOR scripts/config.json

# 1. 给即将重置的机器（源）建索引
#    Windows 源（无需在它上面装 Python）：
B64=$(iconv -t UTF-16LE < scripts/index-remote.ps1 | base64 -w0)
ssh "$REMOTE_USER@$REMOTE_HOST" "powershell -NoProfile -EncodedCommand $B64" > index/source.tsv
#    mac / linux / WSL 源：把 Python 索引器经 ssh 喂过去
#    ssh "$REMOTE_USER@$REMOTE_HOST" python3 - --roots /home /data < scripts/index-local.py > index/source.tsv
#    （WSL 要索引自己的 Windows 宿主？见 docs/platforms.md——原生索引，别去 walk /mnt/c）

# 2. 给本地参照机建索引（根目录来自 config.json）
python3 scripts/index-local.py > index/reference.tsv

# 3. 比对、精筛，再用内容 hash 确认小文件候选
python3 scripts/compare.py index/source.tsv index/reference.tsv > index/report-missing.md
python3 scripts/diff-analyze.py index/source.tsv index/reference.tsv
python3 scripts/hash-confirm.py        # 源就是本机时加 --src-local

# 4. 建树并在网页里交互审阅（浏览器把点选实时存为 JSON）
python3 scripts/build-tree.py index/to-migrate.tsv web/tree.json
python3 scripts/serve.py
# 打开 http://localhost:<端口>/

# 5. 拷贝精筛后的集合（Windows：tar-over-ssh；unix：rsync——见 SKILL.md 第 8 步）
python3 scripts/copy-scattered.py

# 6. 逐文件按大小校验
python3 scripts/verify-landed.py
```

完整分步说明（含确切的 tar／rsync 命令、中文／编码坑，以及各平台配方）：
见 `SKILL.md` 与 `docs/platforms.md`。

## 作为 agent skill 安装

每个 `plugins/<agent>/` 目录都是一份指向 `SKILL.md` 的自包含清单。软链或复制进对应
agent 的 skill 目录：

- **Claude Code**：`~/.claude/skills/the-snap/` → `plugins/claude-code/`
- **Codex**：见 `plugins/codex/README.md`
- **OpenCode**：见 `plugins/opencode/README.md`

当用户提到「迁移」「重置前」「audit files」「这台机器哪些文件是独有的」等，agent 会自动
加载该 skill。

## 状态与路线图

1.0 之前。当前限制：

- 内容 hash 受 **name+size 闸门** 控制：只对同名同 size 的**小文件**（≤ `hash_max_bytes`）
  做 sha256 确认，大文件仅凭 name+size 信任。这是刻意的取舍（全盘 hash 太慢）——一个 size
  恰好相撞但内容不同的大文件会被当成已有副本。
- 源端索引：Windows 用 `index-remote.ps1`（无需在它上面装 Python）；macOS／Linux／WSL
  把 `index-local.py` 经 ssh 喂过去。
- tar-over-ssh 假设远端有 `bsdtar`（Windows 10+ 自带）；unix 源改用 `rsync`。

## 许可

MIT —— 见 `LICENSE`。
