# 系统结构

```text
Browser A ─> random session A ─> ticker + InvestorProfile A ─┐
Browser B ─> random session B ─> ticker + InvestorProfile B ─┤
                                                             v
                                                  shared engine pool by ticker
                                                             │
                    market + news + SEC ─> X20 x(t), gradient, Hessian, dz/dt
                                                             │
                      session profile ─> private personal-risk overlay
                                                             │
                                             per-session JSON + SSE response
```

同一只股票只运行一个共享引擎，不会为每个浏览器重复创建。基础快照每两秒更新一次；返回结果前，服务会复制这份快照，再叠加当前会话的个人风险数据。这样，一个用户的刷新频率或持仓设置不会影响另一个用户。

## 时间怎么记录

- `event_time`：交易、新闻或财报事件实际发生的时间。
- `observed_at`：X20 收到这条数据的时间。
- `valid_from`：回测最早可以使用这条数据的时间。

v0.1 只在内存里保留来源发布时间和接收时间。v0.2 需要把三种时间持久化，否则无法可靠排除 look-ahead leakage。

## 出错时会发生什么

- live 模式没有 Alpaca 凭证时，服务不会启动。
- WebSocket 断开后，状态会显示 `reconnecting`，页面仍保留最后更新时间。
- 新闻或 SEC 请求失败时，错误会写入 `last_error`，行情流可以继续运行。
- demo 数据在 API 和页面上始终标为模拟数据。
- 同一个页面里的卡片都使用同一份快照，避免混用不同时间的数据。
- 切换股票只影响发起操作的会话。没有会话使用的股票引擎会被停止并清理。
- 空闲会话会过期；达到会话或股票数量上限时，服务返回 HTTP 503。

## 安全边界

API Key 只留在本机 live 进程中，不会进入仪表盘 JSON。浏览器凭证页面和静态服务都绑定到 `127.0.0.1`；凭证页面使用随机 CSRF token，并返回 `Cache-Control: no-store`。公网 demo 使用随机的 `HttpOnly`、`SameSite=Lax`、仅 HTTPS Cookie，仓位资料只存在服务器内存中。项目没有下单接口。
