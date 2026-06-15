import * as THREE from "three";

import type { BrepFaceEntity, BrepGraphSnapshot } from "../../appTypes";
import type { CaeSetupOverlayResponse } from "../../types";
import { modelToDisplayVec, type DisplayTransform } from "./coordinateFrames";
import { createFaceHighlightMesh, disposeHighlightObject } from "./highlights";

const LOAD_COLOR = 0xf59e0b; // amber
const CONSTRAINT_COLOR = 0x06b6d4; // cyan
const STALE_COLOR = 0xef4444; // red

function makeOverlayMaterial(color: number): THREE.MeshBasicMaterial {
  return new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.55,
    depthTest: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    polygonOffset: true,
    polygonOffsetFactor: -5,
    polygonOffsetUnits: -5,
  });
}

function createLabelSprite(text: string, color: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return new THREE.Sprite(new THREE.SpriteMaterial({ color: 0xffffff }));
  }
  const fontSize = 14;
  ctx.font = `bold ${fontSize}px system-ui, sans-serif`;
  const metrics = ctx.measureText(text);
  const padding = 8;
  canvas.width = Math.ceil(metrics.width + padding * 2);
  canvas.height = Math.ceil(fontSize * 1.4 + padding);
  ctx.font = `bold ${fontSize}px system-ui, sans-serif`;
  ctx.textBaseline = "middle";
  ctx.fillStyle = color;
  ctx.fillText(text, padding, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
    opacity: 0.92,
  });
  const sprite = new THREE.Sprite(material);
  const aspect = canvas.width / canvas.height;
  sprite.scale.set(0.25 * aspect, 0.25, 1);
  sprite.renderOrder = 1003;
  return sprite;
}

function faceCentroidInDisplay(face: BrepFaceEntity, transform: DisplayTransform): THREE.Vector3 {
  if (face.center && face.center.length === 3) {
    return modelToDisplayVec(face.center[0], face.center[1], face.center[2], transform);
  }
  const bbox = face.bounding_box;
  if (bbox && bbox.length === 6) {
    const a = modelToDisplayVec(bbox[0], bbox[1], bbox[2], transform);
    const b = modelToDisplayVec(bbox[3], bbox[4], bbox[5], transform);
    return new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
  }
  return new THREE.Vector3();
}

function sceneDiagonal(object: THREE.Object3D): number {
  const box = new THREE.Box3().setFromObject(object);
  if (box.isEmpty()) return 1;
  const size = new THREE.Vector3().subVectors(box.max, box.min);
  return Math.max(size.length(), 1e-3);
}

/**
 * Build the CAE setup overlay: amber arrows + labels on loaded faces, cyan glyphs
 * on constrained faces, and translucent tinted highlights on the bound faces.
 * Stale/unresolved faces are highlighted in red.
 */
export function buildCaeSetupOverlayGroup(
  overlay: CaeSetupOverlayResponse,
  brepSnapshot: BrepGraphSnapshot | null,
  object: THREE.Object3D,
  transform: DisplayTransform,
): THREE.Group {
  const group = new THREE.Group();
  group.name = "cae-setup-overlay";
  if (!overlay.available || !brepSnapshot) return group;

  const loadMaterial = makeOverlayMaterial(LOAD_COLOR);
  const constraintMaterial = makeOverlayMaterial(CONSTRAINT_COLOR);
  const staleMaterial = makeOverlayMaterial(STALE_COLOR);
  const diagonal = sceneDiagonal(object);
  const arrowLength = diagonal * 0.25;
  const arrowHead = arrowLength * 0.25;

  const addFaceHighlight = (faceId: string, material: THREE.MeshBasicMaterial, stale: boolean) => {
    const face = brepSnapshot.faces[faceId];
    if (!face) return;
    const mesh = createFaceHighlightMesh(object, face, transform);
    if (mesh) {
      mesh.material = stale ? staleMaterial : material;
      group.add(mesh);
    }
  };

  for (const load of overlay.loads) {
    const stale = load.face_ids.length === 0 || Boolean(overlay.warnings?.some((w) => load.face_ids.some((fid) => w.includes(fid))));
    for (const faceId of load.face_ids) {
      addFaceHighlight(faceId, loadMaterial, stale);
      const face = brepSnapshot.faces[faceId];
      if (!face) continue;
      const origin = faceCentroidInDisplay(face, transform);
      const dir = new THREE.Vector3(load.direction[0], load.direction[1], load.direction[2]);
      const displayDir = modelToDisplayVec(dir.x, dir.y, dir.z, transform).normalize();
      if (displayDir.lengthSq() === 0) displayDir.set(0, 0, -1);
      const arrow = new THREE.ArrowHelper(displayDir, origin, arrowLength, LOAD_COLOR, arrowHead, arrowHead * 0.6);
      arrow.renderOrder = 1002;
      group.add(arrow);
      const label = createLabelSprite(`${load.magnitude_n} N`, "#fbbf24");
      label.position.copy(origin).add(displayDir.clone().multiplyScalar(arrowLength * 0.6)).add(new THREE.Vector3(0, arrowLength * 0.15, 0));
      group.add(label);
    }
  }

  for (const constraint of overlay.constraints) {
    const stale = constraint.face_ids.length === 0 || Boolean(overlay.warnings?.some((w) => constraint.face_ids.some((fid) => w.includes(fid))));
    for (const faceId of constraint.face_ids) {
      addFaceHighlight(faceId, constraintMaterial, stale);
      const face = brepSnapshot.faces[faceId];
      if (!face) continue;
      const origin = faceCentroidInDisplay(face, transform);
      // Fixed-support glyph: a small cone.
      const glyph = new THREE.Mesh(
        new THREE.ConeGeometry(diagonal * 0.035, diagonal * 0.08, 16),
        new THREE.MeshBasicMaterial({ color: CONSTRAINT_COLOR, depthTest: false }),
      );
      glyph.position.copy(origin).add(new THREE.Vector3(0, diagonal * 0.04, 0));
      glyph.renderOrder = 1002;
      group.add(glyph);
    }
  }

  return group;
}

export function disposeCaeSetupOverlayGroup(group: THREE.Group): void {
  group.traverse((obj) => {
    if (obj instanceof THREE.Mesh) {
      disposeHighlightObject(obj);
    }
    if (obj instanceof THREE.Sprite) {
      const material = obj.material;
      if (material.map) material.map.dispose();
      material.dispose();
    }
    if (obj instanceof THREE.ArrowHelper) {
      // ArrowHelper children are Line and Mesh; their geometries/materials are
      // managed by the helper's dispose method.
      obj.dispose();
    }
  });
}
