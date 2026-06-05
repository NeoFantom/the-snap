# 响指 / the-snap

> 重置即将抹掉这台机器的一半文件——你来决定谁能活下来。
>
> 一套可复现的工作流,用于在多台机器之间迁移、核对、精简文件——
> 为「电脑马上要重置,我是不是忘了什么?」这个场景而生,
> 也适用于任何文件整理杂活。

🇬🇧 **English → [README.md](./README.md)**

**状态**:从一次真实的一次性迁移中提炼而来,1.0 之前 API 可能变动。

## 它做什么

给定两个根目录(source 源 与 reference 参照)——通常是*旧机器*和
*新机器*——本工具集:

1. **建索引(Index)**:把两边都扫成 TSV(路径、大小、mtime),
   不递归进系统 / 缓存 / 依赖等黑名单目录。
2. **比对(Compare)**:按「文件名 + 大小」分类——`present`(参照侧已有)、
   `changed`(同名不同大小)、`unique`(仅源侧有)。
3. **精筛(Refine)**:从待迁清单里剥掉噪音(编译产物、第三方 clone、
   隐藏配置目录、用户声明丢弃的项)。
4. **网页审阅(Serve)**:在 `http://localhost:<哈希端口>/` 起一个交互式
   目录树,点选即排除某个前缀,选择**实时**落盘到 JSON,刷新/重开不丢。
5. **拷贝(Copy)**:用 tar-over-ssh 拷贝精筛后的集合,显式处理编码,
   保住非 ASCII(中文 / emoji)文件名。
6. **校验(Verify)**:逐个文件按大小与清单核对。

适用:重置前迁移;C 盘清理;按项目/主题归集文件;
找回被文件同步工具(因排除了共享数据根)漏掉的东西。

## 为什么需要它

文件同步工具(FreeFileSync、robocopy、rsync)只镜像目录树,
但不告诉你*哪些是独有的、哪些别处已有*。磁盘可视化工具
(WinDirStat、TreeSize)只显示大小,真正核对时容易迷失。
AI agent 能驱动整个流程,但需要一份结构化的 skill 来照着走——
这正是 `SKILL.md` 提供的。

本工具集专门规避的两个坑(详见 `METHODOLOGY.md`):

- **黑名单根目录很危险**。按名整片排除 `ProgramData` 或 `AppData`,
  会埋掉用户手放在里面的便携程序(比如旧版应用残留的好几 GB 聊天记录)。
- **Windows 上 `tar -T` 用系统 ANSI 代码页读文件清单**
  (中文环境通常是 GBK),不是 UTF-8。中文路径要存活,
  必须先 `iconv -t GBK` 转换清单。

## 目录结构

```
.
├── README.md           # 英文版
├── README.zh-CN.md     # 本文件
├── LICENSE             # MIT
├── SKILL.md            # 给 AI agent 的分步工作流
├── METHODOLOGY.md      # 原理 + 经过验证的模式(已匿名)
├── scripts/            # 跨平台:PowerShell 索引器 + Python pipeline
│   ├── config.example.json   # 复制成 config.json 再编辑
│   └── check-no-pii.sh       # 守卫:私有数据泄漏即报错
├── web/                # 交互式目录树排除 UI(免构建,打开即用)
│   └── tree.json.example     # 匿名示例数据
└── plugins/            # claude-code / codex / opencode 的适配清单
```

## 快速上手

```bash
# 0. 配置(主机、ssh 用户、盘符、排除项)——逐行读内联注释
cp scripts/config.example.json scripts/config.json && $EDITOR scripts/config.json

# 1. 给即将重置的远端(Windows)机器建索引
B64=$(iconv -t UTF-16LE < scripts/index-remote.ps1 | base64 -w0)
ssh "$REMOTE_USER@$REMOTE_HOST" "powershell -NoProfile -EncodedCommand $B64" \
    > index/source.tsv

# 2. 给本地参照机建索引(根目录来自 config.json)
python3 scripts/index-local.py > index/reference.tsv

# 3. 先比对,再精筛出待迁清单
python3 scripts/compare.py index/source.tsv index/reference.tsv > index/report-missing.md
python3 scripts/diff-analyze.py index/source.tsv index/reference.tsv

# 4. 建树并在网页里交互审阅(浏览器把点选实时存为 JSON)
python3 scripts/build-tree.py index/to-migrate.tsv web/tree.json
python3 scripts/serve.py
# 打开 http://localhost:<端口>/

# 5. 拷贝精筛后的集合(tar-over-ssh;中文处理见 SKILL.md 第 7 步)
python3 scripts/copy-scattered.py

# 6. 逐文件按大小校验
python3 scripts/verify-landed.py
```

完整分步说明(含确切的 tar-over-ssh 命令与中文/编码坑):见 `SKILL.md`。

## 作为 agent skill 安装

每个 `plugins/<agent>/` 目录都是一份指向 `SKILL.md` 的自包含清单。
软链或复制进对应 agent 的 skill 目录:

- **Claude Code**:`~/.claude/skills/the-snap/` → `plugins/claude-code/`
- **Codex**:见 `plugins/codex/README.md`
- **OpenCode**:见 `plugins/opencode/README.md`

当用户提到「迁移」「重置前」「audit files」「这台机器哪些文件是独有的」等,
agent 会自动加载该 skill。

## 状态与路线图

1.0 之前。当前限制:

- `index-remote.ps1` 仅限 Windows。macOS / Linux 作为源,暂时用
  `index-local.py`。
- 比对只看「名字 + 大小」,不做内容哈希(刻意为之——全盘哈希对核对
  流程太慢)。可插拔的哈希校验在路线图上。
- tar-over-ssh 假设远端有 `bsdtar`(Windows 10+ 自带)。Unix 源用
  GNU tar 即可。

## 许可

MIT —— 见 `LICENSE`。
