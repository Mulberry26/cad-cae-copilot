import { useEffect } from "react";
import * as THREE from "three";

import type { BrepGraphSnapshot } from "../../../appTypes";
import type { CaeSetupOverlayResponse } from "../../../types";
import { type DisplayTransform } from "../coordinateFrames";
import { buildCaeSetupOverlayGroup, disposeCaeSetupOverlayGroup } from "../caeSetupOverlay";

/**
 * Manage the CAE setup overlay group in the scene. Rebuilds arrows, glyphs, and
 * bound-face highlights whenever the toggle, setup data, model, or transform
 * changes.
 */
export function useCaeSetupOverlay(
  groupRef: React.RefObject<THREE.Group | null>,
  show: boolean,
  overlay: CaeSetupOverlayResponse | null,
  brepSnapshot: BrepGraphSnapshot | null,
  objectRef: React.RefObject<THREE.Object3D | null>,
  displayTransformRef: React.MutableRefObject<DisplayTransform>,
  objectReadyKey: number,
) {
  useEffect(() => {
    const group = groupRef.current;
    const object = objectRef.current;
    if (!group) return;

    // Clear previous overlay.
    while (group.children.length > 0) {
      const child = group.children.pop()!;
      group.remove(child);
      if (child instanceof THREE.Group) disposeCaeSetupOverlayGroup(child);
    }

    if (!show || !overlay || !overlay.available || !object || !brepSnapshot) return;

    const nextGroup = buildCaeSetupOverlayGroup(
      overlay,
      brepSnapshot,
      object,
      displayTransformRef.current,
    );
    group.add(nextGroup);

    return () => {
      while (group.children.length > 0) {
        const child = group.children.pop()!;
        group.remove(child);
        if (child instanceof THREE.Group) disposeCaeSetupOverlayGroup(child);
      }
    };
  }, [show, overlay, brepSnapshot, objectReadyKey, groupRef, objectRef, displayTransformRef]);
}
