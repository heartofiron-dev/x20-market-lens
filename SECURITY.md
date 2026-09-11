# Security

## 支持范围

这个项目还在研究阶段，目前只维护 `main` 分支的最新版本。

## 发现安全问题时

不要在公开 Issue 里提交 API Key、账户资料或持仓信息。如果 GitHub Security Advisories 可用，请通过私密安全报告联系我。

## 密钥和个人资料怎么处理

- `APCA_API_KEY_ID` 和 `APCA_API_SECRET_KEY` 不能提交到 Git；`.env` 已经被忽略。
- 推荐的浏览器凭证页面只监听 `127.0.0.1`，使用一次性 CSRF token，并把凭证直接交给本机 live 进程，不写入磁盘。
- 不要把数据供应商密钥写进 `web/app.js`。
- 服务器默认只监听本机地址。
- Render 公网版本只运行 demo 模式，不包含 Alpaca 凭证。
- 公网会话使用随机的 `HttpOnly`、`SameSite=Lax`、仅 HTTPS Cookie；用户填写的仓位资料只放在进程内存中，空闲后会过期。
- 没有供应商的书面许可，不要使用个人行情订阅公开转发行情。
- X20 没有创建订单、取消订单或修改券商账户的接口。
