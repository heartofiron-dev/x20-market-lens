# 数据从哪里来

| 数据 | 来源 | 获取方式 | 更新频率 | 当前情况 |
|---|---|---|---|---|
| 美股成交、报价和分钟线 | Alpaca IEX | REST 初始快照 + WebSocket | 事件驱动 | 已接入，但只在本机使用 Alpaca 凭证 |
| 加拿大股票 demo tick | 本地模拟器 | 进程内生成 | 1 秒 | 支持 `.TO`、`.V`、`.CN`、`.NE`；不是真实 TSX 行情 |
| 公司新闻 | Alpaca News | REST | 60 秒 | 已接入 |
| 美国公司财务数据 | SEC EDGAR Company Facts | REST | 5 分钟 | 已完成通用 ticker/CIK 查找和 XBRL 归一化 |
| 加拿大公司财务数据 | SEDAR+ | 尚未连接 | 暂不可用 | 需要得到许可的数据接入；当前保持 unavailable |
| SPCX 案例 | SPCX 2026 Q2 10-Q | 本地 JSON | 固定测试数据 | 只作为案例保留，不参与通用运行 |
| 利率 | FRED | 计划接入 | 5–15 分钟 | 当前为中性占位值 |
| 行业基准 | Nasdaq 或获准供应商 | 计划接入 | 1 分钟 | 当前为中性占位值 |
| 期权、空头和流通股 | 获准供应商 | 计划接入 | 由供应商决定 | 当前为中性占位值 |

## 原始资料

- SEC EDGAR API 文档：<https://www.sec.gov/search-filings/edgar-application-programming-interfaces>
- Alpaca Market Data 文档：<https://docs.alpaca.markets/docs/about-market-data-api>
- Alpaca 股票 WebSocket 文档：<https://docs.alpaca.markets/docs/real-time-stock-pricing-data>
- SPCX 案例财报：<https://www.sec.gov/Archives/edgar/data/1181412/000162828026052535/spcx-20260630.htm>

## 行情覆盖范围

Alpaca 免费 Paper Trading 账户只提供 IEX 行情。每份 X20 快照都会写明供应商、feed 和传输方式，不会把 IEX 描述成覆盖全美交易所的 SIP。没有接入的数据保持中性或 unavailable，不用猜测值补齐。

## 信息可信度

1. 监管文件（tier 4）
2. 公司或政府机构原文（tier 3）
3. 能确认作者和来源的二手报道（tier 2）
4. 未核实帖子或传闻（tier 1）

有明确反证的信息，其可信度会乘以 `0.35`。传闻可以影响 rumor-pressure 风险因子，但不能覆盖已经核实的财务数字。
