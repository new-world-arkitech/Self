// Self/src/avatar/RiggedAvatarEntity.tsx
import React, { useEffect, useMemo, useRef } from "react";
import { createPortal, useFrame, useGraph } from "@react-three/fiber";
import { useGLTF, useAnimations, Sparkles } from "@react-three/drei";
import * as THREE from "three";
import { SkeletonUtils } from "three-stdlib";
import { createSkinnedCreditShaderMaterial } from "./shaders/creditShader";
import {
  TEMPLE_VITALITY_STATES,
  LEVEL_UP_BURST_CANDIDATES,
  resolveBestAction,
} from "./animationStateMachine";

export interface ParsedTiers {
  career: number;
  credit: number;
  knowledge: number;
  temple: number;
}

interface RiggedAvatarProps {
  modelUrl?: string;
  tiers: ParsedTiers;
  onVitalityStateChange?: (stateName: string) => void;
}

function findBone(nodes: Record<string, THREE.Object3D>, patterns: string[]): THREE.Bone | null {
  for (const key of Object.keys(nodes)) {
    const obj = nodes[key];
    if ((obj as THREE.Bone).isBone) {
      const lower = key.toLowerCase();
      if (patterns.some((p) => lower.includes(p))) {
        return obj as THREE.Bone;
      }
    }
  }
  return null;
}

export const RiggedAvatarEntity: React.FC<RiggedAvatarProps> = ({
  modelUrl = "/models/self_avatar.glb",
  tiers,
  onVitalityStateChange,
}) => {
  const groupRef = useRef<THREE.Group>(null);
  const neuralCrownRef = useRef<THREE.Group>(null);

  const activeActionRef = useRef<THREE.AnimationAction | null>(null);
  const prevTotalTiersRef = useRef<number>(
    tiers.career + tiers.credit + tiers.knowledge + tiers.temple
  );

  const currentPostureRef = useRef({
    spinePitch: 0,
    headPitch: 0,
    hoverY: -1.1,
  });

  // 1. Load GLTF, clone skeleton, and bind animations
  const { scene, animations } = useGLTF(modelUrl);
  const clonedScene = useMemo(() => SkeletonUtils.clone(scene), [scene]);
  const { nodes } = useGraph(clonedScene);
  const { actions, mixer } = useAnimations(animations, groupRef);

  // 2. Instantiate skinning-enabled Credit & Temple GLSL shader
  const skinnedShader = useMemo(() => createSkinnedCreditShaderMaterial(), []);

  // 3. Locate target humanoid bones for attachments & posture manipulation
  const rigBones = useMemo(() => {
    return {
      head: findBone(nodes, ["head"]),
      neck: findBone(nodes, ["neck"]),
      spine: findBone(nodes, ["spine2", "chest", "upperchest", "spine1", "spine"]),
      leftShoulder: findBone(nodes, ["leftarm", "leftshoulder", "l_upperarm"]),
      rightShoulder: findBone(nodes, ["rightarm", "rightshoulder", "r_upperarm"]),
    };
  }, [nodes]);

  // 4. Bind custom shader and toggle named career sub-meshes
  useEffect(() => {
    clonedScene.traverse((child) => {
      if ((child as THREE.SkinnedMesh).isSkinnedMesh || (child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.material = skinnedShader;
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        const tierMatch = mesh.name.match(/Armor_Tier(\d+)/i);
        if (tierMatch) {
          const requiredTier = parseInt(tierMatch[1], 10);
          mesh.visible = tiers.career >= requiredTier;
        }
      }
    });
  }, [clonedScene, skinnedShader, tiers.career]);

  // 5. ANIMATION STATE MACHINE: Crossfade idle states when Self.temple changes
  useEffect(() => {
    const vitalityCfg = TEMPLE_VITALITY_STATES[tiers.temple] || TEMPLE_VITALITY_STATES[1];
    onVitalityStateChange?.(vitalityCfg.name);

    const targetAction = resolveBestAction(actions, vitalityCfg.clipCandidates);
    if (!targetAction) return;

    const prevAction = activeActionRef.current;

    targetAction.setLoop(THREE.LoopRepeat, Infinity);
    targetAction.clampWhenFinished = false;
    targetAction.setEffectiveTimeScale(vitalityCfg.timeScale);

    if (prevAction && prevAction !== targetAction) {
      targetAction.reset().play();
      prevAction.crossFadeTo(targetAction, vitalityCfg.crossfadeDuration, true);
    } else if (!prevAction) {
      targetAction.reset().fadeIn(vitalityCfg.crossfadeDuration).play();
    }

    activeActionRef.current = targetAction;
  }, [actions, tiers.temple, onVitalityStateChange]);

  // 6. ONE-SHOT ACTION SURGE: Trigger power-up clip when any domain levels up
  useEffect(() => {
    const currentTotal = tiers.career + tiers.credit + tiers.knowledge + tiers.temple;
    const leveledUp = currentTotal > prevTotalTiersRef.current;
    prevTotalTiersRef.current = currentTotal;

    if (!leveledUp) return;

    const burstAction = resolveBestAction(actions, LEVEL_UP_BURST_CANDIDATES);
    const baseIdleAction = activeActionRef.current;

    if (burstAction && burstAction !== baseIdleAction && baseIdleAction) {
      burstAction.reset();
      burstAction.setLoop(THREE.LoopOnce, 1);
      burstAction.clampWhenFinished = true;
      burstAction.setEffectiveTimeScale(1.15);
      burstAction.play();

      baseIdleAction.crossFadeTo(burstAction, 0.25, false);

      const handleFinished = (e: any) => {
        if (e.action === burstAction) {
          mixer.removeEventListener("finished", handleFinished);
          baseIdleAction.reset().play();
          burstAction.crossFadeTo(baseIdleAction, 0.45, false);
        }
      };

      mixer.addEventListener("finished", handleFinished);
      return () => mixer.removeEventListener("finished", handleFinished);
    }
  }, [tiers.career, tiers.credit, tiers.knowledge, tiers.temple, actions, mixer]);

  // 7. Per-frame updates: Shader uniforms + Procedural Spine/Head Posture & Levitation
  useFrame(({ clock }, delta) => {
    const t = clock.getElapsedTime();
    const vitalityCfg = TEMPLE_VITALITY_STATES[tiers.temple] || TEMPLE_VITALITY_STATES[1];

    skinnedShader.uniforms.uTime.value = t;
    skinnedShader.uniforms.uCreditTier.value = tiers.credit;
    skinnedShader.uniforms.uTempleTier.value = tiers.temple;
    skinnedShader.uniforms.uVitalityTier.value = tiers.temple;

    const dampSpeed = 4.0 * delta;
    currentPostureRef.current.spinePitch = THREE.MathUtils.lerp(
      currentPostureRef.current.spinePitch,
      vitalityCfg.spinePitchOffset,
      dampSpeed
    );
    currentPostureRef.current.headPitch = THREE.MathUtils.lerp(
      currentPostureRef.current.headPitch,
      vitalityCfg.headPitchOffset,
      dampSpeed
    );

    if (rigBones.spine) {
      const breathWave = Math.sin(t * (1.2 + tiers.temple * 0.35)) * 0.025;
      rigBones.spine.rotation.x += currentPostureRef.current.spinePitch + breathWave;
    }
    if (rigBones.head) {
      rigBones.head.rotation.x += currentPostureRef.current.headPitch;
    }

    if (groupRef.current) {
      const targetY =
        -1.1 +
        vitalityCfg.hoverBaseOffset +
        Math.sin(t * 2.0) * vitalityCfg.hoverAmplitude;
      groupRef.current.position.y = THREE.MathUtils.lerp(
        groupRef.current.position.y,
        targetY,
        dampSpeed
      );
    }

    if (neuralCrownRef.current) {
      neuralCrownRef.current.rotation.y = -t * (0.5 + tiers.knowledge * 0.2);
    }
  });

  const accentColor = tiers.credit >= 5 ? "#eab308" : "#00f0ff";

  return (
    <group ref={groupRef} position={[0, -1.1, 0]} dispose={null}>
      <primitive object={clonedScene} />

      {/* SELF.KNOWLEDGE: Bone-Attached Neural Halo & Glyphs (Head Bone) */}
      {rigBones.head &&
        createPortal(
          <group ref={neuralCrownRef} position={[0, 0.18, 0]}>
            {Array.from({ length: tiers.knowledge }).map((_, idx) => (
              <mesh
                key={`head-ring-${idx}`}
                rotation={[Math.PI / 2 + idx * 0.2, idx * 0.35, 0]}
              >
                <torusGeometry args={[0.28 + idx * 0.08, 0.006, 16, 64]} />
                <meshBasicMaterial color={accentColor} transparent opacity={0.8} />
              </mesh>
            ))}

            {Array.from({ length: tiers.knowledge * 2 }).map((_, idx) => {
              const angle = (idx / (tiers.knowledge * 2)) * Math.PI * 2;
              const r = 0.38;
              return (
                <mesh
                  key={`head-glyph-${idx}`}
                  position={[Math.cos(angle) * r, 0.05, Math.sin(angle) * r]}
                >
                  <octahedronGeometry args={[0.025, 0]} />
                  <meshStandardMaterial
                    color={accentColor}
                    emissive={accentColor}
                    emissiveIntensity={2}
                  />
                </mesh>
              );
            })}
          </group>,
          rigBones.head
        )}

      {/* SELF.CAREER: Bone-Attached Reactor Core & Pauldrons */}
      {rigBones.spine &&
        tiers.career >= 2 &&
        createPortal(
          <group position={[0, 0.12, 0.16]}>
            <mesh material={skinnedShader}>
              <octahedronGeometry args={[0.06 + tiers.career * 0.015, 0]} />
            </mesh>
          </group>,
          rigBones.spine
        )}

      {rigBones.leftShoulder &&
        tiers.career >= 2 &&
        createPortal(
          <group position={[0.08, 0.05, 0]} rotation={[0, 0, -0.3]}>
            <mesh material={skinnedShader}>
              <boxGeometry
                args={[
                  0.12 + tiers.career * 0.02,
                  0.22 + tiers.career * 0.04,
                  0.18 + tiers.career * 0.02,
                ]}
              />
            </mesh>
          </group>,
          rigBones.leftShoulder
        )}

      {rigBones.rightShoulder &&
        tiers.career >= 2 &&
        createPortal(
          <group position={[-0.08, 0.05, 0]} rotation={[0, 0, 0.3]}>
            <mesh material={skinnedShader}>
              <boxGeometry
                args={[
                  0.12 + tiers.career * 0.02,
                  0.22 + tiers.career * 0.04,
                  0.18 + tiers.career * 0.02,
                ]}
              />
            </mesh>
          </group>,
          rigBones.rightShoulder
        )}

      {/* SELF.CREDIT: Ambient Sovereign Aura & Particle Field */}
      <Sparkles
        position={[0, 1.1, 0]}
        count={tiers.credit * 40}
        scale={[2.2, 2.6, 2.2]}
        size={1.2 + tiers.credit * 0.35}
        speed={0.25 + tiers.temple * 0.15}
        color={accentColor}
      />
    </group>
  );
};
