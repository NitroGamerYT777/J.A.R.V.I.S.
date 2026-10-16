import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const params = new URLSearchParams(location.search);
const capture = params.has('capture');
if (capture) document.body.classList.add('capture');
const scene = new THREE.Scene();
scene.background = new THREE.Color('#060c12');
const camera = new THREE.PerspectiveCamera(35, innerWidth / innerHeight, .05, 100);
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.8));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.querySelector('#scene').append(renderer.domElement);
const pmrem = new THREE.PMREMGenerator(renderer);
const room = new RoomEnvironment();
const environment = pmrem.fromScene(room, .04);
scene.environment = environment.texture;
scene.environmentIntensity = .55;
room.dispose();
pmrem.dispose();
scene.add(new THREE.HemisphereLight(0xb5e8ff, 0x101923, .55));
const key = new THREE.DirectionalLight(0xe1efff, 2.2);
key.position.set(-4, 5, 5); scene.add(key);
const rim = new THREE.DirectionalLight(0x4d9dcc, 1.4);
rim.position.set(5, 1, -4); scene.add(rim);
const coreLight = new THREE.PointLight(0x24cbe8, 2.2, 4, 2);
coreLight.position.set(0, .1, 1.35); scene.add(coreLight);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = .09;
controls.minDistance = 4.8; controls.maxDistance = 13;
controls.enablePan = false;
const views = { front: [0, .08, 8.1], angle: [3.1, 1.1, 7.8], side: [8.4, .15, .15], back: [0, .1, -8.2] };
function setView(name) {
  camera.position.fromArray(views[name] || views.angle);
  controls.target.set(0, 0, 0); controls.update();
}
setView(params.get('view') || 'angle');
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), .52, .48, .75);
composer.addPass(bloom);
composer.addPass(new OutputPass());

let root, outer, inner, core;
let state = params.get('state') || 'idle';
let paused = false, animationTime = 0, spinTime = 0, easedSpeed = 1;
const emissive = new Map();
const clock = new THREE.Clock();
const loader = document.querySelector('#loader');
window.jarvisPreview = { ready: false, error: null };

function pose(t, integratedSpin = null) {
  if (!root) return;
  const speed = { idle: 1, listening: 1.15, thinking: 3.8, speaking: 1.7 }[state];
  const spin = integratedSpin ?? t * speed;
  const pulse = state === 'listening' ? .5 + .5 * Math.sin(t * 4.5)
    : state === 'speaking' ? .45 + .28 * Math.sin(t * 13) + .2 * Math.sin(t * 21)
    : state === 'thinking' ? .5 + .4 * Math.sin(t * 7) : .5 + .5 * Math.sin(t * 1.8);
  outer.rotation.set(.055 * Math.sin(t * .23), .055 * Math.sin(t * .19), spin * .055);
  inner.rotation.set(.15 * Math.sin(t * .31), .26 * Math.sin(t * .33), -spin * .07);
  core.rotation.y = spin * .11;
  core.rotation.z = .035 * Math.sin(t * .24);
  core.scale.setScalar(1 + (state === 'idle' ? .004 : .015) * pulse);
  for (const [material, base] of emissive) {
    material.emissiveIntensity = base * (state === 'idle' ? .88 + pulse * .14 : .9 + pulse * .65);
  }
  coreLight.intensity = 1.8 + pulse * (state === 'idle' ? .3 : 1.5);
  bloom.strength = state === 'speaking' ? .60 : .48;
}

function setState(next) {
  if (!['idle', 'listening', 'thinking', 'speaking'].includes(next)) return;
  state = next;
  document.querySelectorAll('[data-state]').forEach(b => b.classList.toggle('active', b.dataset.state === state));
}

const modelFile = params.get('model') === 'animated' ? 'jarvis-core-animated.glb' : 'jarvis-core.glb';
new GLTFLoader().load(`./${modelFile}`, gltf => {
  root = gltf.scene; scene.add(root);
  outer = root.getObjectByName('OuterRing');
  inner = root.getObjectByName('InnerRing');
  core = root.getObjectByName('Core');
  let triangles = 0, meshes = 0;
  const allMaterials = new Set();
  root.traverse(object => {
    if (!object.isMesh) return;
    meshes++;
    triangles += (object.geometry.index?.count || object.geometry.attributes.position.count) / 3;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.forEach(material => {
      allMaterials.add(material);
      if (material.emissive && material.emissive.getHex() !== 0) emissive.set(material, material.emissiveIntensity);
    });
  });
  document.querySelector('#triangles').textContent = `${(triangles / 1000).toFixed(1)}k TRI`;
  loader.remove();
  Object.assign(window.jarvisPreview, {
    ready: true, root, stats: { triangles, meshes, materials: allMaterials.size, emissiveMaterials: emissive.size, animations: gltf.animations.map(a => a.name) }, setState, setView,
    renderAt(t = 0) { pose(t); controls.update(); composer.render(); },
  });
  pose(0); composer.render();
  setState(state);
}, undefined, error => {
  window.jarvisPreview.error = String(error);
  loader.textContent = 'Modelni yuklab bo‘lmadi. Preview server orqali ochilganini tekshiring.';
  console.error(error);
});

document.querySelectorAll('[data-state]').forEach(button => button.addEventListener('click', () => setState(button.dataset.state)));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
document.querySelector('#pause').addEventListener('click', event => {
  paused = !paused;
  event.target.textContent = paused ? 'Davom ettirish' : 'Aylanishni to‘xtat';
});
let wireframe = false;
document.querySelector('#wireframe').addEventListener('click', event => {
  wireframe = !wireframe;
  root?.traverse(object => {
    if (object.isMesh) {
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) material.wireframe = wireframe;
    }
  });
  event.target.classList.toggle('active', wireframe);
});
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight); composer.setSize(innerWidth, innerHeight);
});
function frame() {
  requestAnimationFrame(frame);
  const delta = Math.min(clock.getDelta(), .1);
  if (!root) return;
  if (!capture) {
    if (!paused) {
      animationTime += delta;
      const target = { idle: 1, listening: 1.15, thinking: 3.8, speaking: 1.7 }[state];
      easedSpeed += (target - easedSpeed) * Math.min(1, delta * 3);
      spinTime += delta * easedSpeed;
    }
    pose(animationTime, spinTime);
  }
  controls.update(); composer.render();
}
frame();
