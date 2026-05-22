/**
 * SceneManager — manages Three.js scene, camera, renderer, controls.
 *
 * Handles initialization, animation loop, lighting, and camera utilities.
 * NOTE: three.js must be installed (`npm install three @types/three`).
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CameraTween, type CameraState } from "./CameraTween";

export interface Viewpoint {
  position: { x: number; y: number; z: number };
  target: { x: number; y: number; z: number };
}

/** Canonical orientations driven by the View Cube (W6.6). */
export type ViewPreset =
  | "top"
  | "bottom"
  | "front"
  | "back"
  | "left"
  | "right"
  | "iso_ne"
  | "iso_nw"
  | "iso_se"
  | "iso_sw"
  | "fit";

export class SceneManager {
  readonly scene: THREE.Scene;
  readonly camera: THREE.PerspectiveCamera;
  readonly renderer: THREE.WebGLRenderer;
  readonly controls: OrbitControls;

  private animationId: number | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private container: HTMLElement;
  private gridHelper: THREE.GridHelper | null = null;
  /** On-demand rendering flag — drops idle CPU from 60 FPS to ~0%. */
  private _needsRender = true;
  /** Active camera tween (W6.6) — null when the camera is at rest. */
  private _tween: CameraTween | null = null;
  /** Reject the pending flyTo() promise when a new tween cancels it. */
  private _tweenReject: ((err: Error) => void) | null = null;
  /** controls.enabled value captured at tween start. Restored on cancel
   *  AND completion so a back-to-back cube click (which cancels the
   *  previous tween before it could restore controls) does not leave
   *  OrbitControls permanently disabled. */
  private _tweenWasControlsEnabled: boolean | null = null;
  /** Subscribers to camera-change events (used by the View Cube widget). */
  private _cameraChangeListeners = new Set<() => void>();
  /**
   * Last preset name + accumulated 90° rotation applied when the user
   * re-clicks the same View Cube face (Revit-style "snap-and-spin").
   */
  private _lastPreset: ViewPreset | null = null;
  private _lastPresetRotationSteps = 0;
  /** Listener refs kept so dispose() can remove them — without this,
   *  modifier-key handlers leaked on every viewer remount and the
   *  pointerup restore listener could fire AFTER dispose, leaving
   *  OrbitControls permanently disabled on the next model load. */
  private _onKeyDown: ((e: KeyboardEvent) => void) | null = null;
  private _onKeyUp: ((e: KeyboardEvent) => void) | null = null;
  private _onPointerDown: ((e: PointerEvent) => void) | null = null;
  private _canvasEl: HTMLCanvasElement | null = null;
  private _activeRestoreListeners = new Set<() => void>();

  constructor(canvas: HTMLCanvasElement) {
    const parent = canvas.parentElement;
    if (!parent)
      throw new Error("BIMViewer: canvas must have a parent element");
    this.container = parent;

    // Renderer
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      // Real IFC/RVT models carry many near-coplanar faces (multilayer
      // walls, slab finishes, IfcCovering over IfcWall, doubled
      // geometry from the converter). With a normal depth buffer and a
      // wide near/far range these faces get the same depth value and
      // the GPU flips which one wins every frame → "jumping"/flickering
      // triangles (z-fighting). A logarithmic depth buffer distributes
      // precision evenly across the whole range and removes the
      // artefact regardless of the model's unit/scale.
      logarithmicDepthBuffer: true,
    });
    // Pixel ratio capped at 1 — high-DPI rendering on a 5 000-mesh BIM
    // scene quadruples the per-frame fragment cost for marginal visual
    // gain on the engineering-readability use case. Users who want a
    // sharper picture can take a screenshot via the browser at any
    // zoom; the live viewport stays fluid.
    this.renderer.setPixelRatio(1);
    // Shadow map disabled — see DirectionalLight comment below.
    this.renderer.shadowMap.enabled = false;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.updateSize();

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf0f2f5);

    // No fog. RVT/COLLADA models can ship in millimetres / centimetres /
    // feet — a fixed-distance fog either swallows the geometry whole or
    // does nothing useful, depending on the model size. Easier to skip it
    // than to keep recomputing the range every time the model changes.

    // Camera — wide near/far so any unit fits without manual zoom.
    const aspect =
      this.container.clientWidth / Math.max(this.container.clientHeight, 1);
    this.camera = new THREE.PerspectiveCamera(45, aspect, 0.01, 1_000_000);
    this.camera.position.set(30, 20, 30);
    this.camera.lookAt(0, 0, 0);

    // Controls — smooth, professional orbit behaviour.
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08; // smoother deceleration (was 0.1)
    this.controls.rotateSpeed = 0.8; // slightly slower rotation for precision
    this.controls.panSpeed = 1.0;
    this.controls.zoomSpeed = 1.2;
    this.controls.minDistance = 0.01;
    this.controls.maxDistance = 100_000;
    // Prevent camera from flipping upside down — construction models
    // should always have "up" pointing up.
    this.controls.minPolarAngle = 0.05; // ~3° from top
    this.controls.maxPolarAngle = Math.PI - 0.05; // ~3° from bottom
    this.controls.target.set(0, 0, 0);
    // Remap mouse buttons so Ctrl+Left doesn't trigger pan (which would
    // steal clicks from SelectionManager's Ctrl+Click multi-select).
    // Left=ROTATE, Middle=DOLLY, Right=PAN.  Ctrl/Shift+Left is now free
    // for the selection system.
    this.controls.mouseButtons = {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN,
    };

    // Disable OrbitControls when Ctrl or Shift is held so that
    // Ctrl+Click and Shift+Click are free for multi-select in the
    // SelectionManager.  Re-enable on keyup.
    this._onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Control' || e.key === 'Shift') {
        this.controls.enabled = false;
      }
    };
    this._onKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Control' || e.key === 'Shift') {
        this.controls.enabled = true;
      }
    };
    window.addEventListener('keydown', this._onKeyDown);
    window.addEventListener('keyup', this._onKeyUp);
    // Also handle the case where modifier was held during pointerdown
    // on the canvas — OrbitControls checks enabled on pointer events.
    this._canvasEl = canvas;
    this._onPointerDown = (e: PointerEvent) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey) {
        this.controls.enabled = false;
        // Re-enable on next pointerup. The restore is tracked in a Set
        // so dispose() can drop it — otherwise a navigate-away mid-click
        // leaves OrbitControls disabled for the next model load.
        const restore = () => {
          this.controls.enabled = true;
          window.removeEventListener('pointerup', restore);
          this._activeRestoreListeners.delete(restore);
        };
        this._activeRestoreListeners.add(restore);
        window.addEventListener('pointerup', restore);
      }
    };
    canvas.addEventListener('pointerdown', this._onPointerDown, { capture: true });