# Project Charter · X20 Market Lens

## Mission

为个体投资者提供一套可以追溯“数据从哪里来、数学如何得出、用户风险怎样叠加”的通用实时美股研究工具。股票代码是运行时输入，不允许在模型或采集层硬编码单一标的。

## Success criteria

### v0.1 · Runnable research MVP

- [x] 启动即产生连续数据流（demo）或连接真实 WebSocket（live）。
- [x] 20 个可解释因子、解析梯度、Hessian、链式变化率、二阶压力测试。
- [x] 新闻/传闻的证据层级、时间、原文和反证标记。
- [x] 通用 SEC ticker/CIK、Company Facts 与同比财务归一化；SPCX 仅作为案例夹具。
- [x] 用户仓位、风险预算与投资期限的独立风险层。
- [x] Web dashboard、测试、文档和 CI。

### v0.2 · Data integrity

- [ ] SEC Company Facts 自动字段映射、单位校验和 amended filing 处理。
- [ ] FRED 利率、Nasdaq 行业基准、期权 IV、short interest 和 float calendar。
- [ ] 文章去重、实体链接、claim-level contradiction graph。
- [ ] SQLite/Parquet event store，严格保存 observation time 与 publication time。

### v0.3 · Scientific validation

- [ ] Purged walk-forward splits，杜绝未来数据泄漏。
- [ ] Logistic/Brier calibration 与 prediction interval coverage。
- [ ] 和 price-only、random walk、buy-and-hold baseline 对比。
- [ ] 交易成本、滑点、停牌和延迟注入。
- [ ] Model card + data card + reproducible evaluation report。

### v1.0 · Production candidate

- [ ] 至少 12 个月稳定采集历史，覆盖多个市场状态。
- [ ] 密钥托管、provider failover、健康监控、数据许可审计。
- [ ] 每个模型版本可复现，可一键回滚。
- [ ] 仅在独立验证达标后考虑 paper-trading；默认仍不自动下单。

## Non-goals

- 不声称精确预测未来价格。
- 不把匿名传闻当成事实。
- 不把“研发投入高”或“股价涨”单独当作公司质量证明。
- 不为提高回测结果而使用未来数据、幸存者偏差或人工挑选窗口。

## Initial risks

1. 新上市或交易历史较短的标的无法支持可信的长期校准。
2. 低流通盘、解禁和注意力冲击会造成分布漂移。
3. 多来源时间戳、修订财报和 provider 延迟可能造成数据泄漏。
4. 用户可能把“上涨概率”误读成指令，因此界面必须持续显示不确定区间和风险预算。
