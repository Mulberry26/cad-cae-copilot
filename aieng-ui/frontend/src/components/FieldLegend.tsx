import { useState, type CSSProperties } from "react";

import type { SolverFieldDescriptor } from "../types";
import {
  COLORMAP_NAMES,
  colormapCssStops,
  type FieldColorMapping,
} from "./viewer/fieldColors";
import { formatFieldValue, legendTicks, resultFieldLabel } from "./viewer/resultFields";

type FieldLegendProps = {
  fieldDescriptor: SolverFieldDescriptor | null;
  mapping: FieldColorMapping;
  onMappingChange(mapping: FieldColorMapping): void;
};

const SHELL: CSSProperties = {
  position: "absolute",
  top: 12,
  right: 12,
  zIndex: 5,
  background: "rgba(17, 24, 39, 0.82)",
  color: "#e5e7eb",
  borderRadius: 8,
  padding: "8px 10px",
  font: "12px/1.3 system-ui, sans-serif",
  display: "flex",
  flexDirection: "column",
  gap: 6,
  pointerEvents: "auto",
  minWidth: 180,
  maxWidth: 240,
};

const ROW: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  flexWrap: "wrap",
};

const LABEL: CSSProperties = {
  minWidth: 70,
  opacity: 0.85,
};

const INPUT: CSSProperties = {
  width: 80,
  background: "rgba(255,255,255,0.08)",
  border: "1px solid #374151",
  borderRadius: 4,
  color: "#e5e7eb",
  padding: "2px 6px",
  fontSize: 12,
};

const SELECT: CSSProperties = {
  background: "rgba(255,255,255,0.08)",
  border: "1px solid #374151",
  borderRadius: 4,
  color: "#e5e7eb",
  padding: "2px 6px",
  fontSize: 12,
};

const BUTTON: CSSProperties = {
  background: "rgba(255,255,255,0.08)",
  border: "1px solid #374151",
  borderRadius: 4,
  color: "#e5e7eb",
  padding: "2px 8px",
  fontSize: 11,
  cursor: "pointer",
};

function clampBands(value: number): number {
  return Math.max(2, Math.min(64, Math.round(value)));
}

// Color scale bar for the active result field: label, gradient, min↔max ticks
// with units. Honest when the descriptor is not real solver data.
export function FieldLegend({
  fieldDescriptor,
  mapping,
  onMappingChange,
}: FieldLegendProps) {
  const [expanded, setExpanded] = useState(true);

  if (!fieldDescriptor) return null;
  const label = resultFieldLabel(fieldDescriptor.field_name);
  const unit = fieldDescriptor.unit ?? "";
  const hasRealData =
    fieldDescriptor.source === "frd" &&
    Array.isArray(fieldDescriptor.values) &&
    fieldDescriptor.values.length > 0;

  const stops = colormapCssStops(mapping.colormap, 10, mapping.bands);
  const gradient = `linear-gradient(to top, ${stops.join(", ")})`;
  // Ticks high→low so the top of the bar (high color) reads as the max.
  const ticks = legendTicks(fieldDescriptor.min_value, fieldDescriptor.max_value, 5).reverse();

  function updateClamp(
    key: "clampMin" | "clampMax",
    raw: string,
  ) {
    const value = raw.trim() === "" ? null : Number(raw);
    onMappingChange({
      ...mapping,
      [key]: value === null || Number.isNaN(value) ? null : value,
    });
  }

  return (
    <div className="field-legend" style={SHELL}>
      <div style={{ ...ROW, justifyContent: "space-between" }}>
        <strong>{label}</strong>
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          style={BUTTON}
          aria-expanded={expanded}
          aria-label={expanded ? "Collapse legend" : "Expand legend"}
        >
          {expanded ? "−" : "+"}
        </button>
      </div>

      {!hasRealData ? (
        <span style={{ opacity: 0.75 }}>No solver result for this field.</span>
      ) : (
        <>
          <div style={{ display: "flex", gap: 8 }}>
            <div
              aria-hidden
              style={{
                width: 14,
                height: 120,
                borderRadius: 3,
                background: gradient,
                border: "1px solid #374151",
              }}
            />
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                height: 120,
              }}
            >
              {ticks.map((t, i) => (
                <span key={i} style={{ fontVariantNumeric: "tabular-nums" }}>
                  {formatFieldValue(t, unit)}
                </span>
              ))}
            </div>
          </div>

          {expanded && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
              <div style={ROW}>
                <span style={LABEL}>Colormap</span>
                <select
                  value={mapping.colormap}
                  onChange={(event) =>
                    onMappingChange({
                      ...mapping,
                      colormap: event.target.value as FieldColorMapping["colormap"],
                    })
                  }
                  style={SELECT}
                  aria-label="Colormap"
                >
                  {COLORMAP_NAMES.map((name) => (
                    <option key={name} value={name}>
                      {name[0].toUpperCase() + name.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              <div style={ROW}>
                <span style={LABEL}>Clamp min</span>
                <input
                  type="number"
                  step="any"
                  value={mapping.clampMin ?? ""}
                  onChange={(event) => updateClamp("clampMin", event.target.value)}
                  style={INPUT}
                  placeholder="Auto"
                  aria-label="Clamp minimum"
                />
              </div>

              <div style={ROW}>
                <span style={LABEL}>Clamp max</span>
                <input
                  type="number"
                  step="any"
                  value={mapping.clampMax ?? ""}
                  onChange={(event) => updateClamp("clampMax", event.target.value)}
                  style={INPUT}
                  placeholder="Auto"
                  aria-label="Clamp maximum"
                />
              </div>

              <div style={ROW}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={mapping.bands != null}
                    onChange={(event) =>
                      onMappingChange({
                        ...mapping,
                        bands: event.target.checked ? 8 : null,
                      })
                    }
                  />
                  Bands
                </label>
                {mapping.bands != null && (
                  <input
                    type="number"
                    min={2}
                    max={64}
                    value={mapping.bands}
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      onMappingChange({
                        ...mapping,
                        bands: Number.isNaN(value) ? 8 : clampBands(value),
                      });
                    }}
                    style={{ ...INPUT, width: 48 }}
                    aria-label="Band count"
                  />
                )}
              </div>

              <div style={ROW}>
                <span style={LABEL}>Threshold</span>
                <input
                  type="number"
                  step="any"
                  value={mapping.threshold ?? ""}
                  onChange={(event) => {
                    const value =
                      event.target.value.trim() === ""
                        ? null
                        : Number(event.target.value);
                    onMappingChange({
                      ...mapping,
                      threshold:
                        value === null || Number.isNaN(value) ? null : value,
                    });
                  }}
                  style={INPUT}
                  placeholder="None"
                  aria-label="Threshold"
                />
              </div>
            </div>
          )}

          {fieldDescriptor.bbox_status === "suspicious" ? (
            <span style={{ color: "#f59e0b" }}>
              ⚠ results may not align with current geometry
            </span>
          ) : null}
        </>
      )}
    </div>
  );
}
