// Self/src/avatar/AvatarCanvas.tsx
import React, { useMemo, useRef, Suspense } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Float, Stars, Sparkles } from "@react-three/drei";
import * as THREE from "three";
import { createCreditShaderMaterial } from "./shaders/creditShader";
import { RiggedAvatarEntity, ParsedTiers } from "./RiggedAvatarEntity";

export interface StateMatrix {
  app: string;
  last_synced: string;
  avatar_composite: {
    overall_level: number;
    total_xp: number;
    visual_layers: {
      armor_and_gear: string;           // Self.career    (tier_1 .. tier_5)
      material_shader_and_aura: string; // Self.credit    (tier_1 .. tier_5)
      neural_hud_and_glyphs: string;    // Self.knowledge (tier_1 .. tier_5)
      base_mesh_and_vitality: string;   // Self.temple    (tier_1 .. tier_5)
    };
  };
}

export function parseTierNumber(tierStr?: string): number {
  if (!tierStr) return 1;
  const match = tierStr.match(/tier_(\d+)/i);
  return match ? Math.min(5, Math.max(1, parseInt(match[1], 10))) : 1;
}

/**
 * Procedural Geometric Avatar fallback when no external .glb model is mounted.
 */
export const ProceduralAvatarEntity: React.FC<{ tiers: ParsedTiers }> = ({ tiers }) => {
  const coreGroupRef = useRef<THREE.Group>(null);
  const neuralRingRef = useRef<THREE.Group>(null);
  const armorGroupRef = useRef<THREE.Group>(null);

  const shaderMaterial = useMemo(() => createCreditShaderMaterial(), []);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    shaderMaterial.uniforms.uTime.value = t;
    shaderMaterial.uniforms.uCreditTier.value = tiers.credit;
    shaderMaterial.uniforms.uTempleTier.value = tiers.temple;
    shaderMaterial.uniforms.uVitalityTier.value = tiers.temple;

    if (coreGroupRef.current) {
      coreGroupRef.current.rotation.y = t * 0.25;
    }

    if (neuralRingRef.current) {
      neuralRingRef.current.rotation.y = -t * (0.4 + tiers.knowledge * 0.15);
      neuralRingRef.current.rotation.z = Math.sin(t * 0.5) * 0.2;
    }

    if (armorGroupRef.current) {
      armorGroupRef.current.rotation.y = t * 0.18;
      armorGroupRef.current.position.y = Math.sin(t * 1.5) * 0.05;
    }
  });

  const glyphCount = tiers.knowledge * 3;
  const glyphs = useMemo(() => {
    return Array.from({ length: glyphCount }, (_, i) => {
      const angle = (i / glyphCount) * Math.PI * 2;
      const radius = 1.65 + (i % 2) * 0.25;
      return {
        position: [
          Math.cos(angle) * radius,
          0.9 + Math.sin(angle * 2) * 0.25,
          Math.sin(angle) * radius,
        ] as [number, number, number],
        rotation: [0, -angle, 0] as [number, number, number],
      };
    });
  }, [glyphCount]);

  const armorPlateCount = tiers.career * 2;
  const armorPlates = useMemo(() => {
    return Array.from({ length: armorPlateCount }, (_, i) => {
      const angle = (i / armorPlateCount) * Math.PI * 2;
      const radius = 1.25;
      return {
        position: [
          Math.cos(angle) * radius,
          (i % 2 === 0 ? 0.25 : -0.35),
          Math.sin(angle) * radius,
        ] as [number, number, number],
        rotation: [0.2, -angle, 0] as [number, number, number],
      };
    });
  }, [armorPlateCount]);

  const accentColor = tiers.credit >= 5 ? "#eab308" : "#00f0ff";

  return (
    <group position={[0, -0.2, 0]}>
      {/* 1. Core Vitality Geometry (Temple) */}
      <group ref={coreGroupRef}>
        <mesh material={shaderMaterial}>
          <icosahedronGeometry args={[0.75, Math.min(4, tiers.temple)]} />
        </mesh>
        <mesh>
          <sphereGeometry args={[0.3, 16, 16]} />
          <meshBasicMaterial color={accentColor} wireframe />
        </mesh>
      </group>

      {/* 2. Neural Glyph Orbital Field (Knowledge) */}
      <group ref={neuralRingRef}>
        {glyphs.map((g, i) => (
          <mesh key={`glyph-${i}`} position={g.position} rotation={g.rotation}>
            <octahedronGeometry args={[0.07, 0]} />
            <meshStandardMaterial
              color={accentColor}
              emissive={accentColor}
              emissiveIntensity={1.8}
            />
          </mesh>
        ))}
      </group>

      {/* 3. Kinetic Armor Plates (Career) */}
      <group ref={armorGroupRef}>
        {armorPlates.map((p, i) => (
          <mesh key={`plate-${i}`} position={p.position} rotation={p.rotation} material={shaderMaterial}>
            <boxGeometry args={[0.18, 0.45, 0.05]} />
          </mesh>
        ))}
      </group>

      {/* 4. Sovereign Radiance Sparkles (Credit) */}
      <Sparkles
        count={tiers.credit * 35}
        scale={[3, 3, 3]}
        size={1.5 + tiers.credit * 0.4}
        speed={0.3 + tiers.temple * 0.15}
        color={accentColor}
      />
    </group>
  );
};

interface AvatarCanvasProps {
  stateMatrix?: StateMatrix;
  customTiers?: ParsedTiers;
  modelUrl?: string;
  useRiggedModel?: boolean;
}

export const AvatarCanvas: React.FC<AvatarCanvasProps> = ({
  stateMatrix,
  customTiers,
  modelUrl = "/models/self_avatar.glb",
  useRiggedModel = false,
}) => {
  const tiers: ParsedTiers = useMemo(() => {
    if (customTiers) return customTiers;
    const layers = stateMatrix?.avatar_composite?.visual_layers;
    return {
      career: parseTierNumber(layers?.armor_and_gear),
      credit: parseTierNumber(layers?.material_shader_and_aura),
      knowledge: parseTierNumber(layers?.neural_hud_and_glyphs),
      temple: parseTierNumber(layers?.base_mesh_and_vitality),
    };
  }, [stateMatrix, customTiers]);

  return (
    <div style={{ width: "100%", height: "100%", background: "#050508", position: "relative" }}>
      <Canvas
        camera={{ position: [0, 0.5, 3.8], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.4} />
        <directionalLight position={[5, 8, 5]} intensity={1.2} />
        <pointLight position={[-5, -2, -3]} color="#00f0ff" intensity={1.5} />
        <pointLight position={[0, 4, 2]} color={tiers.credit >= 4 ? "#eab308" : "#6366f1"} intensity={2.0} />

        <Stars radius={60} depth={30} count={1500} factor={3} saturation={0} fade speed={1} />

        <Float speed={1.2} rotationIntensity={0.3} floatIntensity={0.4}>
          <Suspense fallback={null}>
            {useRiggedModel ? (
              <RiggedAvatarEntity modelUrl={modelUrl} tiers={tiers} />
            ) : (
              <ProceduralAvatarEntity tiers={tiers} />
            )}
          </Suspense>
        </Float>

        <OrbitControls
          enablePan={false}
          minDistance={1.8}
          maxDistance={6.0}
          maxPolarAngle={Math.PI / 1.7}
        />
      </Canvas>
    </div>
  );
};

export default AvatarCanvas;
