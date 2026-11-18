# raw/assets/ —— 图片资产（本层**故意为空**）

## 决策：不复制图片，只引用既有路径 + sha256

D1 已把 120 张图片落到 `data/ins-mmbench/raw/<split>/<source_index>/<n>.{jpg,png}`（共 **33.01 MiB**）。
D2 的规范化**不把它们复制到这里**，理由：

1. 避免 33 MiB 重复占用与双份维护（同一张图两个路径，sha256 会漂）；
2. `raw/sources/*.json` 的 `images[].asset_ref` 已给出仓库相对路径，`sha256` + `bytes` 让引用可校验，等价于「就地入库」的证据强度；
3. C0 的 `raw/README.md` 原约定即「不做二进制（图片/PDF）入库；如确需，只在条目里记路径与哈希」。

引用形态（每个源单元内）：

```json
"images": [
  {
    "path": "claim/0/0.jpg",
    "bytes": 8004,
    "sha256": "056d2489be28e55f76c326ba5b99a2c678c836ea2a5d2aae144e0fdad2e8d64e",
    "asset_ref": "data/ins-mmbench/raw/claim/0/0.jpg",
    "asset_sha256_verified": true
  }
]
```

## 代价（如实登记）

`data/ins-mmbench/**` 被 `.gitignore` 忽略（数据不入库），因此**全新 clone 不会带图片**：
- 只做文本检索/引用接地的评测不受影响（`question`/`labels` 已完整入库）；
- 需要图片的环节（多模态/视觉核验）必须先按 `data/ins-mmbench/FETCH.md` 重新取数，再用
  `python3 data/llm-wiki-claims/scripts/normalize_raw.py check` 复核 sha256。

## 若将来要改为「图片入库」

把生成器里 `images[]` 的写入改成复制到本目录（`raw/assets/<split>/<index>/<n>.<ext>`）并把
`asset_ref` 指过来，然后同时把 `.gitignore` 白名单与 `data/README.md` 的 10 MiB 阈值说明同步更新；
不要手工复制文件——否则 `check` 会因为清单与磁盘不一致而失败（这是预期行为）。
