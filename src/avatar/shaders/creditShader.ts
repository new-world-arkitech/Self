// Self/src/avatar/shaders/creditShader.ts
import * as THREE from "three";

export const CreditVertexShader = /* glsl */ `
  #include <common>
  #include <skinning_pars_vertex>

  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec2 vUv;

  uniform float uTime;
  uniform float uVitalityTier;

  void main() {
    vUv = uv;

    // 1. Initialize base object-space normal and vertex position
    vec3 objectNormal = normal;
    vec3 transformed = position;

    // 2. Apply Self.temple vitality breathing displacement along the surface normal
    float pulse = sin(uTime * (1.2 + uVitalityTier * 0.4) + position.y * 4.0) * 0.006 * uVitalityTier;
    transformed += objectNormal * pulse;

    // 3. Apply skeletal bone matrices (Hardware Skinning)
    #include <skinbase_vertex>
    #include <skinnormal_vertex>
    #include <skinning_vertex>

    // 4. Compute view-space position and normal for the Credit Fresnel shader
    vNormal = normalize(normalMatrix * objectNormal);
    vec4 mvPosition = modelViewMatrix * vec4(transformed, 1.0);
    vPosition = mvPosition.xyz;

    gl_Position = projectionMatrix * mvPosition;
  }
`;

export const CreditFragmentShader = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec2 vUv;

  uniform float uTime;
  uniform float uCreditTier;
  uniform float uTempleTier;
  uniform float uVitalityTier;

  void main() {
    // 1. Compute view-angle Fresnel factor
    vec3 viewDir = normalize(-vPosition);
    float fresnel = pow(1.0 - max(dot(viewDir, normalize(vNormal)), 0.0), 3.0);

    // 2. Dynamic color selection based on Credit & Prosperity tier
    vec3 tierColor = vec3(0.0, 0.94, 1.0); // Cyan base
    if (uCreditTier >= 5.0) {
      tierColor = vec3(0.92, 0.70, 0.03); // Sovereign Gold
    } else if (uCreditTier >= 4.0) {
      tierColor = vec3(0.95, 0.45, 0.15); // Kinetic Amber
    } else if (uCreditTier >= 3.0) {
      tierColor = vec3(0.25, 0.55, 1.0); // Electric Azure
    } else if (uCreditTier >= 2.0) {
      tierColor = vec3(0.0, 0.85, 0.75); // Emerald Aqua
    } else {
      tierColor = vec3(0.35, 0.42, 0.50); // Hardened Slate
    }

    // 3. Oscillating energy pulse driven by Temple vitality
    float pulse = 0.5 + 0.5 * sin(uTime * 2.0 + vPosition.y * 3.0);
    vec3 aura = tierColor * (fresnel * (0.8 + 0.4 * pulse * uVitalityTier));
    vec3 baseColor = vec3(0.04, 0.05, 0.08);

    gl_FragColor = vec4(baseColor + aura, clamp(0.35 + fresnel * 0.65, 0.0, 1.0));
  }
`;

/**
 * Standard unskinned shader for procedural meshes and geometric avatars
 */
export function createCreditShaderMaterial() {
  return new THREE.ShaderMaterial({
    vertexShader: CreditVertexShader,
    fragmentShader: CreditFragmentShader,
    transparent: true,
    uniforms: {
      uTime: { value: 0 },
      uCreditTier: { value: 1 },
      uTempleTier: { value: 1 },
      uVitalityTier: { value: 1 },
    },
  });
}

/**
 * Skinned shader for rigged humanoid GLTF/GLB models with skeletal bones
 */
export function createSkinnedCreditShaderMaterial() {
  const mat = new THREE.ShaderMaterial({
    vertexShader: CreditVertexShader,
    fragmentShader: CreditFragmentShader,
    transparent: true,
    uniforms: {
      uTime: { value: 0 },
      uCreditTier: { value: 1 },
      uTempleTier: { value: 1 },
      uVitalityTier: { value: 1 },
    },
  });

  // Enable skinning flag for Three.js WebGLProgram
  (mat as any).skinning = true;
  return mat;
}
