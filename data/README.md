# data/ —— 理赔域数据根（C0 骨架）

> 状态：**C0 骨架，仅有占位文件**。建立于 2026-11-17。

## 布局

```text
data/
├── ins-mmbench/            # INS-MMBench 原始/子集数据（大文件，gitignored）
│   ├── .gitkeep
│   └── README.md           # 放置方式、目录约定、manifest 要求
└── llm-wiki-claims/        # 理赔 LLM-Wiki 工作区（**入库**，交付物）
    ├── raw/                # 抽样原文 + 溯源元数据
    └── wiki/               # 结构化 LLM-Wiki 条目（与续保 wiki/ 物理分离）
```

## 入库策略（三种，别混）

| 路径 | 入库 | 理由 |
|---|---|---|
| `data/ins-mmbench/**` | **否** | 第三方数据集体积大。GitHub 官方限制：单文件 >50 MiB 警告、>100 MiB 拒收，仓库建议 <1 GB（依据见 `docs/log/step-c0-baseline.md` 第 8 节 S2）。仅保留 `.gitkeep` / `README.md` 占位 |
| `data/llm-wiki-claims/raw/**` | **是** | 抽样原文是**溯源证据**，不入库则引用无法回溯；文本体量小 |
| `data/llm-wiki-claims/wiki/**` | **是** | 知识产物本身就是交付物 |

### 10 MiB 阈值（预先声明，免得以后争）

`raw/` 中**单文件**超过 10 MiB 时：不得直接入库，先裁剪为「与所引结论相关的片段」，原文另行存放并在 README 里登记来源与哈希。
这条阈值对应 S2 的 50 MiB 警告线留出 5× 余量，避免单个提交把仓库拖大。

## 为什么在这里而不在 `homework5/insurance-agent/`

团队目标提到 `homework5/insurance-agent/`，但本步骤任务契约为「方案 C：在 `renewal-assistant` 内新增理赔域，复用既有基础设施」，验收也以本仓库 `git status` 为准。
故 C0 全部落在 `renewal-assistant/` 内。若后续需要独立仓库形态，届时整体迁移并保留 git 历史（`git mv` + 独立提交），不要两边各写一份。

## 硬规则

- 任何写入 `data/` 的文件都必须能回答「这条数据的来源与许可是什么」。
- 不得把真实 PII 数据放进 `data/`（一切为合成/公开数据集）。
- 动手前按 `docs/log/hard-rules.md` 完成 ≥3 来源检索并登记。
