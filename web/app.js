const $ = (id) => document.getElementById(id);
const pct = (value, digits = 1) => `${(Number(value) * 100).toFixed(digits)}%`;
const money = (value, digits = 0) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: digits }).format(Number(value));
const compactMoney = value => new Intl.NumberFormat('en-US', { style:'currency', currency:'USD', notation:'compact', maximumFractionDigits:2 }).format(Number(value));
const signed = (value, digits = 4) => `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(digits)}`;

let latest = null;
let profileHydrated = false;

function drawChart(series) {
  const canvas = $('price-chart');
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, rect.width * ratio);
  canvas.height = Math.max(1, rect.height * ratio);
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  const width = rect.width, height = rect.height;
  ctx.clearRect(0, 0, width, height);
  if (!series || series.length < 2) return;
  const values = series.map(d => d.p);
  const min = Math.min(...values), max = Math.max(...values);
  const spread = Math.max(.01, max - min);
  const x = i => 4 + i * (width - 8) / (values.length - 1);
  const y = p => 12 + (max - p) * (height - 30) / spread;
  ctx.strokeStyle = 'rgba(172,204,208,.09)'; ctx.lineWidth = 1;
  for (let i = 1; i < 5; i++) { ctx.beginPath(); ctx.moveTo(0, i * height / 5); ctx.lineTo(width, i * height / 5); ctx.stroke(); }
  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, 'rgba(105,229,229,.30)'); gradient.addColorStop(1, 'rgba(105,229,229,0)');
  ctx.beginPath(); values.forEach((p, i) => i ? ctx.lineTo(x(i), y(p)) : ctx.moveTo(x(i), y(p)));
  ctx.lineTo(x(values.length - 1), height); ctx.lineTo(x(0), height); ctx.closePath(); ctx.fillStyle = gradient; ctx.fill();
  ctx.beginPath(); values.forEach((p, i) => i ? ctx.lineTo(x(i), y(p)) : ctx.moveTo(x(i), y(p)));
  ctx.strokeStyle = '#69e5e5'; ctx.lineWidth = 2; ctx.shadowColor = '#69e5e5'; ctx.shadowBlur = 9; ctx.stroke(); ctx.shadowBlur = 0;
  $('chart-range').textContent = `${money(min, 2)} — ${money(max, 2)}`;
}

function renderSensitivity(items) {
  const max = Math.max(.01, ...items.map(item => Math.abs(item.partial)));
  $('sensitivity-list').innerHTML = items.map(item => `
    <div class="bar-row ${item.partial < 0 ? 'negative' : ''}">
      <label>${item.label_zh}</label>
      <div class="bar-track"><i style="width:${Math.abs(item.partial) / max * 100}%"></i></div>
      <output>${signed(item.partial, 3)}</output>
    </div>`).join('');
}

function renderFactors(factors) {
  const zh = {
    short_momentum:'短线动量', medium_momentum:'中期动量', realized_volatility:'实现波动率', volume_shock:'成交量异动', order_flow:'订单流',
    news_sentiment:'新闻情绪', news_credibility:'新闻可信度', rumor_pressure:'传闻压力', revenue_growth:'营收增长', rd_intensity:'研发强度',
    rd_efficiency:'研发转化效率', operating_margin:'经营利润率', operating_cash_margin:'经营现金率', capex_intensity:'资本开支强度', liquidity_strength:'流动性实力',
    valuation_stretch:'估值拉伸', rate_shock:'利率冲击', sector_relative_strength:'行业相对强度', float_unlock_pressure:'解禁供给压力', event_risk:'事件风险'
  };
  $('factor-grid').innerHTML = factors.map((factor, index) => `
    <div class="factor"><header><span>${String(index + 1).padStart(2,'0')} · ${zh[factor.name]}</span><span>${factor.velocity >= 0 ? '↗' : '↘'}</span></header>
    <strong>${signed(factor.value, 3)}</strong><div class="factor-meter"><i style="width:${Math.abs(factor.value) * 100}%"></i></div><small>${factor.name}</small></div>`).join('');
}

function renderEvidence(items) {
  const names = {1:'RUMOR', 2:'SECONDARY', 3:'PRIMARY', 4:'REGULATORY'};
  $('evidence-list').innerHTML = items.slice(0, 8).map(item => `
    <article class="evidence"><header><h3>${escapeHtml(item.title)}</h3><span class="tier tier-${item.tier}">${names[item.tier]} · ${Math.round(item.credibility * 100)}</span></header>
    <p>${escapeHtml(item.claim)}</p><a href="${item.url.startsWith('http') ? item.url : '#'}" target="_blank" rel="noreferrer">${escapeHtml(item.source || 'source')} · ${item.published_at.slice(0,10)} ↗</a></article>`).join('');
}

function escapeHtml(text) {
  const span = document.createElement('span'); span.textContent = String(text); return span.innerHTML;
}

function render(data) {
  latest = data;
  const live = !data.quote.is_simulated && ['snapshot_ready','connected','authenticated','subscribed','live'].includes(data.feed_status);
  $('feed-pill').classList.toggle('live', live);
  $('feed-status').textContent = `${data.feed_status.toUpperCase()} · ${data.mode.toUpperCase()}`;
  $('mode-badge').textContent = data.quote.is_simulated ? 'DEMO' : data.provider.feed.toUpperCase();
  $('mode-badge').style.background = data.quote.is_simulated ? 'var(--amber)' : 'var(--lime)';
  $('quote-symbol').textContent = data.symbol;
  $('symbol-input').value = data.symbol;
  $('symbol-line').textContent = `${data.company} · ${data.symbol} · 20-VARIABLE RESPONSE SURFACE`;
  document.title = `X20 Market Lens · ${data.symbol}`;
  $('price').textContent = data.quote.price ? money(data.quote.price, 2) : '—';
  $('tick-time').textContent = data.last_market_at ? `最新 tick · ${new Date(data.last_market_at).toLocaleTimeString()}` : '等待首个数据点';
  $('quote-kind').textContent = data.quote.is_simulated ? 'SIMULATED FEED' : `ALPACA ${data.provider.feed.toUpperCase()} · ${data.last_event_kind || 'CONNECTING'}`;
  $('probability').textContent = pct(data.model.probability_up);
  $('expected-return').textContent = pct(data.model.expected_return_20d);
  $('return-range').textContent = `90% 区间 ${pct(data.model.interval_low)} → ${pct(data.model.interval_high)}`;
  $('chain-rate').textContent = signed(data.model.chain_rate, 5);
  $('risk-load').textContent = `${Number(data.investor.risk_load).toFixed(2)}×`;
  $('risk-status').textContent = data.investor.status;
  $('stress-total').textContent = signed(data.stress_test.total, 3);
  $('stress-detail').textContent = `一阶 ${signed(data.stress_test.first_order,3)} · 二阶 ${signed(data.stress_test.second_order,3)}`;
  drawChart(data.series); renderSensitivity(data.model.top_sensitivities); renderFactors(data.factors); renderEvidence(data.evidence);
  const f = data.fundamentals;
  $('revenue').textContent = f.available ? compactMoney(f.revenue) : '—';
  $('revenue-growth').textContent = f.available ? `同比 ${pct(f.revenue_growth)}` : 'SEC 数据加载中';
  $('rd-intensity').textContent = f.available ? pct(f.rd_intensity) : '—';
  $('op-margin').textContent = f.available ? pct(f.operating_margin) : '—';
  $('capex-intensity').textContent = f.available ? `${Number(f.capex_intensity).toFixed(2)}×` : '—';
  $('fundamental-reading').textContent = f.interpretation;
  $('filing-link').href = f.source || `https://www.sec.gov/edgar/search/#/q=${data.symbol}`;
  $('concentration').textContent = pct(data.investor.concentration);
  $('downside').textContent = money(data.investor.downside_95_amount, 0);
  $('pnl').textContent = money(data.investor.unrealized_pnl, 0);
  if (!profileHydrated) {
    for (const [key, value] of Object.entries(data.investor.profile)) {
      const field = $('profile-form').elements.namedItem(key); if (field) field.value = value;
    }
    $('risk-output').value = Number(data.investor.profile.risk_aversion).toFixed(2);
    profileHydrated = true;
  }
}

async function initial() {
  const response = await fetch('/api/snapshot');
  if (!response.ok) throw new Error(`snapshot ${response.status}`);
  render(await response.json());
  const stream = new EventSource('/api/events');
  stream.onmessage = event => render(JSON.parse(event.data));
  stream.onerror = () => { $('feed-status').textContent = 'RECONNECTING'; };
}

$('profile-form').addEventListener('submit', async event => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  const response = await fetch('/api/profile', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
  if (!response.ok) return;
  render(await response.json());
});
$('profile-form').elements.risk_aversion.addEventListener('input', event => $('risk-output').value = Number(event.target.value).toFixed(2));
$('symbol-form').addEventListener('submit', async event => {
  event.preventDefault();
  const symbol = new FormData(event.currentTarget).get('symbol');
  const response = await fetch('/api/symbol', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({symbol}) });
  const payload = await response.json();
  if (!response.ok) { $('feed-status').textContent = `ERROR · ${payload.error}`; return; }
  render(payload);
});
window.addEventListener('resize', () => latest && drawChart(latest.series));
initial().catch(error => { $('feed-status').textContent = `ERROR · ${error.message}`; });
