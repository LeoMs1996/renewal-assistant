# traces-claims/ —— 理赔轨迹（**不入库**，与续保 `traces/` 物理分离）

> 状态：C0 占位（仅 `.gitkeep`）。建立于 2026-11-17。

## 为什么单独一个目录

1. **合规**：理赔轨迹含报案人信息、事故描述、医疗/维修材料摘要——PII 密度高于续保轨迹。与续保 `traces/` 混放会让「哪些数据属于哪个业务」无法界定。
2. **可观测性**：两条业务线的轨迹要能分别统计、分别清理、分别设保留期。
3. **基线保护**：续保 `traces/` 属保护对象（只读），理赔写入它即为违规。

## 强制隔离方式（不改源码）

`server/config.py`：

```python
TRACE_DIR = Path(env("TRACE_DIR", str(BASE_DIR / "traces")) ...)
```

理赔域运行时**必须**注入：

```bash
export TRACE_DIR="$PWD/traces-claims"
```

这样复用 `server/trace.py` 写 JSONL 时，落点是本目录，续保 `traces/` 零写入。
**首次运行必须自证落点**：启动日志或 `ls -la traces-claims/` 里应出现新 JSONL，且 `traces/` 的 mtime 不变。

## 不入库

`.gitignore`：

```gitignore
traces-claims/**
!traces-claims/.gitkeep
!traces-claims/README.md
```

理由与续保 `traces/` 一致：运行态 + 含 PII + 每次运行都变。目录骨架入库，内容不入库。

## 保留期与清理（C4/C5 决策，先记要求）

- 演示/测试产生的轨迹，任务结束即清理，勿长期堆积（续保 `traces/` 已积压 1183 个文件，属历史遗留）。
- 若接入可观测后端，轨迹应导出为 OTLP 而非长期本地堆积（续保已有 `server/otel_export.py` 可参考，**只读**）。

## 自检命令

```bash
cd renewal-assistant
# 1) 隔离生效：claims 运行后 traces/ 不应有新文件
git status --short traces/          # 期望：空（traces/ 已 gitignore，此处仅作示意）
ls -la traces-claims/               # 期望：出现本次运行的 .jsonl
# 2) 入库边界正确
git status --short | grep traces-claims   # 期望：只有 .gitkeep / README.md 可能被跟踪
```

## 当前内容

`.gitkeep`（占位）+ `README.md`（本文件）。**没有任何轨迹。**
