const DATA_URL = "data/dashboard-data.json";
const COLORS = ["#0a665d", "#ff735c", "#5ba4ff", "#bfdc55", "#d699ff", "#f2b653"];

const formatCompact = (value, digits = 1) => new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: digits,
}).format(value);

const formatNumber = (value, digits = 0) => new Intl.NumberFormat("en", {
  maximumFractionDigits: digits,
  minimumFractionDigits: digits,
}).format(value);

const pct = (value, digits = 1) => `${formatNumber(value, digits)}%`;

function aggregateMonths(months) {
  const totalOrders = months.reduce((s, d) => s + d.total_orders, 0);
  const deliveredOrders = months.reduce((s, d) => s + d.delivered_orders, 0);
  const netSales = months.reduce((s, d) => s + d.delivered_net_sales, 0);
  const grossProfit = months.reduce((s, d) => s + d.delivered_gross_profit, 0);
  const cancelledOrders = months.reduce((s, d) => s + d.cancelled_orders, 0);
  return {
    totalOrders,
    deliveredOrders,
    netSales,
    grossProfit,
    grossMargin: netSales ? grossProfit / netSales * 100 : 0,
    aov: deliveredOrders ? netSales / deliveredOrders : 0,
    cancellationRate: totalOrders ? cancelledOrders / totalOrders * 100 : 0,
  };
}

function renderKpis(data, months, isAllYears) {
  const a = aggregateMonths(months);
  const kpis = [
    ["Delivered net sales", formatCompact(a.netSales, 2), `${formatNumber(a.deliveredOrders)} delivered orders`],
    ["Gross margin", pct(a.grossMargin, 1), `${formatCompact(a.grossProfit, 2)} gross profit`],
    ["Average order value", formatNumber(a.aov, 0), "Net sales per delivered order"],
    ["Return unit rate", isAllYears ? pct(data.kpis.return_unit_rate_pct, 1) : "—", isAllYears ? `${formatNumber(data.kpis.returned_units)} returned units` : "Return data shown for full period"],
    ["Cancellation rate", pct(a.cancellationRate, 1), `${formatNumber(a.totalOrders)} total orders`],
  ];
  document.querySelector("#kpiGrid").innerHTML = kpis.map(([label, value, sub]) => `
    <article class="kpi">
      <div class="kpi-label">${label}</div>
      <div class="kpi-value">${value}</div>
      <div class="kpi-sub">${sub}</div>
    </article>`).join("");
}

function lineChart(months) {
  const el = document.querySelector("#salesChart");
  if (!months.length) { el.innerHTML = "<p>No data</p>"; return; }
  const width = 1040, height = 310;
  const pad = { left: 58, right: 18, top: 18, bottom: 36 };
  const max = Math.max(...months.map(d => d.delivered_net_sales)) * 1.08;
  const min = 0;
  const x = i => pad.left + i * (width - pad.left - pad.right) / Math.max(months.length - 1, 1);
  const y = v => pad.top + (max - v) * (height - pad.top - pad.bottom) / (max - min);
  const points = months.map((d, i) => `${x(i)},${y(d.delivered_net_sales)}`).join(" ");
  const area = `${pad.left},${height - pad.bottom} ${points} ${x(months.length - 1)},${height - pad.bottom}`;
  const yTicks = [0, .25, .5, .75, 1].map(t => ({ value: max * t, y: y(max * t) }));
  const step = Math.max(1, Math.ceil(months.length / 8));
  const xTicks = months.map((d, i) => ({ d, i })).filter(({i}) => i % step === 0 || i === months.length - 1);
  el.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0a665d"/><stop offset="1" stop-color="#0a665d" stop-opacity="0"/></linearGradient></defs>
      ${yTicks.map(t => `<line class="chart-grid" x1="${pad.left}" y1="${t.y}" x2="${width-pad.right}" y2="${t.y}"/><text class="chart-axis" x="${pad.left-8}" y="${t.y+3}" text-anchor="end">${formatCompact(t.value)}</text>`).join("")}
      ${xTicks.map(({d,i}) => `<text class="chart-axis" x="${x(i)}" y="${height-10}" text-anchor="middle">${d.month}</text>`).join("")}
      <polygon class="chart-area" points="${area}"/>
      <polyline class="chart-line" points="${points}"/>
      ${months.map((d,i) => `<circle class="chart-dot" cx="${x(i)}" cy="${y(d.delivered_net_sales)}" r="3" data-month="${d.month}" data-value="${d.delivered_net_sales}"/>`).join("")}
    </svg>`;
  const tooltip = document.createElement("div");
  tooltip.className = "chart-tooltip";
  tooltip.hidden = true;
  document.body.appendChild(tooltip);
  el.querySelectorAll(".chart-dot").forEach(dot => {
    dot.addEventListener("mousemove", ev => {
      tooltip.hidden = false;
      tooltip.style.left = `${ev.clientX}px`;
      tooltip.style.top = `${ev.clientY}px`;
      tooltip.innerHTML = `<b>${dot.dataset.month}</b><br>${formatNumber(Number(dot.dataset.value), 0)}`;
    });
    dot.addEventListener("mouseleave", () => { tooltip.hidden = true; });
  });
}

function categoryBars(categories) {
  const max = Math.max(...categories.map(d => d.delivered_net_sales));
  document.querySelector("#categoryChart").innerHTML = categories.map(d => `
    <div class="bar-row">
      <span>${d.category}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${d.delivered_net_sales/max*100}%"></div></div>
      <span class="bar-value">${formatCompact(d.delivered_net_sales)}</span>
    </div>`).join("");
}

function returnDonut(rows) {
  const total = rows.reduce((s, d) => s + d.returned_units, 0);
  let running = 0;
  const stops = rows.map((d, i) => {
    const start = running;
    running += d.returned_units / total * 100;
    return `${COLORS[i]} ${start}% ${running}%`;
  }).join(", ");
  document.querySelector("#returnDonut").style.background = `conic-gradient(${stops})`;
  document.querySelector("#returnTotal").textContent = formatCompact(total, 1);
  document.querySelector("#returnLegend").innerHTML = rows.map((d, i) => `
    <div class="legend-row"><span class="legend-swatch" style="background:${COLORS[i]}"></span><span>${d.return_reason.replaceAll("_", " ")}</span><b>${pct(d.return_unit_share_pct, 1)}</b></div>`).join("");
}

function productTable(data, category) {
  const rows = category === "all" ? data.top_products : data.category_products;
  const shown = rows.filter(d => category === "all" || d.category === category).slice(0, 10);
  document.querySelector("#productRows").innerHTML = shown.map(d => `
    <tr>
      <td><b>${d.product_name}</b></td>
      <td>${d.category}</td>
      <td>${formatNumber(d.delivered_orders)}</td>
      <td>${formatNumber(d.delivered_net_sales, 0)}</td>
      <td><span class="margin-pill ${d.gross_margin_pct < 0 ? "negative" : ""}">${pct(d.gross_margin_pct, 1)}</span></td>
    </tr>`).join("") || `<tr><td colspan="5">No product in this category among the top ten.</td></tr>`;
}

function initWorkflowPreview() {
  const cards = [...document.querySelectorAll(".code-preview-card[data-preview]")];
  const panels = [...document.querySelectorAll(".workflow-code-panel[data-code-panel]")];
  const title = document.querySelector("#workflowCodeTitle");
  if (!cards.length || !panels.length || !title) return;

  const activate = key => {
    cards.forEach(card => {
      const isActive = card.dataset.preview === key;
      card.classList.toggle("is-active", isActive);
      if (isActive) card.setAttribute("aria-current", "step");
      else card.removeAttribute("aria-current");
    });

    panels.forEach(panel => {
      const isActive = panel.dataset.codePanel === key;
      panel.hidden = !isActive;
      panel.classList.toggle("is-active", isActive);
      if (isActive) title.textContent = panel.dataset.filename;
    });
  };

  cards.forEach(card => {
    card.addEventListener("pointerenter", () => activate(card.dataset.preview));
    card.addEventListener("focus", () => activate(card.dataset.preview));
  });

  activate(cards[0].dataset.preview);
}

async function init() {
  const response = await fetch(DATA_URL);
  const data = await response.json();
  const years = [...new Set(data.monthly.map(d => d.month.slice(0,4)))];
  const yearFilter = document.querySelector("#yearFilter");
  years.forEach(year => yearFilter.insertAdjacentHTML("beforeend", `<option value="${year}">${year}</option>`));

  const categories = data.categories.map(d => d.category);
  const categoryFilter = document.querySelector("#categoryFilter");
  categories.forEach(c => categoryFilter.insertAdjacentHTML("beforeend", `<option value="${c}">${c}</option>`));

  const renderYear = () => {
    const selected = yearFilter.value;
    const months = selected === "all" ? data.monthly : data.monthly.filter(d => d.month.startsWith(selected));
    renderKpis(data, months, selected === "all");
    lineChart(months);
  };
  yearFilter.addEventListener("change", renderYear);
  categoryFilter.addEventListener("change", () => productTable(data, categoryFilter.value));

  renderYear();
  categoryBars(data.categories);
  returnDonut(data.returns);
  productTable(data, "all");

  document.querySelector("#negativeShare").textContent = pct(data.kpis.negative_margin_sales_share_pct, 1);
  const wrongSize = data.returns.find(d => d.return_reason === "wrong_size");
  document.querySelector("#wrongSizeShare").textContent = pct(wrongSize?.return_unit_share_pct ?? 0, 1);
  document.querySelector("#dataPeriod").textContent = `${data.meta.date_min} to ${data.meta.date_max}`;
}

initWorkflowPreview();

init().catch(error => {
  console.error(error);
  document.querySelector("#kpiGrid").innerHTML = `<p>Dashboard data could not be loaded.</p>`;
});
