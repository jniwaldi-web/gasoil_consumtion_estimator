// Gasoil Consumption Estimator - custom Lovelace card.
// Vanilla JS, no build step. Registers <gasoil-card> as custom:gasoil-card.

const STAT_FIELDS = [
  { key: "consumed_entity", label: "Consumo estimado", unit: "L", icon: "\u{1F6E2}️" },
  { key: "since_last_entity", label: "Desde la última lectura", unit: "L", icon: "⛽" },
  { key: "ratio_entity", label: "Ratio", unit: "L/kWh", icon: "⚖️" },
  { key: "last_reading_entity", label: "Lectura del medidor", unit: "L", icon: "\u{1F522}" },
  { key: "last_reading_time_entity", label: "Última lectura", unit: "", icon: "\u{1F551}", isDate: true },
  { key: "energy_entity", label: "Energía actual", unit: "kWh", icon: "⚡" },
  { key: "total_measured_entity", label: "Total medido", unit: "L", icon: "\u{1F4CF}" },
  { key: "remaining_entity", label: "Restante", unit: "L", icon: "\u{1F6E2}️" },
  { key: "percentage_entity", label: "Depósito", unit: "%", icon: "\u{1F4CA}" },
];

const UNAVAILABLE = ["unavailable", "unknown", "none", "", null, undefined];

class GasoilCard extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._config = {};
    this._statusTimer = null;
    this.attachShadow({ mode: "open" });
    this._built = false;
  }

  // Default config used by the Lovelace editor / card picker.
  static getStubConfig() {
    return {
      type: "custom:gasoil-card",
      title: "Consumo de gasoil",
      consumed_entity: "sensor.estimador_gasoil_estimated_gasoil_consumed",
      since_last_entity:
        "sensor.estimador_gasoil_estimated_gasoil_since_last_reading",
      ratio_entity: "sensor.estimador_gasoil_gasoil_liters_per_kwh",
      last_reading_entity: "sensor.estimador_gasoil_last_gasoil_manual_reading",
      last_reading_time_entity:
        "sensor.estimador_gasoil_last_gasoil_reading_time",
      energy_entity: "sensor.estimador_gasoil_current_energy_kwh",
      total_measured_entity: "sensor.estimador_gasoil_total_gasoil_measured",
    };
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Configuración inválida para gasoil-card");
    }
    if (!config.consumed_entity) {
      throw new Error("gasoil-card requiere al menos 'consumed_entity'");
    }
    this._config = { title: "Consumo de gasoil", ...config };
    this._built = false;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  // Format a numeric state with up to 2 decimals; "—" when unavailable.
  _formatNumber(state) {
    if (!state || UNAVAILABLE.includes(state.state)) return "—";
    const num = parseFloat(state.state);
    if (Number.isNaN(num)) return state.state;
    return num.toLocaleString("es-ES", { maximumFractionDigits: 2 });
  }

  // Format a timestamp state into a readable local date/time.
  _formatDate(state) {
    if (!state || UNAVAILABLE.includes(state.state)) return "—";
    const date = new Date(state.state);
    if (Number.isNaN(date.getTime())) return state.state;
    return date.toLocaleString("es-ES", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  // Build the static DOM skeleton once.
  _build() {
    const style = document.createElement("style");
    style.textContent = `
      ha-card, .card {
        background: var(--ha-card-background, var(--card-background-color, #fff));
        border-radius: var(--ha-card-border-radius, 12px);
        box-shadow: var(--ha-card-box-shadow, none);
        padding: 16px;
        color: var(--primary-text-color, #212121);
      }
      .title {
        font-size: 1.25rem;
        font-weight: 500;
        margin-bottom: 12px;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 10px;
      }
      .stat {
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 10px;
        padding: 10px 12px;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .stat .label {
        font-size: 0.75rem;
        color: var(--secondary-text-color, #727272);
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .stat .value {
        font-size: 1.15rem;
        font-weight: 600;
      }
      .stat .unit {
        font-size: 0.8rem;
        font-weight: 400;
        color: var(--secondary-text-color, #727272);
        margin-left: 2px;
      }
      .form {
        margin-top: 16px;
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: flex-end;
      }
      .field {
        display: flex;
        flex-direction: column;
        gap: 4px;
        flex: 1 1 160px;
      }
      .field label {
        font-size: 0.75rem;
        color: var(--secondary-text-color, #727272);
      }
      .field input {
        padding: 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color, #e0e0e0);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color, #212121);
        font-size: 0.95rem;
      }
      button {
        padding: 9px 16px;
        border: none;
        border-radius: 8px;
        background: var(--primary-color, #03a9f4);
        color: var(--text-primary-color, #fff);
        font-size: 0.95rem;
        cursor: pointer;
        flex: 0 0 auto;
      }
      button:hover { opacity: 0.9; }
      button:disabled { opacity: 0.5; cursor: default; }
      .status {
        margin-top: 10px;
        font-size: 0.9rem;
        min-height: 1.2em;
      }
      .status.ok { color: var(--success-color, #4caf50); }
      .status.err { color: var(--error-color, #f44336); }
    `;

    const card = document.createElement("ha-card");
    card.className = "card";
    card.innerHTML = `
      <div class="title"></div>
      <div class="grid"></div>
      <div class="form">
        <div class="field">
          <label class="lit-label">Litros que marca el medidor</label>
          <input class="liters" type="number" min="0" step="0.01"
                 placeholder="0.00" inputmode="decimal" />
        </div>
        <div class="field">
          <label>Fecha y hora (opcional)</label>
          <input class="ts" type="datetime-local" />
        </div>
        <button class="submit">Añadir lectura</button>
      </div>
      <div class="status"></div>
    `;

    this.shadowRoot.innerHTML = "";
    this.shadowRoot.appendChild(style);
    this.shadowRoot.appendChild(card);

    this._elTitle = card.querySelector(".title");
    this._elGrid = card.querySelector(".grid");
    this._elLiters = card.querySelector(".liters");
    this._elTs = card.querySelector(".ts");
    this._elSubmit = card.querySelector(".submit");
    this._elStatus = card.querySelector(".status");

    this._elSubmit.addEventListener("click", () => this._submit());
    this._built = true;
  }

  _render() {
    if (!this._config) return;
    if (!this._built) this._build();

    this._elTitle.textContent = this._config.title || "Consumo de gasoil";

    // Rebuild the stats grid from configured entities.
    this._elGrid.innerHTML = "";
    if (!this._hass) return;

    for (const field of STAT_FIELDS) {
      const entityId = this._config[field.key];
      if (!entityId) continue;
      const state = this._hass.states[entityId];
      const value = field.isDate
        ? this._formatDate(state)
        : this._formatNumber(state);

      const cell = document.createElement("div");
      cell.className = "stat";
      const unit = field.unit && value !== "—"
        ? `<span class="unit">${field.unit}</span>`
        : "";
      cell.innerHTML = `
        <span class="label">${field.icon} ${field.label}</span>
        <span class="value">${value}${unit}</span>
      `;
      this._elGrid.appendChild(cell);
    }
  }

  // Build an ISO 8601 string with the local timezone offset.
  _toLocalIso(datetimeLocal) {
    const date = new Date(datetimeLocal);
    if (Number.isNaN(date.getTime())) return null;
    const pad = (n) => String(Math.abs(n)).padStart(2, "0");
    const off = -date.getTimezoneOffset();
    const sign = off >= 0 ? "+" : "-";
    const hh = pad(Math.floor(Math.abs(off) / 60));
    const mm = pad(Math.abs(off) % 60);
    const y = date.getFullYear();
    const mo = pad(date.getMonth() + 1);
    const d = pad(date.getDate());
    const h = pad(date.getHours());
    const mi = pad(date.getMinutes());
    const s = pad(date.getSeconds());
    return `${y}-${mo}-${d}T${h}:${mi}:${s}${sign}${hh}:${mm}`;
  }

  _showStatus(message, ok) {
    this._elStatus.textContent = message;
    this._elStatus.className = `status ${ok ? "ok" : "err"}`;
    if (this._statusTimer) clearTimeout(this._statusTimer);
    this._statusTimer = setTimeout(() => {
      this._elStatus.textContent = "";
      this._elStatus.className = "status";
    }, 4000);
  }

  async _submit() {
    if (!this._hass) return;
    const raw = this._elLiters.value;
    const liters = parseFloat(raw);
    if (raw === "" || Number.isNaN(liters) || liters < 0) {
      this._showStatus("Introduce un valor de litros válido (≥ 0).", false);
      return;
    }

    const payload = { liters };
    if (this._config.config_entry_id) {
      payload.config_entry_id = this._config.config_entry_id;
    }
    if (this._elTs.value) {
      const iso = this._toLocalIso(this._elTs.value);
      if (iso) payload.timestamp = iso;
    }

    this._elSubmit.disabled = true;
    try {
      await this._hass.callService(
        "gasoil_consumption_estimator",
        "add_manual_reading",
        payload
      );
      this._showStatus("Lectura registrada", true);
      this._elLiters.value = "";
      this._elTs.value = "";
    } catch (err) {
      const msg =
        (err && (err.message || err.error)) || "Error al registrar la lectura";
      this._showStatus(msg, false);
    } finally {
      this._elSubmit.disabled = false;
    }
  }
}

customElements.define("gasoil-card", GasoilCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "gasoil-card",
  name: "Estimador de consumo de gasoil",
  description:
    "Muestra la estimación de consumo de gasoil y permite añadir lecturas manuales.",
});
