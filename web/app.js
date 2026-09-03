const $ = (id) => document.getElementById(id);
const pct = (value, digits = 1) => `${(Number(value) * 100).toFixed(digits)}%`;
let currentCurrency = 'USD';
const money = (value, digits = 0, currency = currentCurrency) => new Intl.NumberFormat(currency === 'CAD' ? 'en-CA' : 'en-US', { style: 'currency', currency, maximumFractionDigits: digits }).format(Number(value));
const compactMoney = (value, currency = currentCurrency) => new Intl.NumberFormat(currency === 'CAD' ? 'en-CA' : 'en-US', { style:'currency', currency, notation:'compact', maximumFractionDigits:2 }).format(Number(value));
const signed = (value, digits = 4) => `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(digits)}`;

const FACTOR_LABELS = {
  short_momentum: 'Short momentum',
  medium_momentum: 'Medium momentum',
  realized_volatility: 'Realized volatility',
  volume_shock: 'Volume shock',
  order_flow: 'Order flow',
  news_sentiment: 'News sentiment',
  news_credibility: 'News credibility',
  rumor_pressure: 'Rumor pressure',
  revenue_growth: 'Revenue growth',
  rd_intensity: 'R&D intensity',
  rd_efficiency: 'R&D efficiency',
  operating_margin: 'Operating margin',
  operating_cash_margin: 'Operating cash margin',
  capex_intensity: 'Capex intensity',
  liquidity_strength: 'Liquidity strength',
  valuation_stretch: 'Valuation stretch',
  rate_shock: 'Rate shock',
  sector_relative_strength: 'Sector relative strength',
  float_unlock_pressure: 'Float unlock pressure',
  event_risk: 'Event risk'
};

const STATUS_LABELS = {
  '超出个人风险预算': 'Above personal risk budget',
  '接近个人风险上限': 'Near personal risk limit',
  '风险预算内': 'Within personal risk budget'
};

let latest = null;
let profileHydrated = false;
let symbolEditing = false;

function syncSymbolInput(symbol) {
  if (!symbolEditing) $('symbol-input').value = symbol;
}

function initFluidField() {
  const canvas = $('fluid-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d', { alpha: true });
  if (!ctx) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const pointer = { x: innerWidth * .72, y: innerHeight * .28, px: innerWidth * .72, py: innerHeight * .28, active: false };
  let width = 1;
  let height = 1;
  let dpr = 1;
  let particles = [];
  let frame = 0;

  const palette = [
    [110, 247, 210],
    [99, 223, 240],
    [159, 140, 255]
  ];

  function makeParticle(index, randomX = true) {
    const edgeBias = index % 4 === 0;
    return {
      x: randomX ? Math.random() * width : -20,
      y: Math.random() * height,
      px: 0,
      py: 0,
      vx: edgeBias ? .18 + Math.random() * .18 : (Math.random() - .5) * .25,
      vy: (Math.random() - .5) * .22,
      size: .45 + Math.random() * 1.25,
      alpha: .12 + Math.random() * .34,
      seed: Math.random() * 1000,
      color: palette[index % palette.length]
    };
  }

  function resizeFluid() {
    width = window.innerWidth;
    height = window.innerHeight;
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = Math.max(1, Math.floor(width * dpr));
    canvas.height = Math.max(1, Math.floor(height * dpr));
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = reducedMotion ? 34 : Math.min(112, Math.max(54, Math.floor(width * height / 16500)));
    particles = Array.from({ length: count }, (_, index) => makeParticle(index));
    ctx.clearRect(0, 0, width, height);
  }

  function movePointer(event) {
    pointer.px = pointer.x;
    pointer.py = pointer.y;
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    pointer.active = true;
    document.documentElement.style.setProperty('--cursor-x', `${event.clientX}px`);
    document.documentElement.style.setProperty('--cursor-y', `${event.clientY}px`);
  }

  function releasePointer() { pointer.active = false; }

  function paintParticle(particle, time) {
    particle.px = particle.x;
    particle.py = particle.y;

    const waveA = Math.sin((particle.y + time * 28) * .006 + particle.seed);
    const waveB = Math.cos((particle.x - time * 18) * .004 - particle.seed * .7);
    const angle = waveA * 1.4 + waveB * 1.1;
    particle.vx += Math.cos(angle) * .012;
    particle.vy += Math.sin(angle) * .012;

    if (pointer.active) {
      const dx = particle.x - pointer.x;
      const dy = particle.y - pointer.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      if (distance < 270) {
        const force = (1 - distance / 270) * .22;
        particle.vx += (-dy / distance) * force - (dx / distance) * force * .16;
        particle.vy += (dx / distance) * force - (dy / distance) * force * .16;
        particle.vx += (pointer.x - pointer.px) * .0018 * force;
        particle.vy += (pointer.y - pointer.py) * .0018 * force;
      }
    }

    particle.vx *= .972;
    particle.vy *= .972;
    const speed = Math.sqrt(particle.vx ** 2 + particle.vy ** 2);
    if (speed > 2.4) {
      particle.vx = particle.vx / speed * 2.4;
      particle.vy = particle.vy / speed * 2.4;
    }

    particle.x += particle.vx;
    particle.y += particle.vy;
    if (particle.x < -40 || particle.x > width + 40 || particle.y < -40 || particle.y > height + 40) {
      Object.assign(particle, makeParticle(Math.floor(particle.seed), false));
      particle.px = particle.x;
      particle.py = particle.y;
    }

    const [r, g, b] = particle.color;
    ctx.beginPath();
    ctx.moveTo(particle.px, particle.py);
    ctx.lineTo(particle.x, particle.y);
    ctx.strokeStyle = `rgba(${r},${g},${b},${particle.alpha})`;
    ctx.lineWidth = particle.size;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.size * 1.25, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${r},${g},${b},${Math.min(.62, particle.alpha * 1.4)})`;
    ctx.fill();

    if (pointer.active) {
      const dx = particle.x - pointer.x;
      const dy = particle.y - pointer.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      if (distance < 125 && particle.seed % 3 < 1) {
        ctx.beginPath();
        ctx.moveTo(particle.x, particle.y);
        ctx.lineTo(pointer.x, pointer.y);
        ctx.strokeStyle = `rgba(${r},${g},${b},${(1 - distance / 125) * .08})`;
        ctx.lineWidth = .6;
        ctx.stroke();
      }
    }
  }

  function draw(timeStamp = 0) {
    const time = timeStamp * .001;
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = frame === 0 ? 'rgba(6,9,13,1)' : 'rgba(6,9,13,.105)';
    ctx.fillRect(0, 0, width, height);
    ctx.globalCompositeOperation = 'lighter';
    particles.forEach(particle => paintParticle(particle, time));
    ctx.globalCompositeOperation = 'source-over';
    pointer.px += (pointer.x - pointer.px) * .16;
    pointer.py += (pointer.y - pointer.py) * .16;
    frame += 1;
    if (!reducedMotion) requestAnimationFrame(draw);
  }

  resizeFluid();
  window.addEventListener('resize', resizeFluid, { passive: true });
  window.addEventListener('pointermove', movePointer, { passive: true });
  document.documentElement.addEventListener('mouseleave', releasePointer);
  window.addEventListener('blur', releasePointer);
  draw();
}

function drawChart(series) {
  const canvas = $('price-chart');
  const rect = canvas.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.max(1, rect.width * ratio);
  canvas.height = Math.max(1, rect.height * ratio);
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);
  if (!series || series.length < 2) return;

  const values = series.map(item => item.p);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(.01, max - min);
  const x = index => 6 + index * (width - 12) / (values.length - 1);
  const y = price => 14 + (max - price) * (height - 38) / spread;

  ctx.strokeStyle = 'rgba(180,225,222,.075)';
  ctx.lineWidth = 1;
  for (let index = 1; index < 5; index += 1) {
    ctx.beginPath();
    ctx.moveTo(0, index * height / 5);
    ctx.lineTo(width, index * height / 5);
    ctx.stroke();
  }

  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, 'rgba(110,247,210,.28)');
  gradient.addColorStop(.62, 'rgba(99,223,240,.07)');
  gradient.addColorStop(1, 'rgba(99,223,240,0)');
  ctx.beginPath();
  values.forEach((price, index) => index ? ctx.lineTo(x(index), y(price)) : ctx.moveTo(x(index), y(price)));
  ctx.lineTo(x(values.length - 1), height);
  ctx.lineTo(x(0), height);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.beginPath();
  values.forEach((price, index) => index ? ctx.lineTo(x(index), y(price)) : ctx.moveTo(x(index), y(price)));
  ctx.strokeStyle = '#6ef7d2';
  ctx.lineWidth = 1.8;
  ctx.shadowColor = '#6ef7d2';
  ctx.shadowBlur = 11;
  ctx.stroke();
  ctx.shadowBlur = 0;
  $('chart-range').textContent = `${money(min, 2)} — ${money(max, 2)}`;
}

function renderSensitivity(items) {
  const max = Math.max(.01, ...items.map(item => Math.abs(item.partial)));
  $('sensitivity-list').innerHTML = items.map(item => `
    <div class="bar-row ${item.partial < 0 ? 'negative' : ''}">
      <label>${FACTOR_LABELS[item.factor] || item.factor}</label>
      <div class="bar-track"><i style="width:${Math.abs(item.partial) / max * 100}%"></i></div>
      <output>${signed(item.partial, 3)}</output>
    </div>`).join('');
}

function renderFactors(factors) {
  $('factor-grid').innerHTML = factors.map((factor, index) => `
    <div class="factor">
      <header><span>${String(index + 1).padStart(2,'0')} · ${FACTOR_LABELS[factor.name] || factor.name}</span><span>${factor.velocity >= 0 ? '↗' : '↘'}</span></header>
      <strong>${signed(factor.value, 3)}</strong>
      <div class="factor-meter"><i style="width:${Math.abs(factor.value) * 100}%"></i></div>
      <small>${factor.name}</small>
    </div>`).join('');
}

function renderEvidence(items) {
  const names = { 1: 'RUMOR', 2: 'SECONDARY', 3: 'PRIMARY', 4: 'REGULATORY' };
  $('evidence-list').innerHTML = items.slice(0, 8).map(item => `
    <article class="evidence">
      <header><h3>${escapeHtml(item.title)}</h3><span class="tier tier-${item.tier}">${names[item.tier]} · ${Math.round(item.credibility * 100)}</span></header>
      <p>${escapeHtml(item.claim)}</p>
      <a href="${item.url.startsWith('http') ? item.url : '#'}" target="_blank" rel="noreferrer">${escapeHtml(item.source || 'source')} · ${item.published_at.slice(0,10)} ↗</a>
    </article>`).join('');
}

function escapeHtml(text) {
  const span = document.createElement('span');
  span.textContent = String(text);
  return span.innerHTML;
}

function render(data) {
  latest = data;
  currentCurrency = data.quote.currency || 'USD';
  const live = !data.quote.is_simulated && ['snapshot_ready', 'connected', 'authenticated', 'subscribed', 'live'].includes(data.feed_status);
  $('feed-pill').classList.toggle('live', live);
  $('feed-status').textContent = `${data.feed_status.toUpperCase()} · ${data.mode.toUpperCase()}`;
  $('mode-badge').textContent = data.quote.is_simulated ? 'DEMO' : data.provider.feed.toUpperCase();
  $('mode-badge').style.background = data.quote.is_simulated ? 'var(--amber)' : 'var(--aqua)';
  $('quote-symbol').textContent = data.symbol;
  $('quote-currency').textContent = currentCurrency;
  syncSymbolInput(data.symbol);
  $('symbol-line').textContent = `${data.instrument.market_label} · ${data.company} · ${data.symbol} · 20-VARIABLE RESPONSE SURFACE`;
  document.title = `X20 Market Lens · ${data.symbol}`;
  $('price').textContent = data.quote.price ? money(data.quote.price, 2) : '—';
  $('tick-time').textContent = data.last_market_at ? `Latest tick · ${new Date(data.last_market_at).toLocaleTimeString('en-US')}` : 'Waiting for the first data point';
  $('quote-kind').textContent = data.quote.is_simulated ? 'SIMULATED FEED' : `ALPACA ${data.provider.feed.toUpperCase()} · ${data.last_event_kind || 'CONNECTING'}`;
  $('probability').textContent = pct(data.model.probability_up);
  $('expected-return').textContent = pct(data.model.expected_return_20d);
  $('return-range').textContent = `90% interval ${pct(data.model.interval_low)} → ${pct(data.model.interval_high)}`;
  $('chain-rate').textContent = signed(data.model.chain_rate, 5);
  $('risk-load').textContent = `${Number(data.investor.risk_load).toFixed(2)}×`;
  $('risk-status').textContent = STATUS_LABELS[data.investor.status] || data.investor.status;
  $('stress-total').textContent = signed(data.stress_test.total, 3);
  $('stress-detail').textContent = `First order ${signed(data.stress_test.first_order,3)} · Second order ${signed(data.stress_test.second_order,3)}`;
  drawChart(data.series);
  renderSensitivity(data.model.top_sensitivities);
  renderFactors(data.factors);
  renderEvidence(data.evidence);

  const fundamentals = data.fundamentals;
  $('revenue').textContent = fundamentals.available ? compactMoney(fundamentals.revenue, fundamentals.units || currentCurrency) : '—';
  $('revenue-growth').textContent = fundamentals.available ? `YoY ${pct(fundamentals.revenue_growth)}` : (data.instrument.country === 'CA' ? 'Awaiting SEDAR+ integration' : 'Loading SEC data');
  $('rd-intensity').textContent = fundamentals.available ? pct(fundamentals.rd_intensity) : '—';
  $('op-margin').textContent = fundamentals.available ? pct(fundamentals.operating_margin) : '—';
  $('capex-intensity').textContent = fundamentals.available ? `${Number(fundamentals.capex_intensity).toFixed(2)}×` : '—';
  $('fundamental-reading').textContent = fundamentals.interpretation;
  $('filing-link').href = fundamentals.source || data.instrument.regulatory_url;
  $('filing-link').textContent = `${data.instrument.regulator} ↗`;
  $('concentration').textContent = pct(data.investor.concentration);
  $('downside').textContent = money(data.investor.downside_95_amount, 0);
  $('pnl').textContent = money(data.investor.unrealized_pnl, 0);

  if (!profileHydrated) {
    for (const [key, value] of Object.entries(data.investor.profile)) {
      const field = $('profile-form').elements.namedItem(key);
      if (field) field.value = value;
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
  const response = await fetch('/api/profile', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!response.ok) return;
  render(await response.json());
});

$('profile-form').elements.risk_aversion.addEventListener('input', event => $('risk-output').value = Number(event.target.value).toFixed(2));
$('symbol-input').addEventListener('focus', () => { symbolEditing = true; });
$('symbol-input').addEventListener('input', () => { symbolEditing = true; });
$('symbol-input').addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    symbolEditing = false;
    if (latest) $('symbol-input').value = latest.symbol;
    event.currentTarget.blur();
  }
});

$('symbol-form').addEventListener('submit', async event => {
  event.preventDefault();
  const symbol = String(new FormData(event.currentTarget).get('symbol') || '').trim().toUpperCase();
  $('symbol-input').value = symbol;
  const response = await fetch('/api/symbol', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }) });
  const payload = await response.json();
  if (!response.ok) {
    symbolEditing = true;
    $('feed-status').textContent = `ERROR · ${payload.error}`;
    $('symbol-input').focus();
    return;
  }
  symbolEditing = false;
  render(payload);
  $('symbol-input').blur();
});

window.addEventListener('resize', () => latest && drawChart(latest.series));
initFluidField();
initial().catch(error => { $('feed-status').textContent = `ERROR · ${error.message}`; });
