import * as THREE from "three";

// Field/solver color mapping: sample a colormap, paint a Y-normalized preview,
// or map per-node solver values onto displayed mesh vertices via a spatial grid.
// All pure THREE.js — no React, unit-testable in isolation.

export const COLORMAP_NAMES = ["thermal", "coolwarm", "viridis", "grayscale"] as const;
export type ColormapName = (typeof COLORMAP_NAMES)[number];

export type FieldColorMappingOptions = {
  clampMin?: number | null;
  clampMax?: number | null;
  bands?: number | null;
  threshold?: number | null;
};

export type FieldColorMapping = {
  colormap: ColormapName;
  clampMin: number | null;
  clampMax: number | null;
  bands: number | null;
  threshold: number | null;
};

export const DEFAULT_FIELD_COLOR_MAPPING: FieldColorMapping = {
  colormap: "thermal",
  clampMin: null,
  clampMax: null,
  bands: null,
  threshold: null,
};

const NO_COLOR = new THREE.Color(0.5, 0.5, 0.5);

// CSS color stops across a colormap, for a legend gradient bar (low→high).
export function colormapCssStops(
  name?: string | null,
  count = 8,
  bands?: number | null,
): string[] {
  const stops: string[] = [];
  const n = bands && bands >= 2 ? bands : Math.max(2, count);
  for (let i = 0; i < n; i += 1) {
    const t = i / (n - 1);
    const displayT = bands && bands >= 2 ? quantize(t, bands) : t;
    const c = sampleColormap(displayT, name);
    stops.push(
      `rgb(${Math.round(c.r * 255)}, ${Math.round(c.g * 255)}, ${Math.round(c.b * 255)})`,
    );
  }
  return stops;
}

function quantize(t: number, bands: number): number {
  return Math.floor(t * bands) / Math.max(1, bands - 1);
}

export function sampleColormap(t: number, name?: string | null): THREE.Color {
  const c = Math.max(0, Math.min(1, t));
  if (name === "coolwarm") {
    // blue(0) -> white(0.5) -> red(1)
    const r = c < 0.5 ? 0.2 + c * 1.6 : 1.0;
    const g = c < 0.5 ? 0.2 + c * 1.6 : 1.0 - (c - 0.5) * 2.0;
    const b = c < 0.5 ? 1.0 : 1.0 - (c - 0.5) * 1.6;
    return new THREE.Color(r, g, b);
  }
  if (name === "viridis") {
    // Perceptually-uniform purple -> teal -> yellow
    const r = Math.max(0, Math.min(1, 0.267 + 0.105 * c - 0.63 * c * c + 1.36 * c * c * c));
    const g = Math.max(0, Math.min(1, 0.004 + 0.898 * c + 0.05 * c * c));
    const b = Math.max(0, Math.min(1, 0.329 + 0.644 * c - 1.5 * c * c + 0.58 * c * c * c));
    return new THREE.Color(r, g, b);
  }
  if (name === "grayscale") {
    return new THREE.Color(c, c, c);
  }
  // thermal: blue -> cyan -> green -> yellow -> red
  const r = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * c - 3)));
  const g = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * c - 2)));
  const b = Math.max(0, Math.min(1, 1.5 - Math.abs(4 * c - 1)));
  return new THREE.Color(r, g, b);
}

export function applyYNormalizedColors(object: THREE.Object3D, colormap?: string | null): boolean {
  let applied = false;
  object.traverse((node) => {
    if (!(node instanceof THREE.Mesh)) return;
    const geo = node.geometry as THREE.BufferGeometry;
    const pos = geo.attributes.position;
    if (!pos) return;
    let yMin = Infinity;
    let yMax = -Infinity;
    for (let i = 0; i < pos.count; i++) {
      const y = pos.getY(i);
      if (y < yMin) yMin = y;
      if (y > yMax) yMax = y;
    }
    const yRange = yMax > yMin ? yMax - yMin : 1;
    const colors = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) {
      const col = sampleColormap((pos.getY(i) - yMin) / yRange, colormap);
      colors[i * 3] = col.r;
      colors[i * 3 + 1] = col.g;
      colors[i * 3 + 2] = col.b;
    }
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    node.material = new THREE.MeshStandardMaterial({ vertexColors: true, metalness: 0.1, roughness: 0.65 });
    applied = true;
  });
  return applied;
}

type UniformGrid = {
  cellSize: number;
  minX: number;
  minY: number;
  minZ: number;
  cells: Map<string, number[]>;
};

export function buildUniformGrid(nodeCoords: [number, number, number][]): UniformGrid {
  if (nodeCoords.length === 0) {
    return { cellSize: 1, minX: 0, minY: 0, minZ: 0, cells: new Map() };
  }
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (const [x, y, z] of nodeCoords) {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
    minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    minZ = Math.min(minZ, z); maxZ = Math.max(maxZ, z);
  }
  const dx = maxX - minX, dy = maxY - minY, dz = maxZ - minZ;
  const diagonal = Math.sqrt(dx * dx + dy * dy + dz * dz);
  const cellSize = Math.max(diagonal / Math.sqrt(nodeCoords.length), 1e-6);

  const cells = new Map<string, number[]>();
  for (let i = 0; i < nodeCoords.length; i++) {
    const [x, y, z] = nodeCoords[i];
    const ix = Math.floor((x - minX) / cellSize);
    const iy = Math.floor((y - minY) / cellSize);
    const iz = Math.floor((z - minZ) / cellSize);
    const key = `${ix},${iy},${iz}`;
    if (!cells.has(key)) cells.set(key, []);
    cells.get(key)!.push(i);
  }
  return { cellSize, minX, minY, minZ, cells };
}

export function nearestNodeIndex(
  vx: number,
  vy: number,
  vz: number,
  grid: UniformGrid,
  nodeCoords: [number, number, number][],
): number {
  const { cellSize, minX, minY, minZ, cells } = grid;
  const ix = Math.floor((vx - minX) / cellSize);
  const iy = Math.floor((vy - minY) / cellSize);
  const iz = Math.floor((vz - minZ) / cellSize);

  let bestIdx = -1;
  let bestDist = Infinity;

  for (let dx = -1; dx <= 1; dx += 1) {
    for (let dy = -1; dy <= 1; dy += 1) {
      for (let dz = -1; dz <= 1; dz += 1) {
        const key = `${ix + dx},${iy + dy},${iz + dz}`;
        const candidates = cells.get(key);
        if (!candidates) continue;
        for (const idx of candidates) {
          const [nx, ny, nz] = nodeCoords[idx];
          const dist2 = (vx - nx) ** 2 + (vy - ny) ** 2 + (vz - nz) ** 2;
          if (dist2 < bestDist) {
            bestDist = dist2;
            bestIdx = idx;
          }
        }
      }
    }
  }

  return bestIdx;
}

export function applyFieldColors(
  object: THREE.Object3D,
  values: number[],
  nodeCoords: [number, number, number][],
  minVal: number,
  maxVal: number,
  colormap?: string | null,
  options?: FieldColorMappingOptions,
): { applied: boolean; bboxStatus: "aligned" | "suspicious" | null; warnings: string[] } {
  let applied = false;
  const warnings: string[] = [];
  const valueRange = maxVal > minVal ? maxVal - minVal : 1;

  const grid = buildUniformGrid(nodeCoords);
  const bboxCheck = checkBboxAlignment(nodeCoords, object);

  const clampMin = options?.clampMin ?? null;
  const clampMax = options?.clampMax ?? null;
  const displayMin = clampMin != null ? Math.max(clampMin, minVal) : minVal;
  const displayMax = clampMax != null ? Math.min(clampMax, maxVal) : maxVal;
  const displayRange = displayMax > displayMin ? displayMax - displayMin : 1;
  const bands = options?.bands && options.bands >= 2 ? options.bands : null;
  const threshold = options?.threshold ?? null;

  object.traverse((node) => {
    if (!(node instanceof THREE.Mesh)) return;
    const geo = node.geometry as THREE.BufferGeometry;
    const pos = geo.attributes.position;
    if (!pos) return;
    const colors = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) {
      const vx = pos.getX(i);
      const vy = pos.getY(i);
      const vz = pos.getZ(i);
      const bestIdx = nearestNodeIndex(vx, vy, vz, grid, nodeCoords);
      const val = values[bestIdx] ?? minVal;

      if (threshold != null && val < threshold) {
        colors[i * 3] = NO_COLOR.r;
        colors[i * 3 + 1] = NO_COLOR.g;
        colors[i * 3 + 2] = NO_COLOR.b;
        continue;
      }

      const clamped = Math.max(displayMin, Math.min(displayMax, val));
      let t = (clamped - displayMin) / displayRange;
      if (bands != null) {
        t = quantize(t, bands);
      }
      const col = sampleColormap(t, colormap);
      colors[i * 3] = col.r;
      colors[i * 3 + 1] = col.g;
      colors[i * 3 + 2] = col.b;
    }
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    node.material = new THREE.MeshStandardMaterial({
      vertexColors: true,
      metalness: 0.1,
      roughness: 0.65,
      side: THREE.DoubleSide,
    });
    applied = true;
  });

  return { applied, bboxStatus: bboxCheck.status, warnings };
}

function checkBboxAlignment(
  nodeCoords: [number, number, number][],
  object: THREE.Object3D,
): { status: "aligned" | "suspicious" | null } {
  if (nodeCoords.length === 0) return { status: null };

  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (const [x, y, z] of nodeCoords) {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
    minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    minZ = Math.min(minZ, z); maxZ = Math.max(maxZ, z);
  }
  const nodeCenter = new THREE.Vector3(
    (minX + maxX) / 2,
    (minY + maxY) / 2,
    (minZ + maxZ) / 2,
  );
  const nodeSize = new THREE.Vector3(
    Math.max(1e-6, maxX - minX),
    Math.max(1e-6, maxY - minY),
    Math.max(1e-6, maxZ - minZ),
  );

  const box = new THREE.Box3().setFromObject(object);
  const meshCenter = new THREE.Vector3();
  const meshSize = new THREE.Vector3();
  box.getCenter(meshCenter);
  box.getSize(meshSize);

  const centerOffset = nodeCenter.distanceTo(meshCenter);
  const sizeRatio = Math.max(
    meshSize.x / nodeSize.x,
    meshSize.y / nodeSize.y,
    meshSize.z / nodeSize.z,
    nodeSize.x / meshSize.x,
    nodeSize.y / meshSize.y,
    nodeSize.z / meshSize.z,
  );

  const threshold = Math.max(nodeSize.length(), meshSize.length()) * 0.25;
  if (centerOffset > threshold || sizeRatio > 5) {
    return { status: "suspicious" };
  }
  return { status: "aligned" };
}
