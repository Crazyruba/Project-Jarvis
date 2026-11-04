// Subtle "alive" motion for the hologram head: slow breathing float and a lazy turn.
import type { Scene } from "@babylonjs/core/scene";
import type { Observer } from "@babylonjs/core/Misc/observable";
import type { TransformNode } from "@babylonjs/core/Meshes/transformNode";

export interface IdleMotionOptions {
  /** Float height in the node's local units. */
  floatAmplitude?: number;
  /** Seconds per breath. */
  breathPeriod?: number;
  /** Maximum turn either side, in radians. */
  turnAmplitude?: number;
  /** Seconds for one full left-right-left turn. */
  turnPeriod?: number;
}

/**
 * Animates `node` relative to its rest pose on every frame. Returns a function that stops the
 * motion and puts the node back. Other code can still rotate the node's parent freely.
 */
export function attachIdleMotion(scene: Scene, node: TransformNode, opts: IdleMotionOptions = {}): () => void {
  const floatAmp = opts.floatAmplitude ?? 0.1;
  const breath = (2 * Math.PI) / (opts.breathPeriod ?? 5.5);
  const turnAmp = opts.turnAmplitude ?? 0.12;
  const turn = (2 * Math.PI) / (opts.turnPeriod ?? 24);
  const restY = node.position.y;
  const restYaw = node.rotation.y;
  let t = 0;

  const observer: Observer<Scene> = scene.onBeforeRenderObservable.add(() => {
    t += Math.min(scene.getEngine().getDeltaTime() / 1000, 0.05);
    // Breathing: a sine with a softer top, so it rises slowly and settles gently.
    const b = Math.sin(t * breath);
    node.position.y = restY + floatAmp * (b + 0.15 * Math.sin(t * breath * 2));
    node.rotation.y = restYaw + turnAmp * Math.sin(t * turn);
  });

  return () => {
    scene.onBeforeRenderObservable.remove(observer);
    node.position.y = restY;
    node.rotation.y = restYaw;
  };
}
