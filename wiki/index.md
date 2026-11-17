# 条款 Wiki 索引（index.md）

> 本文件由 `python scripts/wiki_tool.py index` 生成，**勿手改**。
> 模式：LLM-Wiki（Karpathy 2026-04，见 `wiki/README.md` 与本文件末尾出处）。
> 条目数：8 · 正文语料：3602 字符 · 章节锚点格式：`wiki_id#章节标题`。

**查询顺序**：先读本目录定位 `wiki_id` → 读条目对应章节 → 语料增长到 index 不够用时再回退 `server/wiki_search.py` 的 RRF 混合检索。

| wiki_id | 标题 | 一句话摘要 | 版本 | 标签 |
|---|---|---|---|---|
| **承保条件** | | | | |
| [`wiki-ride-hailing`](ride-hailing.md) | 网约车/用途变更对保险的影响 | 家庭自用改网约车属危险程度显著增加，须及时通知保险人；已批改按营运系数 1.6 补收保费，未通知商业险可拒赔或比例赔。 | v2024.3 | 网约车, 用途变更, 营运系数, 危险程度显著增加 |
| **理赔与承保条件** | | | | |
| [`wiki-annual-inspection`](annual-inspection.md) | 车辆未年检，保险赔不赔？ | 未年检不必然拒赔：事故后补检合格且无因果关系多支持赔付；未年检与事故有直接因果则可拒赔或比例赔；交强险在限额内仍赔人身损害。 | v2024.3 | 年检, 拒赔, 因果关系, 承保条件, 交强险 |
| **规则与系数** | | | | |
| [`wiki-deductible`](deductible.md) | 免赔额/免赔率规则 | 综改后车损/三者默认含不计免赔；仍适用免赔的只有盗抢 20%、约定行驶区域外出险 +10%、非允许驾驶人商业险拒赔等。 | v2024.3 | 免赔率, 不计免赔, 综改, 同等保障比较 |
| [`wiki-rate-surcharge`](rate-surcharge.md) | 费率上浮/下浮规则（NCD 无赔款优待系数） | NCD 系数 0.65~1.50：连续 4 年无出险 0.65，上年出险 3 次及以上 1.50；商业险保费=Σ基准保费×NCD×用途系数×车龄系数。 | v2025.1 | NCD, 费率浮动, 出险次数, 报价有效期 |
| **险种条款** | | | | |
| [`wiki-csx`](csx.md) | 机动车损失险（车损险） | 车损险综改后已并入盗抢、自燃、玻璃单独破碎、涉水、不计免赔；保额按实际价值，车龄系数 1.0/1.05/1.15/1.3。 | v2024.3 | 车损险, 保障范围, 车龄系数, 盗抢, 涉水 |
| [`wiki-dsx`](dsx.md) | 第三者责任险（三者险） | 三者险赔第三方人身伤亡与财产直接损毁中超交强险分项限额的部分；合成费率 50 万 780、100 万 1180、200 万 1520、300 万 1780 元/年。 | v2024.3 | 三者险, 保额档位, 基准保费, 医保外用药 |
| [`wiki-jqx`](jqx.md) | 交强险（机动车交通事故责任强制保险） | 交强险法定强制、续保不可删除；死亡伤残 18 万/医疗 1.8 万/财产 2000 元，无责按 20%；赔付顺序先交强后商业。 | v2024.3 | 交强险, 责任限额, 强制投保, 费率浮动 |
| [`wiki-ywyw`](ywyw.md) | 医保外用药责任险 | 医保外用药责任险须先投保三者险或车上人员责任险；基准保费 60 元/年、常见保额 5 万，赔医保目录外自费药与进口药。 | v2024.3 | 附加险, 医保外, 自费药, 投保条件 |

## 互链图（related）

- `wiki-annual-inspection` → `wiki-csx`, `wiki-jqx`
- `wiki-csx` → `wiki-deductible`, `wiki-annual-inspection`, `wiki-rate-surcharge`, `wiki-ride-hailing`
- `wiki-deductible` → `wiki-csx`, `wiki-dsx`
- `wiki-dsx` → `wiki-jqx`, `wiki-ywyw`, `wiki-deductible`, `wiki-rate-surcharge`
- `wiki-jqx` → `wiki-dsx`, `wiki-annual-inspection`
- `wiki-rate-surcharge` → `wiki-ride-hailing`, `wiki-dsx`, `wiki-csx`
- `wiki-ride-hailing` → `wiki-rate-surcharge`, `wiki-csx`
- `wiki-ywyw` → `wiki-dsx`

---

出处：Karpathy《llm-wiki.md》idea file（2026-04；检索 2026-11-17）<https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>。
