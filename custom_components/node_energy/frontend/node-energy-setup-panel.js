class NodeEnergySetupPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._selectedEntity = '';
  }

  set hass(hass) {
    this._hass = hass;
    const valid = this._validEntities();
    if (!this._selectedEntity || !valid.includes(this._selectedEntity)) {
      this._selectedEntity = valid[0] || '';
    }
    this._render();
  }

  connectedCallback() {
    this._render();
  }

  _validEntities() {
    return Object.entries((this._hass && this._hass.states) || {})
      .filter(([entityId, stateObj]) => {
        if (!entityId.startsWith('sensor.')) return false;
        const apex = stateObj && stateObj.attributes && stateObj.attributes.apex_series;
        return !!apex;
      })
      .map(([entityId]) => entityId)
      .sort();
  }

  _status(message, type = '') {
    const status = this.shadowRoot.querySelector('#status');
    if (!status) return;
    status.textContent = message;
    status.className = `status ${type}`.trim();
  }

  _copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise((resolve, reject) => {
      try {
        const area = document.createElement('textarea');
        area.value = text;
        area.style.position = 'fixed';
        area.style.left = '-9999px';
        document.body.appendChild(area);
        area.focus();
        area.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(area);
        if (!ok) {
          reject(new Error('execCommand copy failed'));
          return;
        }
        resolve();
      } catch (err) {
        reject(err);
      }
    });
  }

  _buildDashboardYaml(entity) {
    return `title: Node Energy
views:
  - title: Overview
    path: overview
    type: sections
    sections:
      - type: grid
        cards:
          - type: custom:apexcharts-card
            header:
              show: true
              title: Node Energy
            graph_span: 72h
            now:
              show: true
              label: Now
            apex_config:
              chart:
                height: 680
                toolbar:
                  show: true
              legend:
                show: true
              xaxis:
                type: datetime
                labels:
                  datetimeUTC: false
                  format: dd MMM HH:mm
              stroke:
                width: [3, 3, 2, 2, 2, 2, 2, 2]
              yaxis:
                - id: soc
                  min: 0
                  max: 100
                  decimalsInFloat: 1
                  title: { text: "SOC %" }
                - id: power
                  opposite: true
                  title: { text: "Power W" }
                - id: sun
                  opposite: true
                  min: -90
                  max: 90
                  title: { text: "Sun elev °" }
            series:
              - entity: ${entity}
                name: SOC (history)
                yaxis_id: soc
                data_generator: return (entity.attributes.apex_series?.soc_actual || []).map(p => [new Date(p.x).getTime(), p.y]);
              - entity: ${entity}
                name: SOC (projection weather)
                yaxis_id: soc
                data_generator: return (entity.attributes.apex_series?.soc_projection_weather || []).map(p => [new Date(p.x).getTime(), p.y]);
              - entity: ${entity}
                name: SOC (projection clear sky)
                yaxis_id: soc
                stroke_dash: 6
                data_generator: return (entity.attributes.apex_series?.soc_projection_clear || []).map(p => [new Date(p.x).getTime(), p.y]);
              - entity: ${entity}
                name: Observed net W
                yaxis_id: power
                data_generator: return (entity.attributes.apex_series?.power_observed || []).map(p => [new Date(p.x).getTime(), p.y]);
              - entity: ${entity}
                name: Modeled net W
                yaxis_id: power
                data_generator: return (entity.attributes.apex_series?.power_modeled || []).map(p => [new Date(p.x).getTime(), p.y]);
              - entity: ${entity}
                name: Production W (weather)
                yaxis_id: power
                data_generator: return (entity.attributes.apex_series?.power_production_weather || []).map(p => [new Date(p.x).getTime(), p.y]);
              - entity: ${entity}
                name: Production W (clear sky)
                yaxis_id: power
                stroke_dash: 6
                data_generator: return (entity.attributes.apex_series?.power_production_clear || []).map(p => [new Date(p.x).getTime(), p.y]);
              - entity: ${entity}
                name: Consumption W
                yaxis_id: power
                data_generator: return (entity.attributes.apex_series?.power_consumption || []).map(p => [new Date(p.x).getTime(), p.y]);
              - entity: ${entity}
                name: Sun elevation (history)
                yaxis_id: sun
                data_generator: return (entity.attributes.apex_series?.sun_history || []).map(p => [new Date(p.x).getTime(), p.y]);
              - entity: ${entity}
                name: Sun elevation (forecast)
                yaxis_id: sun
                stroke_dash: 6
                data_generator: return (entity.attributes.apex_series?.sun_forecast || []).map(p => [new Date(p.x).getTime(), p.y]);
        column_span: 4
`;
  }

  _render() {
    if (!this.shadowRoot) return;

    const valid = this._validEntities();
    const selected = valid.includes(this._selectedEntity) ? this._selectedEntity : (valid[0] || '');
    this._selectedEntity = selected;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 20px;
          color: var(--primary-text-color);
          box-sizing: border-box;
        }
        .wrap {
          max-width: 860px;
          margin: 0 auto;
          display: grid;
          gap: 16px;
        }
        .title {
          margin: 0;
          font-size: 1.5rem;
          font-weight: 700;
        }
        .desc {
          margin: 0;
          color: var(--secondary-text-color);
          line-height: 1.45;
        }
        .card {
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 14px;
          padding: 16px;
          display: grid;
          gap: 12px;
        }
        label {
          font-weight: 600;
        }
        select {
          width: 100%;
          min-height: 44px;
          border: 1px solid var(--divider-color);
          border-radius: 10px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          padding: 0 12px;
          font: inherit;
        }
        button {
          width: 100%;
          min-height: 72px;
          border: none;
          border-radius: 12px;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
          font-size: 1.1rem;
          font-weight: 700;
          cursor: pointer;
        }
        button:disabled {
          opacity: 0.45;
          cursor: not-allowed;
        }
        .status {
          min-height: 1.2em;
          color: var(--secondary-text-color);
        }
        .status.ok { color: var(--success-color, #2e7d32); }
        .status.err { color: var(--error-color, #b00020); }
        .steps {
          margin: 0;
          color: var(--secondary-text-color);
        }
      </style>
      <div class="wrap">
        <h1 class="title">Node Energy Setup</h1>
        <p class="desc">Generate dashboard configuration directly from UI. No manual YAML editing required before copy.</p>
        <div class="card">
          <label for="entity">Node Energy sensor</label>
          <select id="entity" ${valid.length ? '' : 'disabled'}>
            ${valid.map((eid) => `<option value="${eid}" ${eid === selected ? 'selected' : ''}>${eid}</option>`).join('')}
          </select>
          <button id="copy" ${selected ? '' : 'disabled'}>Copy Dashboard Config</button>
          <div id="status" class="status"></div>
          <p class="steps">Then open Dashboard -> Edit -> Raw configuration editor -> Paste -> Save.</p>
        </div>
      </div>
    `;

    const entity = this.shadowRoot.querySelector('#entity');
    const copy = this.shadowRoot.querySelector('#copy');

    if (entity) {
      entity.addEventListener('change', (ev) => {
        this._selectedEntity = ev.target.value;
        this._status('');
      });
    }

    if (copy) {
      copy.addEventListener('click', async () => {
        if (!this._selectedEntity) return;
        try {
          await this._copyText(this._buildDashboardYaml(this._selectedEntity));
          this._status(`Copied dashboard config for ${this._selectedEntity}.`, 'ok');
        } catch (_err) {
          this._status('Could not copy. Use HTTPS/app context and clipboard permissions.', 'err');
        }
      });
    }

    if (!valid.length) {
      this._status('No Node Energy sensors found yet. Configure the integration entry first.', 'err');
    }
  }
}

if (!customElements.get('node-energy-setup-panel')) {
  customElements.define('node-energy-setup-panel', NodeEnergySetupPanel);
}
