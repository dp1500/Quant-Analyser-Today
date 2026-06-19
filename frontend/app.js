const plotTheme = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: "#e4e4e7", family: "Inter, system-ui, sans-serif" },
  xaxis: { gridcolor: "#27272a", zerolinecolor: "#3f3f46" },
  yaxis: { gridcolor: "#27272a", zerolinecolor: "#3f3f46" },
  margin: { l: 52, r: 18, t: 12, b: 42 },
};

function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${Number(value).toFixed(2)}%`;
}

async function loadDashboard() {
  const res = await fetch("/api/dashboard");
  if (!res.ok) {
    document.getElementById("generatedAt").textContent = "Run scripts/update_data.py to create local dashboard data.";
    return;
  }
  const data = await res.json();
  render(data);
}

function render(data) {
  document.getElementById("generatedAt").textContent = `Generated ${new Date(data.generated_at).toLocaleString()}`;
  document.getElementById("analysisTill").textContent = data.analysis_till || "-";
  document.getElementById("analysisFor").textContent = data.analysis_for || "-";
  const levels = data.nifty.levels;
  document.getElementById("ath1y").textContent = fmt(levels.one_year.ath);
  document.getElementById("atl1y").textContent = fmt(levels.one_year.atl);
  document.getElementById("ath1m").textContent = fmt(levels.one_month.ath);
  document.getElementById("atl1m").textContent = fmt(levels.one_month.atl);

  renderNiftyChart(data.nifty.ohlc, levels);
  renderRegimes(data.nifty.regimes);
  renderForecast(data.nifty.forecast);
  renderOptions(data.nifty.forecast.history, data.options);
  renderBreadth(data.stocks);
}

function renderNiftyChart(ohlc, levels) {
  const x = ohlc.map((d) => d.date);
  const trace = {
    type: "candlestick",
    x,
    open: ohlc.map((d) => d.open),
    high: ohlc.map((d) => d.high),
    low: ohlc.map((d) => d.low),
    close: ohlc.map((d) => d.close),
    increasing: { line: { color: "#22c55e" } },
    decreasing: { line: { color: "#ef4444" } },
    name: "Nifty",
  };
  const shapes = [
    ["1Y ATH", levels.one_year.ath, "#38bdf8"],
    ["1Y ATL", levels.one_year.atl, "#f97316"],
    ["1M ATH", levels.one_month.ath, "#a3e635"],
    ["1M ATL", levels.one_month.atl, "#f43f5e"],
  ].map(([name, y, color]) => ({
    type: "line",
    xref: "paper",
    x0: 0,
    x1: 1,
    y0: y,
    y1: y,
    line: { color, width: 1, dash: "dot" },
    label: { text: `${name} ${fmt(y)}`, textposition: "end", font: { color } },
  }));
  Plotly.newPlot("niftyChart", [trace], { ...plotTheme, shapes, xaxis: { ...plotTheme.xaxis, rangeslider: { visible: false } } }, { responsive: true });
}

function renderRegimes(rows) {
  document.getElementById("regimeRows").innerHTML = rows
    .map(
      (r) => `
        <tr>
          <td>${r.window}</td>
          <td>${r.label}<div class="text-xs text-zinc-500">mom ${fmt(r.momentum_score)}, rev ${fmt(r.reversion_score)}, H ${fmt(r.hurst)}</div></td>
          <td>${pct(r.return_pct)}</td>
          <td>${pct(r.realized_vol_pct)}</td>
        </tr>`
    )
    .join("");
}

function renderForecast(forecast) {
  const history = forecast.history;
  const future = forecast.forecast;
  const histTrace = {
    type: "candlestick",
    x: history.map((d) => d.date),
    open: history.map((d) => d.open),
    high: history.map((d) => d.high),
    low: history.map((d) => d.low),
    close: history.map((d) => d.close),
    name: "Last 5 days",
    increasing: { line: { color: "#22c55e" } },
    decreasing: { line: { color: "#ef4444" } },
  };
  const highTrace = { type: "scatter", mode: "lines", x: future.map((d) => d.date), y: future.map((d) => d.high), line: { color: "#38bdf8" }, name: "Range high" };
  const lowTrace = { type: "scatter", mode: "lines", x: future.map((d) => d.date), y: future.map((d) => d.low), line: { color: "#f97316" }, fill: "tonexty", fillcolor: "rgba(56,189,248,0.12)", name: "Range low" };
  Plotly.newPlot("forecastChart", [histTrace, highTrace, lowTrace], { ...plotTheme, xaxis: { ...plotTheme.xaxis, rangeslider: { visible: false } } }, { responsive: true });
}

function renderOptions(history, options) {
  document.getElementById("oiStatus").textContent = options.message;
  const expiries = options.expiries || [];
  if (!options.available || !expiries.length) {
    document.getElementById("oiCharts").innerHTML = `<div class="empty-state">No OI data yet</div>`;
    document.getElementById("oiChangePanels").innerHTML = "";
    return;
  }
  document.getElementById("oiCharts").innerHTML = expiries
    .map((expiry, idx) => `<div><div class="mini-chart-title">${idx === 0 ? "Current expiry" : "Next expiry"}: ${expiry.expiry} | ATM ${fmt(expiry.atm)}</div><div id="oiChart${idx}" class="chart oi-mini-chart"></div></div>`)
    .join("");
  expiries.forEach((expiry, idx) => renderOiExpiryChart(`oiChart${idx}`, history, expiry));
  renderOiChanges(expiries[0].changes || {});
}

function renderOiExpiryChart(containerId, history, expiry) {
  const levels = expiry.levels || [];
  if (!levels.length) return;
  const x = history.map((d) => d.date);
  const priceTrace = {
    type: "candlestick",
    x,
    open: history.map((d) => d.open),
    high: history.map((d) => d.high),
    low: history.map((d) => d.low),
    close: history.map((d) => d.close),
    name: "Nifty",
    increasing: { line: { color: "#22c55e" } },
    decreasing: { line: { color: "#ef4444" } },
  };
  const strikes = levels.map((d) => Number(d.strike));
  const yMin = Math.min(...strikes, ...history.map((d) => d.low)) - 80;
  const yMax = Math.max(...strikes, ...history.map((d) => d.high)) + 80;
  const putBars = {
    type: "bar",
    orientation: "h",
    x: levels.map((d) => -(d.put_oi || 0)),
    y: strikes,
    xaxis: "x2",
    name: "Put OI",
    marker: { color: "rgba(239,68,68,0.72)" },
    width: 32,
    hovertemplate: "PE %{y}<br>OI %{customdata:,.0f}<extra></extra>",
    customdata: levels.map((d) => d.put_oi || 0),
  };
  const callBars = {
    type: "bar",
    orientation: "h",
    x: levels.map((d) => d.call_oi || 0),
    y: strikes,
    xaxis: "x2",
    name: "Call OI",
    marker: { color: "rgba(34,197,94,0.72)" },
    width: 32,
    hovertemplate: "CE %{y}<br>OI %{x:,.0f}<extra></extra>",
  };
  const maxOi = Math.max(...levels.map((d) => Math.max(d.call_oi || 0, d.put_oi || 0)), 1);
  const shapes = expiry.atm ? [{
    type: "line",
    xref: "paper",
    x0: 0,
    x1: 1,
    y0: expiry.atm,
    y1: expiry.atm,
    line: { color: "rgba(250,204,21,0.9)", width: 1, dash: "dot" },
    label: { text: `ATM ${fmt(expiry.atm)}`, textposition: "start", font: { color: "#facc15", size: 11 } },
  }] : [];
  Plotly.newPlot(containerId, [priceTrace, putBars, callBars], {
    ...plotTheme,
    shapes,
    barmode: "relative",
    bargap: 0.1,
    xaxis: { ...plotTheme.xaxis, domain: [0, 0.68], rangeslider: { visible: false } },
    xaxis2: {
      domain: [0.72, 1],
      anchor: "y",
      gridcolor: "#27272a",
      zerolinecolor: "#52525b",
      range: [-maxOi * 1.1, maxOi * 1.1],
      title: { text: "OI", font: { size: 11 } },
      side: "top",
      tickformat: "~s",
    },
    yaxis: { ...plotTheme.yaxis, range: [yMin, yMax], title: { text: "Nifty / Strike", font: { size: 11 } } },
    legend: { orientation: "h", x: 0, y: 1.08 },
  }, { responsive: true });
}

function renderOiChanges(changes) {
  const labels = [
    ["30m", "Last 30m"],
    ["1h", "Last 1h"],
    ["2h", "Last 2h"],
    ["day", "Full day"],
  ];
  document.getElementById("oiChangePanels").innerHTML = labels
    .map(([key, label]) => {
      const rows = changes[key] || [];
      const body = rows.length
        ? rows.slice(0, 4).map((r) => {
            const isCall = r.side === "CALL";
            const tone = Number(r.oi_change || 0) >= 0 ? "text-emerald-400" : "text-red-400";
            return `<div class="oi-change-row">
              <span class="${isCall ? "text-emerald-400" : "text-red-400"}">${isCall ? "CE" : "PE"} ${fmt(r.strike)}</span>
              <strong class="${tone}">${fmt(r.oi_change)}</strong>
            </div>`;
          }).join("")
        : `<div class="empty-state compact">No intraday candles</div>`;
      return `<div class="oi-change-card"><h3>${label}</h3>${body}</div>`;
    })
    .join("");
}

function renderBreadth(stocks) {
  const breadth = stocks.breadth || {};
  const scanner = stocks.scanner || {};
  const s = breadth.summary || {};
  document.getElementById("stocksLoaded").textContent = fmt(s.stocks_loaded);
  document.getElementById("above20").textContent = pct(s.above_20dma_pct);
  document.getElementById("median5d").textContent = pct(s.median_5d_return);
  document.getElementById("median20d").textContent = pct(s.median_20d_return);
  const ss = scanner.summary || {};
  document.getElementById("scannerSummary").textContent = `${fmt(ss.scanned)} stocks scanned | ${fmt(ss.mean_reversion_count)} reversion | ${fmt(ss.momentum_count)} momentum`;
  renderSetupList("meanReversionList", scanner.mean_reversion || [], "mean");
  renderSetupList("momentumList", scanner.momentum || [], "momentum");
}

function renderSetupList(id, rows, type) {
  if (!rows.length) {
    document.getElementById(id).innerHTML = `<div class="empty-state">No clean setup passed the filters.</div>`;
    return;
  }
  document.getElementById(id).innerHTML = rows
    .map((r) => {
      const tip = type === "mean" ? r.mean_tip : r.momentum_tip;
      const value = type === "mean" ? `z ${fmt(r.mean_zscore)}` : `${pct(r.return_15d)} 15D`;
      const tone = tip && (tip.includes("Long") || tip.includes("Bullish")) ? "text-emerald-400" : tip && tip.includes("Short") ? "text-red-400" : "text-zinc-300";
      return `<div class="rank-item tall">
        <div>
          <strong>${r.symbol}</strong>
          <span>${tip}</span>
        </div>
        <span class="${tone}">${value}</span>
      </div>`;
    })
    .join("");
}

loadDashboard();
