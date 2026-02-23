class NodeEnergyCard extends HTMLElement {
  static getStubConfig(hass) {
    const preferred =
      Object.entries((hass && hass.states) || {})
        .filter(
          ([eid, st]) =>
            eid.startsWith("sensor.") &&
            st &&
            st.attributes &&
            st.attributes.forecast &&
            st.attributes.intervals &&
            st.attributes.model
        )
        .map(([eid]) => eid)[0] || "";
    return { entity: preferred, cells: 2, days: 7 };
  }

  static getConfigElement() {
    return document.createElement("node-energy-card-editor");
  }

  setConfig(config) {
    this._config = { entity: "", cells: 2, days: 7, ...config };
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 12;
  }

  _range(series, fallbackMin, fallbackMax, padPct = 0.12) {
    if (!series.length) return [fallbackMin, fallbackMax];
    let mn = Math.min(...series.map((p) => p.y));
    let mx = Math.max(...series.map((p) => p.y));
    if (!Number.isFinite(mn) || !Number.isFinite(mx)) return [fallbackMin, fallbackMax];
    if (mn === mx) {
      mn -= 1;
      mx += 1;
    }
    const span = mx - mn;
    return [mn - span * padPct, mx + span * padPct];
  }

  _polyline(series, mapX, mapY) {
    if (!series.length) return "";
    return series.map((p) => `${mapX(p.x).toFixed(1)},${mapY(p.y).toFixed(1)}`).join(" ");
  }

  _render() {
    if (!this._config || !this._hass) return;

    const st = this._hass.states[this._config.entity];
    if (!st) {
      this.innerHTML = `<ha-card header="Node Energy"><div class="card-content">Entity not found: ${this._config.entity}</div></ha-card>`;
      return;
    }

    const attrs = st.attributes || {};
    const meta = attrs.meta || {};
    const model = attrs.model || {};
    const hist = attrs.history_soc || [];
    const intervals = attrs.intervals || [];
    const forecast = attrs.forecast || {};

    const cells = Number(this._config.cells || 2);
    const days = Number(this._config.days || 7);

    const latestSoc = Number(forecast.latest_soc ?? st.state ?? 0);
    const loadW = Number(model.load_w || 0);
    const solarPeakW = Number(model.solar_peak_w || 0);
    const avgNetW = Number(model.avg_net_w_observed || 0);

    const cellMah = Number(this._config.cell_mah || meta.cell_mah || 3500);
    const cellV = Number(this._config.cell_v || meta.cell_v || 3.7);
    const cellWh = (cellMah / 1000) * cellV;

    const ft = (forecast.times || []).map((t) => new Date(t).getTime());
    const wf = forecast.weather_factor || [];
    const sp = forecast.solar_proxy || [];
    const fSolarElev = forecast.solar_elev || [];

    const n = Math.max(2, Math.min(ft.length - 1, Math.floor(days * 24 * 6)));
    const stepH = 10 / 60;

    const projWeather = [{ x: ft[0], y: latestSoc }];
    const projClear = [{ x: ft[0], y: latestSoc }];

    let sw = latestSoc;
    let sc = latestSoc;
    for (let i = 1; i <= n; i++) {
      const prodW = solarPeakW * Number(sp[i] || 0) * Number(wf[i] || 1);
      const prodC = solarPeakW * Number(sp[i] || 0);
      sw += ((-loadW + prodW) * stepH / (cells * cellWh)) * 100;
      sc += ((-loadW + prodC) * stepH / (cells * cellWh)) * 100;
      sw = Math.max(0, Math.min(100, sw));
      sc = Math.max(0, Math.min(100, sc));
      projWeather.push({ x: ft[i], y: sw });
      projClear.push({ x: ft[i], y: sc });
    }

    const histSeries = hist
      .map((p) => ({ x: new Date(p.t).getTime(), y: Number(p.v) }))
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));

    const allSoc = [...histSeries, ...projWeather, ...projClear];
    if (!allSoc.length) {
      this.innerHTML = `<ha-card header="Node Energy"><div class="card-content">No history/forecast data yet.</div></ha-card>`;
      return;
    }

    const xMin = Math.min(...allSoc.map((p) => p.x));
    const xMax = Math.max(...allSoc.map((p) => p.x));

    const histSunSeries = intervals
      .map((p) => ({ x: new Date(p.tm).getTime(), y: Number(p.sun_elev_deg) }))
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
    const fcSunSeries = ft.slice(0, n + 1).map((x, i) => ({ x, y: Number(fSolarElev[i] || 0) }));
    const allSun = [...histSunSeries, ...fcSunSeries];
    const [sunYMin, sunYMax] = this._range(allSun, -10, 30, 0.08);

    const intervalSeries = intervals
      .map((p) => ({
        x: new Date(p.tm).getTime(),
        obs: Number(p.net_power_obs_w),
        model: Number(p.net_power_model_w),
        prodW: Number(p.production_w),
        prodClear: Number(p.production_clear_w),
        cons: Number(p.consumption_w),
      }))
      .filter((p) => Number.isFinite(p.x));
    const pObs = intervalSeries.filter((p) => Number.isFinite(p.obs)).map((p) => ({ x: p.x, y: p.obs }));
    const pModel = intervalSeries.filter((p) => Number.isFinite(p.model)).map((p) => ({ x: p.x, y: p.model }));
    const pProdW = intervalSeries.filter((p) => Number.isFinite(p.prodW)).map((p) => ({ x: p.x, y: p.prodW }));
    const pProdC = intervalSeries.filter((p) => Number.isFinite(p.prodClear)).map((p) => ({ x: p.x, y: p.prodClear }));
    const pCons = intervalSeries.filter((p) => Number.isFinite(p.cons)).map((p) => ({ x: p.x, y: p.cons }));
    const allPower = [...pObs, ...pModel, ...pProdW, ...pProdC, ...pCons];
    const [powYMin, powYMax] = this._range(allPower, -1, 1, 0.12);

    const nowX = histSeries.length ? histSeries[histSeries.length - 1].x : projWeather[0].x;

    const w = 1000;
    const h = 700;
    const padL = 58;
    const padR = 18;
    const padT = 18;
    const padB = 46;
    const gap = 14;
    const r1H = 120;
    const r2H = 90;
    const r3H = 360;
    const r1Y = padT;
    const r2Y = r1Y + r1H + gap;
    const r3Y = r2Y + r2H + gap;

    const x0 = padL;
    const x1 = w - padR;
    const xSpan = Math.max(1, xMax - xMin);
    const mapX = (x) => x0 + ((x - xMin) / xSpan) * (x1 - x0);
    const mapY = (y, yMin, yMax, top, height) => {
      const span = Math.max(1e-9, yMax - yMin);
      return top + height - ((y - yMin) / span) * height;
    };

    const socY = (v) => mapY(v, 0, 100, r1Y, r1H);
    const sunY = (v) => mapY(v, sunYMin, sunYMax, r2Y, r2H);
    const powY = (v) => mapY(v, powYMin, powYMax, r3Y, r3H);

    const socCombined = [...histSeries, ...projWeather.slice(1)];
    const socPts = this._polyline(socCombined, mapX, socY);
    const socCPts = this._polyline(projClear, mapX, socY);

    const sunHistPts = this._polyline(histSunSeries, mapX, sunY);
    const sunFcPts = this._polyline(fcSunSeries, mapX, sunY);

    const pObsPts = this._polyline(pObs, mapX, powY);
    const pModelPts = this._polyline(pModel, mapX, powY);
    const pProdWPts = this._polyline(pProdW, mapX, powY);
    const pProdCPts = this._polyline(pProdC, mapX, powY);
    const pConsPts = this._polyline(pCons, mapX, powY);

    const nowSX = mapX(nowX);

    const tickCount = 7;
    const ticks = [];
    for (let i = 0; i < tickCount; i++) {
      const t = xMin + ((xMax - xMin) * i) / (tickCount - 1);
      const d = new Date(t);
      const label = `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
      ticks.push({ x: mapX(t), label });
    }

    this.innerHTML = `
      <ha-card header="Node Energy">
        <div class="card-content">
          <div class="chips">
            <div class="chip"><span>Latest</span><b>${latestSoc.toFixed(1)}%</b></div>
            <div class="chip"><span>Load</span><b>${loadW.toFixed(2)} W</b></div>
            <div class="chip"><span>Solar Peak</span><b>${solarPeakW.toFixed(2)} W</b></div>
            <div class="chip"><span>Avg Net</span><b>${avgNetW.toFixed(2)} W</b></div>
            <div class="chip"><span>Cells</span><b>${cells}</b></div>
            <div class="chip"><span>Start Hour</span><b>${meta.start_hour ?? "-"}:00</b></div>
            <div class="chip wide"><span>Weather Entity</span><b>${meta.weather_entity || "(none)"}</b></div>
          </div>

          <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" class="chart">
            <line x1="${x0}" y1="${r1Y + r1H}" x2="${x1}" y2="${r1Y + r1H}" class="axis"></line>
            <line x1="${x0}" y1="${r2Y + r2H}" x2="${x1}" y2="${r2Y + r2H}" class="axis"></line>
            <line x1="${x0}" y1="${r3Y + r3H}" x2="${x1}" y2="${r3Y + r3H}" class="axis"></line>
            <line x1="${x0}" y1="${r1Y}" x2="${x0}" y2="${r3Y + r3H}" class="axis"></line>

            <polyline points="${socPts}" class="soc"></polyline>
            <polyline points="${socCPts}" class="projc"></polyline>

            <polyline points="${sunHistPts}" class="sunh"></polyline>
            <polyline points="${sunFcPts}" class="sunf"></polyline>

            <polyline points="${pObsPts}" class="pobs"></polyline>
            <polyline points="${pModelPts}" class="pmodel"></polyline>
            <polyline points="${pProdWPts}" class="pprodw"></polyline>
            <polyline points="${pProdCPts}" class="pprodc"></polyline>
            <polyline points="${pConsPts}" class="pcons"></polyline>

            <line x1="${nowSX.toFixed(1)}" y1="${r1Y}" x2="${nowSX.toFixed(1)}" y2="${r3Y + r3H}" class="now"></line>
            <text x="${(nowSX + 4).toFixed(1)}" y="${(r1Y + 12).toFixed(1)}" class="txt">Now</text>

            <text x="8" y="${(r1Y + 12).toFixed(1)}" class="txt">SOC</text>
            <text x="8" y="${(r2Y + 12).toFixed(1)}" class="txt">Sun °</text>
            <text x="8" y="${(r3Y + 12).toFixed(1)}" class="txt">Power W</text>

            ${ticks
              .map(
                (t) => `
              <line x1="${t.x.toFixed(1)}" y1="${r3Y + r3H}" x2="${t.x.toFixed(1)}" y2="${r3Y + r3H + 6}" class="axis"></line>
              <text x="${t.x.toFixed(1)}" y="${h - 16}" class="xtick" text-anchor="middle">${t.label}</text>
            `
              )
              .join("")}
          </svg>

          <div id="tooltip" class="tooltip hidden"></div>
          <div class="legend">
            <span class="lg" data-target="soc"><i class="dot soc"></i>SOC (history + projection)</span>
            <span class="lg" data-target="projc"><i class="dot projc"></i>SOC projection (clear)</span>
            <span class="lg" data-target="sunh"><i class="dot sunh"></i>Sun elevation (history)</span>
            <span class="lg" data-target="sunf"><i class="dot sunf"></i>Sun elevation (forecast)</span>
            <span class="lg" data-target="pobs"><i class="dot pobs"></i>Observed net W</span>
            <span class="lg" data-target="pmodel"><i class="dot pmodel"></i>Modeled net W</span>
            <span class="lg" data-target="pprodw"><i class="dot pprodw"></i>Production W (weather)</span>
            <span class="lg" data-target="pprodc"><i class="dot pprodc"></i>Production W (clear)</span>
            <span class="lg" data-target="pcons"><i class="dot pcons"></i>Consumption W</span>
          </div>
        </div>
      </ha-card>
      <style>
        .card-content { padding: 12px; }
        .chips { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin-bottom: 10px; }
        .chip { border: 1px solid var(--divider-color); border-radius: 10px; padding: 8px 10px; background: color-mix(in srgb, var(--card-background-color) 92%, var(--primary-text-color) 8%); }
        .chip.wide { grid-column: span 2; }
        .chip span { display: block; font-size: 11px; color: var(--secondary-text-color); }
        .chip b { font-size: 14px; color: var(--primary-text-color); }

        .chart {
          width: 100%;
          height: 620px;
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 10px;
          margin-top: 8px;
        }

        .axis { stroke: var(--divider-color); stroke-width: 1; }
        .txt { font-size: 11px; fill: var(--secondary-text-color); }
        .xtick { font-size: 10px; fill: var(--secondary-text-color); }
        .now { stroke: var(--secondary-text-color); stroke-width: 1.2; stroke-dasharray: 4 4; }

        .soc { fill: none; stroke: #17a589; stroke-width: 2.8; }
        .projc { fill: none; stroke: #17a589; stroke-width: 1.6; stroke-dasharray: 5 4; }

        .sunh { fill: none; stroke: #b45309; stroke-width: 2.1; }
        .sunf { fill: none; stroke: #f59e0b; stroke-width: 1.7; stroke-dasharray: 5 4; }

        .pobs { fill: none; stroke: #475569; stroke-width: 1.5; }
        .pmodel { fill: none; stroke: #0f766e; stroke-width: 1.6; }
        .pprodw { fill: none; stroke: #d97706; stroke-width: 1.6; }
        .pprodc { fill: none; stroke: #94a3b8; stroke-width: 1.4; stroke-dasharray: 5 4; }
        .pcons { fill: none; stroke: #b91c1c; stroke-width: 1.6; }

        .legend { display: flex; gap: 10px; margin-top: 10px; font-size: 12px; color: var(--secondary-text-color); flex-wrap: wrap; }
        .lg { cursor: pointer; user-select: none; }
        .dot { display: inline-block; width: 10px; height: 10px; border-radius: 999px; margin-right: 6px; vertical-align: -1px; }
        .dot.soc { background: #17a589; }
        .dot.projc { background: transparent; border: 1px dashed #17a589; }
        .dot.sunh { background: #b45309; }
        .dot.sunf { background: transparent; border: 1px dashed #f59e0b; }
        .dot.pobs { background: #475569; }
        .dot.pmodel { background: #0f766e; }
        .dot.pprodw { background: #d97706; }
        .dot.pprodc { background: transparent; border: 1px dashed #94a3b8; }
        .dot.pcons { background: #b91c1c; }
        .fade { opacity: 0.18; transition: opacity 120ms linear; }
        .highlight { opacity: 1 !important; stroke-width: 3.2; }
        .tooltip {
          position: absolute;
          z-index: 5;
          pointer-events: none;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          padding: 6px 8px;
          font-size: 12px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.18);
        }
        .hidden { display: none; }
      </style>
    `;

    const svg = this.querySelector("svg.chart");
    const tooltip = this.querySelector("#tooltip");
    const cardContent = this.querySelector(".card-content");
    const seriesByName = {
      soc: socCombined,
      projc: projClear,
      sunh: histSunSeries,
      sunf: fcSunSeries,
      pobs: pObs,
      pmodel: pModel,
      pprodw: pProdW,
      pprodc: pProdC,
      pcons: pCons,
    };
    const nearestPoint = (arr, x) => {
      if (!arr.length) return null;
      let best = arr[0];
      let bd = Math.abs(arr[0].x - x);
      for (let i = 1; i < arr.length; i++) {
        const d = Math.abs(arr[i].x - x);
        if (d < bd) {
          bd = d;
          best = arr[i];
        }
      }
      return best;
    };

    svg?.addEventListener("mousemove", (ev) => {
      const rect = svg.getBoundingClientRect();
      const rx = Math.max(0, Math.min(rect.width, ev.clientX - rect.left));
      const tx = xMin + (rx / Math.max(1, rect.width)) * (xMax - xMin);
      const rows = [];
      for (const [name, arr] of Object.entries(seriesByName)) {
        const p = nearestPoint(arr, tx);
        if (p) rows.push(`${name}: ${p.y.toFixed(2)}`);
      }
      const date = new Date(tx);
      tooltip.classList.remove("hidden");
      tooltip.innerHTML = `<div><b>${date.toLocaleString()}</b></div><div>${rows.join("<br/>")}</div>`;
      const cRect = cardContent.getBoundingClientRect();
      tooltip.style.left = `${ev.clientX - cRect.left + 12}px`;
      tooltip.style.top = `${ev.clientY - cRect.top + 12}px`;
    });
    svg?.addEventListener("mouseleave", () => tooltip.classList.add("hidden"));

    const polylines = {};
    for (const name of Object.keys(seriesByName)) {
      const el = this.querySelector(`.${name}`);
      if (el) polylines[name] = el;
    }
    this.querySelectorAll(".legend .lg").forEach((el) => {
      el.addEventListener("mouseenter", () => {
        const target = el.getAttribute("data-target");
        Object.entries(polylines).forEach(([name, line]) => {
          line.classList.remove("fade", "highlight");
          if (name === target) line.classList.add("highlight");
          else line.classList.add("fade");
        });
      });
      el.addEventListener("mouseleave", () => {
        Object.values(polylines).forEach((line) => line.classList.remove("fade", "highlight"));
      });
    });
  }
}

class NodeEnergyCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { entity: "", cells: 2, days: 7, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _emitChanged() {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      })
    );
  }

  _render() {
    if (!this._hass || !this._config) return;

    const validSensors = Object.entries(this._hass.states || {})
      .filter(
        ([eid, st]) =>
          eid.startsWith("sensor.") &&
          st &&
          st.attributes &&
          st.attributes.forecast &&
          st.attributes.intervals &&
          st.attributes.model
      )
      .map(([eid, st]) => ({ eid, name: st.attributes.friendly_name || eid }))
      .sort((a, b) => a.name.localeCompare(b.name));

    if (!this._config.entity && validSensors.length) {
      this._config = { ...this._config, entity: validSensors[0].eid };
      this._emitChanged();
    }

    this.innerHTML = `
      <style>
        .wrap { display: grid; gap: 10px; }
        .row { display: grid; gap: 4px; }
        label { font-size: 12px; color: var(--secondary-text-color); }
        input, select {
          padding: 8px;
          border: 1px solid var(--divider-color);
          border-radius: 6px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
        }
      </style>
      <div class="wrap">
        <div class="row">
          <label>Entity</label>
          <select id="entity">
            ${
              validSensors.length
                ? validSensors
                    .map(
                      (s) =>
                        `<option value="${s.eid}" ${
                          s.eid === this._config.entity ? "selected" : ""
                        }>${s.name} (${s.eid})</option>`
                    )
                    .join("")
                : '<option value="">No valid Node Energy entities found</option>'
            }
          </select>
        </div>
        <div class="row">
          <label>Cells</label>
          <input id="cells" type="number" min="1" max="12" step="1" value="${Number(this._config.cells || 2)}" />
        </div>
        <div class="row">
          <label>Days</label>
          <input id="days" type="number" min="1" max="14" step="1" value="${Number(this._config.days || 7)}" />
        </div>
      </div>
    `;

    this.querySelector("#entity")?.addEventListener("change", (ev) => {
      this._config = { ...this._config, entity: ev.target.value };
      this._emitChanged();
    });
    this.querySelector("#cells")?.addEventListener("change", (ev) => {
      const v = Math.max(1, Math.min(12, Number(ev.target.value || 2)));
      this._config = { ...this._config, cells: v };
      this._emitChanged();
    });
    this.querySelector("#days")?.addEventListener("change", (ev) => {
      const v = Math.max(1, Math.min(14, Number(ev.target.value || 7)));
      this._config = { ...this._config, days: v };
      this._emitChanged();
    });
  }
}

if (!customElements.get("node-energy-card")) {
  customElements.define("node-energy-card", NodeEnergyCard);
}
if (!customElements.get("node-energy-card-editor")) {
  customElements.define("node-energy-card-editor", NodeEnergyCardEditor);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "node-energy-card",
  name: "Node Energy Card",
  description: "Unified history + projection for Node Energy integration",
});
