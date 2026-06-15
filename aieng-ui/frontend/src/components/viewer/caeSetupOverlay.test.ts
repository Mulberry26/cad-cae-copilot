/**
 * @vitest-environment happy-dom
 */
import { describe, expect, it } from "vitest";
import * as THREE from "three";

import { buildCaeSetupOverlayGroup, disposeCaeSetupOverlayGroup } from "./caeSetupOverlay";
import type { BrepGraphSnapshot } from "../../appTypes";
import type { CaeSetupOverlayResponse } from "../../types";

const IDENTITY_TRANSFORM = { scale: 1, isGlb: false };

function makeBoxObject(): THREE.Mesh {
  const geometry = new THREE.BoxGeometry(10, 10, 2);
  return new THREE.Mesh(geometry, new THREE.MeshStandardMaterial());
}

function makeBrepSnapshot(): BrepGraphSnapshot {
  return {
    faces: {
      face_002: {
        id: "face_002",
        surface_type: "plane",
        bounding_box: [0, 0, 1, 10, 10, 1],
        center: [5, 5, 1],
        normal: [0, 0, 1],
      },
      face_003: {
        id: "face_003",
        surface_type: "plane",
        bounding_box: [0, 0, -1, 10, 10, -1],
        center: [5, 5, -1],
        normal: [0, 0, -1],
      },
    },
  };
}

function makeOverlay(available = true): CaeSetupOverlayResponse {
  return {
    available,
    schema_version: "0.1",
    analysis_type: "static_structural",
    material_name: "Al6061-T6",
    loads: [
      {
        id: "load_001",
        target_feature: "base",
        face_ids: ["face_002"],
        magnitude_n: 500,
        direction: [0, 0, -1],
        type: "force",
      },
    ],
    constraints: [
      {
        id: "bc_001",
        target_feature: "hole",
        face_ids: ["face_003"],
        type: "fixed",
      },
    ],
    warnings: [],
  };
}

describe("buildCaeSetupOverlayGroup", () => {
  it("returns an empty group when the overlay is unavailable", () => {
    const group = buildCaeSetupOverlayGroup(
      { available: false, loads: [], constraints: [] },
      makeBrepSnapshot(),
      makeBoxObject(),
      IDENTITY_TRANSFORM,
    );
    expect(group.children.length).toBe(0);
  });

  it("returns an empty group when the B-Rep snapshot is missing", () => {
    const group = buildCaeSetupOverlayGroup(makeOverlay(), null, makeBoxObject(), IDENTITY_TRANSFORM);
    expect(group.children.length).toBe(0);
  });

  it("creates load arrows, constraint glyphs, and labels", () => {
    const group = buildCaeSetupOverlayGroup(makeOverlay(), makeBrepSnapshot(), makeBoxObject(), IDENTITY_TRANSFORM);
    const arrows = group.children.filter((c) => c instanceof THREE.ArrowHelper);
    const sprites = group.children.filter((c) => c instanceof THREE.Sprite);
    const glyphs = group.children.filter((c) => c instanceof THREE.Mesh && !(c instanceof THREE.Sprite));
    expect(arrows.length).toBeGreaterThanOrEqual(1);
    expect(sprites.length).toBeGreaterThanOrEqual(1);
    expect(glyphs.length).toBeGreaterThanOrEqual(1);
  });

  it("disposes without throwing", () => {
    const group = buildCaeSetupOverlayGroup(makeOverlay(), makeBrepSnapshot(), makeBoxObject(), IDENTITY_TRANSFORM);
    expect(() => disposeCaeSetupOverlayGroup(group)).not.toThrow();
  });
});
