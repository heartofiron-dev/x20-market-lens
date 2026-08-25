# X20 Market Lens

> 面向任意受支持美股代码的实时、证据优先、可解释研究系统。它把 20 个市场、新闻、财报与宏观变量放进同一张二次响应曲面，并把投资者本人的仓位与风险预算作为独立决策层。

![Python](https://img.shields.io/badge/Python-3.11%2B-69e5e5) ![Tests](https://img.shields.io/badge/tests-stdlib%20unittest-b4f34d) ![Model](https://img.shields.io/badge/model-explainable%20quadratic-a995ff) ![Trading](https://img.shields.io/badge/auto--trading-disabled-ffbc5c)

## 当前状态（2026-08-25）

| 项目 | 当前情况 |
|---|---|
| 公网测试地址 | [x20-market-lens-nq5d.onrender.com](https://x20-market-lens-nq5d.onrender.com/) 已上线，可直接选择股票并体验分析界面 |
| 公网行情 | **DEMO 模拟数据**；橙色 `DEMO` 标签代表价格不是实际市场成交，即使开盘也不会自动切换为真实行情 |
| 本地真实行情 | 已支持 Alpaca Paper Trading 的 IEX 实时快照与 WebSocket；密钥只保留在本机进程内存 |
| 股票范围 | 不是 SPCX 专用；支持输入任意合法美股代码，SEC 有覆盖时会自动加载公司财务事实 |
| 加拿大股票 | 公网 DEMO 已接受 `SHOP.TO`、`RY.TO`、`TD.TO` 等 TSX/TSXV/CSE/Cboe Canada 代码并使用 CAD 显示；真实 TSX 行情与 SEDAR+ 基本面仍待合规数据源 |
| 多用户 | 已实现浏览器会话隔离；公网配置上限为 200 个活跃会话、12 个同时活跃代码、30 分钟空闲清理 |
| 数学模型 | 20 因子二次响应曲面、梯度、Hessian、链式变化率和二阶压力测试均已实现 |
| 预测能力 | 当前系数仍是透明启发式先验，**尚未完成样本外校准与收益有效性证明** |
| 交易功能 | 未实现自动下单，也不提供收益保证或投资建议 |

目前已经完成的是“可运行、可解释、支持多人测试的研究 MVP”。当前最重要的缺口是：公网实时行情展示许可、历史样本校准与回测、数据源补全、持久化和生产监控。在获得允许多用户展示/再分发的市场数据许可之前，公网继续保持 DEMO；真实 IEX 行情仅通过本地安全模式使用。


## 这个项目解决什么

价格走势、新闻热度、利率、财报和传闻的时点不同、可信度不同，也经常互相矛盾。X20 不把它们压成一个神秘的“AI 分数”，而是保留完整证据链，并回答四个问题：

1. 此刻的 20 维状态是什么？
2. 哪个变量的局部影响（偏导数）最大？
3. 所有变量实时变化后，模型曲面沿时间方向走多快？
4. 同样的市场状态，对用户的真实仓位意味着多大风险？

当前 v0.2 是**可运行研究 MVP**，并已加入多人会话隔离。模型系数是透明启发式先验，还不是经过充分样本外验证的交易模型。

## 一分钟运行

### 安全启动真实行情（推荐）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[live]"
.\.venv\Scripts\python.exe .\scripts\browser_credentials.py
```

打开 <http://127.0.0.1:8764>，在本机页面中填写 Alpaca Paper Trading Key/Secret，再选择初始股票代码。凭证只进入本次实时进程内存，不写入项目文件、不进入浏览器端 JavaScript，也不会由 API 返回。

页面启动后可直接切换 `AAPL`、`NVDA`、`SPCX` 等有效美股代码；切换时旧代码的价格序列、证据和基本面状态会清空并重新加载。

### 演示模式

无需 API key 的实时演示模式：

```powershell
$env:PYTHONPATH = "src"
python -m x20 serve --demo
```

打开 <http://127.0.0.1:8765>。页面会立即收到每秒一个模拟 tick，并通过 SSE 每两秒重算全部 X20 因子、梯度、链式变化率、压力测试和个人风险。

### 让别人从公网同时测试

仓库根目录的 `render.yaml` 可部署一个多人演示实例。部署后，每个浏览器获得随机的
`HttpOnly` 会话 Cookie；股票代码、持仓、成本和风险参数只保存在该会话的服务器内存中，
不会覆盖其他用户。访问相同股票的用户共享同一份市场状态和计算缓存，避免为每位用户
重复创建后台数据流。

[Deploy to Render](https://render.com/deploy?repo=https://github.com/heartofiron-dev/x20-market-lens)

公网 Blueprint 有意使用 `--demo`：它支持最多 200 个活跃会话和 12 个同时活跃的股票代码，
每个空闲会话 30 分钟后自动清理。Render 免费实例重启或休眠后，内存会话会消失；这符合
测试用途，不应被当作永久账户系统。

不要把个人 Alpaca Key 配进公开演示站。个人 Trading API 行情授权不等于公开再分发行情的
授权。真实 IEX 行情仍使用上面的本地安全启动方式；若未来要提供合规的公共实时行情，需要
另行取得允许多用户展示/再分发的数据许可。

高级用户也可以从终端启动真实模式：

```powershell
.\.venv\Scripts\x20.exe serve --live --prompt-credentials --symbol AAPL
```

`--live` 先从 Alpaca REST 载入真实 IEX 快照，再认证 `wss://stream.data.alpaca.markets/v2/iex` 并订阅 trades、quotes 和 bars。免费 Paper 账户只覆盖 IEX，并不是全市场 SIP；休市期间只有最近真实快照，没有新成交事件。没有凭证时程序会拒绝启动 live 模式，不会把模拟或旧数据冒充实时数据。

## 多元微积分如何真正进入模型

令标准化状态为 `x ∈ [-1,1]^20`，模型曲面为：

```text
z(x) = β₀ + βᵀx + ½xᵀHx
P(up | x) = sigmoid(z)
```

- 梯度 `∇z = β + Hx`：此刻每个因子的边际影响。
- 链式法则 `dz/dt = ∇z · dx/dt`：20 个实时变量一起变化时，信号的瞬时方向。
- Hessian `H`：新闻情绪×可信度、研发投入×转化效率、估值×利率等二阶交互。
- 二阶压力测试 `Δz ≈ ∇z·h + ½hᵀHh`：同一组冲击在当前状态下造成的非线性影响。

实现见 [`src/x20/model.py`](src/x20/model.py)，推导与有限差分验证见 [`docs/MATH.md`](docs/MATH.md)。

## X20 因子

| 层 | 因子 |
|---|---|
| Market microstructure | short/medium momentum, realized volatility, volume shock, order flow |
| Information | news sentiment, news credibility, rumor pressure |
| Fundamentals | revenue growth, R&D intensity, R&D efficiency, operating margin, operating cash margin, capex intensity, liquidity strength |
| Regime & supply | valuation stretch, rate shock, sector relative strength, float unlock pressure, event risk |

所有因子都有来源和时点。传闻只能进入 `rumor_pressure`；在监管文件或公司原文交叉验证前，不得升级为基本面事实。

## 通用深层基本面分析

运行时按股票代码解析 SEC ticker/CIK 映射与 Company Facts，把同一财务概念的多个 XBRL 标签合并，并按相同 form、fiscal period 和近似报告跨度寻找去年同期。当前自动提取和派生：

- revenue growth；
- R&D intensity 与 R&D efficiency；
- operating margin 与 operating-cash margin；
- capex intensity 与 liquidity strength；
- filing form、period、filing date 和 SEC 原始来源。

这让系统能区分“研发投入高”和“研发真正转化为增长/利润改善”，而不是凭公司名气或新闻热度判断泡沫。`data/spcx_q2_2026.json` 仅保留为可审计案例，不是默认代码、运行依赖或唯一支持标的。

## 个人风险层

网页允许输入：持股数、买入均价、投资组合总值、最大可承受损失、风险厌恶和持有周期。市场模型不因用户偏好篡改；个人层单独计算：

- 仓位集中度；
- 未实现盈亏；
- 90% 模型区间映射的 95% 下行金额；
- 相对个人亏损预算的 risk load；
- 风险厌恶和集中度惩罚后的个人效用。

## 多用户隔离

- 浏览器只保存不可读的随机会话 ID，不保存 Alpaca 密钥或投资者资料。
- 服务器按会话保存当前股票与 `InvestorProfile`；API 和 SSE 始终读取当前会话。
- 同一股票的行情、新闻、基本面和模型基准快照共享；个人风险覆盖层在响应前单独计算。
- `/api/health` 不创建会话，部署平台的健康检查不会耗尽用户容量。
- 达到会话或活跃股票容量时返回明确的 `503`，不会偷偷复用或覆盖别人的会话。

## 测试

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m x20 snapshot
```

测试覆盖 Hessian 对称性、解析梯度对有限差分、链式法则、二阶压力测试、证据可信度、用户风险层、20 因子快照，以及两个并发浏览器的股票与持仓隔离。

## 项目结构

```text
src/x20/               模型、实时采集、证据账本、用户风险、HTTP/SSE 服务
web/                   无框架实时仪表盘
scripts/               本地安全凭证交接与启动器
data/                  可审计的案例数据，不参与通用运行时硬编码
tests/                 单元与集成测试
docs/                  数学、架构、数据源、验证路线
.github/workflows/     CI
```

## 实时架构边界

- 市场：live 模式是 WebSocket，不是定时刷新网页。
- 新闻：按分钟轮询并保留来源、发布时间、原文 URL、可信层级。
- 监管文件：SEC submissions 通常近实时更新，服务按分钟检查。
- 页面：后端通过 SSE 持续推送一个原子快照，避免多个卡片时间不一致。
- 断线：状态明确显示 `reconnecting/error`；不拿旧数据伪装新数据。

详细图见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 当前边界与后续验证

- 当前模型系数是透明先验，尚未完成跨股票、跨市场状态的 purged walk-forward calibration；
- 尚未接入逐笔 bid/ask、期权隐含波动率、FRED 利率和同行业自动 benchmark；
- 估值、利率、行业强弱、float/解禁等尚无可靠来源时保持中性值，不进行猜测填充；
- 没有自动下单、仓位调整或收益保证；
- 生产部署前仍需持久化、provider failover、速率限制、监控和数据许可审计。

验收门槛和路线图在 [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md)。

## 免责声明

本项目用于教育、研究与风险分析，不构成投资、法律、税务或经纪建议。概率和区间可能严重错误。不要仅凭本系统进行交易，参见 [`docs/DISCLAIMER.md`](docs/DISCLAIMER.md)。
