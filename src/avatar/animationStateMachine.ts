// Self/src/avatar/animationStateMachine.ts
import * as THREE from "three";

export interface VitalityStateConfig {
  tier: number;
  name: string;
  clipCandidates: string[];   // Ordered priority list of GLTF animation names
  timeScale: number;          // Playback speed multiplier
  crossfadeDuration: number;  // Seconds for smooth skeletal blending
  spinePitchOffset: number;   // Procedural slouch (+) vs. proud chest (-) in radians
  headPitchOffset: number;    // Procedural head droop (+) vs. chin up (-) in radians
  hoverAmplitude: number;     // Y-axis levitation wave height (Tier 5 Sovereign Float)
  hoverBaseOffset: number;    // Base elevation off the floor
}

export const TEMPLE_VITALITY_STATES: Record<number, VitalityStateConfig> = {
  1: {
    tier: 1,
    name: "DEPLETED // FATIGUED",
    clipCandidates: ["Fatigued_Idle", "Exhausted", "Injured_Idle", "Sad_Idle", "Idle"],
    timeScale: 0.65,
    crossfadeDuration: 0.8,
    spinePitchOffset: 0.28,   // Noticeable forward slouch
    headPitchOffset: 0.22,    // Head tilted down
    hoverAmplitude: 0.0,
    hoverBaseOffset: 0.0,
  },
  2: {
    tier: 2,
    name: "RECOVERING // BASELINE",
    clipCandidates: ["Breathing_Idle", "Neutral_Idle", "Standard_Idle", "Idle"],
    timeScale: 0.85,
    crossfadeDuration: 0.6,
    spinePitchOffset: 0.1,    // Slight forward lean
    headPitchOffset: 0.08,
    hoverAmplitude: 0.0,
    hoverBaseOffset: 0.0,
  },
  3: {
    tier: 3,
    name: "CONDITIONED // ALIGNED",
    clipCandidates: ["Standard_Idle", "Alert_Idle", "Athletic_Idle", "Idle"],
    timeScale: 1.0,
    crossfadeDuration: 0.5,
    spinePitchOffset: 0.0,    // Neutral, aligned posture
    headPitchOffset: 0.0,
    hoverAmplitude: 0.0,
    hoverBaseOffset: 0.0,
  },
  4: {
    tier: 4,
    name: "PEAK KINETIC // COMBAT POISE",
    clipCandidates: ["Combat_Idle", "Ready_Idle", "Martial_Idle", "Fighter_Idle", "Idle"],
    timeScale: 1.18,
    crossfadeDuration: 0.4,
    spinePitchOffset: -0.06,  // Engaged chest & shoulders back
    headPitchOffset: -0.04,
    hoverAmplitude: 0.02,     // Subtle kinetic micro-bounce
    hoverBaseOffset: 0.0,
  },
  5: {
    tier: 5,
    name: "ASCENDANT // SOVEREIGN VITALITY",
    clipCandidates: ["Floating_Idle", "Hover_Idle", "Meditate_Float", "Power_Idle", "Idle"],
    timeScale: 0.9,           // Calm, controlled zero-G cadence
    crossfadeDuration: 0.7,
    spinePitchOffset: -0.12,  // Proud, open thoracic posture
    headPitchOffset: -0.06,
    hoverAmplitude: 0.12,     // Full magnetic levitation wave
    hoverBaseOffset: 0.18,    // Elevated above ground plane
  },
};

export const LEVEL_UP_BURST_CANDIDATES = [
  "Level_Up",
  "Power_Up",
  "Victory",
  "Roar",
  "Taunt",
  "Action",
];

/**
 * Resolves the best matching AnimationAction from the loaded GLTF dictionary
 */
export function resolveBestAction(
  actions: Record<string, THREE.AnimationAction | null>,
  candidates: string[]
): THREE.AnimationAction | null {
  const availableKeys = Object.keys(actions);
  if (availableKeys.length === 0) return null;

  for (const candidate of candidates) {
    const target = candidate.toLowerCase();
    const matchedKey = availableKeys.find((k) => k.toLowerCase().includes(target));
    if (matchedKey && actions[matchedKey]) {
      return actions[matchedKey];
    }
  }

  // Fallback to first available action or 'idle'
  const fallbackKey = availableKeys.find((k) => k.toLowerCase().includes("idle")) || availableKeys[0];
  return fallbackKey ? actions[fallbackKey] : null;
}
