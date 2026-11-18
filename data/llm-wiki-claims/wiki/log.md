# Wiki 操作账本（log.md）

> 只追加；前缀 `## [YYYY-MM-DD] <op> | <标题>` 可被 `grep '^## \['` 解析（R1 spec §5）。

## [2026-11-18] fix | 重置 log：清除一次误触 `build --all` 生成的 33 条 ingest 记录
- reason: 该次全量构建的生成器仍带「跨分片区间标记」缺陷（doc-auto / entity 跨两个分片时拼出非法区间），产物已作废
- action: 删除全部生成页 → 按 plan §4 分 6 批重编；本条目为删除动作的留痕
- 影响范围: 仅 wiki/ 生成物；raw/ 与 plan.md 未变
## [2026-11-18] ingest | claims-doc-ins-mmbench-agricultural
- page: docs/ins-mmbench-agricultural.md
- units: raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011
- qids: agri_0, agri_1, agri_2, agri_3, agri_4, agri_5, agri_6, agri_7, agri_8, agri_9, agri_10, agri_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-doc-ins-mmbench-auto
- page: docs/ins-mmbench-auto.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011, raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11, liability_0, liability_1, liability_3, liability_4, liability_6, liability_8, liability_10, liability_12, liability_16, liability_17, liability_19, liability_20
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-doc-ins-mmbench-health
- page: docs/ins-mmbench-health.md
- units: raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011
- qids: health_0, health_1, health_2, health_3, health_4, health_5, health_6, health_7, health_8, health_9, health_10, health_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-doc-ins-mmbench-property
- page: docs/ins-mmbench-property.md
- units: raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005
- qids: property_0, property_1, property_2, property_3, property_4, property_5
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-section-claim-policy-validity
- page: sections/claim-policy-validity.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-section-claim-coverage-limits
- page: sections/claim-coverage-limits.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-section-claim-loss-amount
- page: sections/claim-loss-amount.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-section-claim-vehicle-condition
- page: sections/claim-vehicle-condition.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-section-agri-insured-subject
- page: sections/agri-insured-subject.md
- units: raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011
- qids: agri_0, agri_1, agri_2, agri_3, agri_4, agri_5, agri_6, agri_7, agri_8, agri_9, agri_10, agri_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-section-agri-infection-status
- page: sections/agri-infection-status.md
- units: raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011
- qids: agri_0, agri_1, agri_2, agri_3, agri_4, agri_5, agri_6, agri_7, agri_8, agri_9, agri_10, agri_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-section-agri-compensation-tier
- page: sections/agri-compensation-tier.md
- units: raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011
- qids: agri_0, agri_1, agri_2, agri_3, agri_4, agri_5, agri_6, agri_7, agri_8, agri_9, agri_10, agri_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
## [2026-11-18] ingest | claims-section-health-imaging-part
- page: sections/health-imaging-part.md
- units: raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011
- qids: health_0, health_1, health_2, health_3, health_4, health_5, health_6, health_7, health_8, health_9, health_10, health_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-health-report-consistency
- page: sections/health-report-consistency.md
- units: raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011
- qids: health_0, health_1, health_2, health_3, health_4, health_5, health_6, health_7, health_8, health_9, health_10, health_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-health-risk-level
- page: sections/health-risk-level.md
- units: raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011
- qids: health_0, health_1, health_2, health_3, health_4, health_5, health_6, health_7, health_8, health_9, health_10, health_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-health-underwriting-decision
- page: sections/health-underwriting-decision.md
- units: raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011
- qids: health_0, health_1, health_2, health_3, health_4, health_5, health_6, health_7, health_8, health_9, health_10, health_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-liability-accident-occurrence
- page: sections/liability-accident-occurrence.md
- units: raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020
- qids: liability_0, liability_1, liability_3, liability_4, liability_6, liability_8, liability_10, liability_12, liability_16, liability_17, liability_19, liability_20
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-liability-causation
- page: sections/liability-causation.md
- units: raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020
- qids: liability_0, liability_1, liability_3, liability_4, liability_6, liability_8, liability_10, liability_12, liability_16, liability_17, liability_19, liability_20
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-liability-scene-context
- page: sections/liability-scene-context.md
- units: raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020
- qids: liability_0, liability_1, liability_3, liability_4, liability_6, liability_8, liability_10, liability_12, liability_16, liability_17, liability_19, liability_20
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-liability-environment
- page: sections/liability-environment.md
- units: raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020
- qids: liability_0, liability_1, liability_3, liability_4, liability_6, liability_8, liability_10, liability_12, liability_16, liability_17, liability_19, liability_20
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-property-disaster-type
- page: sections/property-disaster-type.md
- units: raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005
- qids: property_0, property_1, property_2, property_3, property_4, property_5
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-property-damage-count
- page: sections/property-damage-count.md
- units: raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005
- qids: property_0, property_1, property_2, property_3, property_4, property_5
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-section-property-claim-decision
- page: sections/property-claim-decision.md
- units: raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005
- qids: property_0, property_1, property_2, property_3, property_4, property_5
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-entity-coverage-limit
- page: entities/coverage-limit.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-entity-policy-expiry
- page: entities/policy-expiry.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-entity-loss-severity
- page: entities/loss-severity.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-entity-primary-responsibility
- page: entities/primary-responsibility.md
- units: raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020
- qids: liability_0, liability_1, liability_3, liability_4, liability_6, liability_8, liability_10, liability_12, liability_16, liability_17, liability_19, liability_20
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-entity-infection-status
- page: entities/infection-status.md
- units: raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011
- qids: agri_0, agri_1, agri_2, agri_3, agri_4, agri_5, agri_6, agri_7, agri_8, agri_9, agri_10, agri_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-entity-compensation-tier
- page: entities/compensation-tier.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011, raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11, agri_0, agri_1, agri_2, agri_3, agri_4, agri_5, agri_6, agri_7, agri_8, agri_9, agri_10, agri_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-entity-report-consistency
- page: entities/report-consistency.md
- units: raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011
- qids: health_0, health_1, health_2, health_3, health_4, health_5, health_6, health_7, health_8, health_9, health_10, health_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-entity-underwriting-decision
- page: entities/underwriting-decision.md
- units: raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011
- qids: health_0, health_1, health_2, health_3, health_4, health_5, health_6, health_7, health_8, health_9, health_10, health_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-entity-claim-decision
- page: entities/claim-decision.md
- units: raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005
- qids: property_0, property_1, property_2, property_3, property_4, property_5
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-faq-claim
- page: faqs/claim.md
- units: raw-claim-0000, raw-claim-0001, raw-claim-0002, raw-claim-0003, raw-claim-0004, raw-claim-0005, raw-claim-0006, raw-claim-0007, raw-claim-0008, raw-claim-0009, raw-claim-0010, raw-claim-0011
- qids: claim_0, claim_1, claim_2, claim_3, claim_4, claim_5, claim_6, claim_7, claim_8, claim_9, claim_10, claim_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-faq-agri
- page: faqs/agri.md
- units: raw-agri-0000, raw-agri-0001, raw-agri-0002, raw-agri-0003, raw-agri-0004, raw-agri-0005, raw-agri-0006, raw-agri-0007, raw-agri-0008, raw-agri-0009, raw-agri-0010, raw-agri-0011
- qids: agri_0, agri_1, agri_2, agri_3, agri_4, agri_5, agri_6, agri_7, agri_8, agri_9, agri_10, agri_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-faq-health
- page: faqs/health.md
- units: raw-health-0000, raw-health-0001, raw-health-0002, raw-health-0003, raw-health-0004, raw-health-0005, raw-health-0006, raw-health-0007, raw-health-0008, raw-health-0009, raw-health-0010, raw-health-0011
- qids: health_0, health_1, health_2, health_3, health_4, health_5, health_6, health_7, health_8, health_9, health_10, health_11
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-faq-liability
- page: faqs/liability.md
- units: raw-liability-0000, raw-liability-0001, raw-liability-0003, raw-liability-0004, raw-liability-0006, raw-liability-0008, raw-liability-0010, raw-liability-0012, raw-liability-0016, raw-liability-0017, raw-liability-0019, raw-liability-0020
- qids: liability_0, liability_1, liability_3, liability_4, liability_6, liability_8, liability_10, liability_12, liability_16, liability_17, liability_19, liability_20
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出

## [2026-11-18] ingest | claims-faq-property
- page: faqs/property.md
- units: raw-property-0000, raw-property-0001, raw-property-0002, raw-property-0003, raw-property-0004, raw-property-0005
- qids: property_0, property_1, property_2, property_3, property_4, property_5
- result: ok (serial, one unit at a time)
- lint: 见 `python3 data/llm-wiki-claims/scripts/wiki_lint.py` 输出
