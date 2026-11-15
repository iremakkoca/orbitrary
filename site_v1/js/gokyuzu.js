/* Developed with assistance from Claude (Anthropic). */
// Ortak gokyuzu: NASA SVS Deep Star Maps 2020. Bilgisayarda 8K (varsa), telefonda ya da 8192 desteklenmiyorsa 4K.
// Ikisi de yoksa 6000 nokta yildiz.
import * as THREE from 'three';

// Gokyuzu parlakligi (doku rengiyle carpilir): 0.03 = cok kisik, 0.08 = belirgin
const GOK_PARLAKLIK = 0.05;

export function gokyuzuEkle(scene, renderer, yaricap = 150) {
  const yukleyici = new THREE.TextureLoader();
  const telefon = window.innerWidth < 800;
  // Ekran karti 8192 piksellik dokuyu destekliyor mu? (cogu destekler)
  const sekizK = !telefon && renderer.capabilities.maxTextureSize >= 8192;
  const dosyalar = sekizK ? ['textures/stars_8k.jpg', 'textures/stars.jpg'] : ['textures/stars.jpg'];
  let mat = null;

  function dene(i) {
    if (i >= dosyalar.length) { mat = yapayYildizlar(scene, renderer, yaricap * 0.9); return; }
    yukleyici.load(dosyalar[i], t => {
      t.colorSpace = THREE.SRGBColorSpace;
      t.wrapS = THREE.RepeatWrapping;
      t.repeat.x = -1;                                           // kureye iceriden bakinca aynalamayi duzelt
      t.anisotropy = renderer.capabilities.getMaxAnisotropy();   // egik bakista netlik
      const c = GOK_PARLAKLIK;
      scene.add(new THREE.Mesh(
        new THREE.SphereGeometry(yaricap, 96, 48),
        new THREE.MeshBasicMaterial({ map: t, color: new THREE.Color(c, c, c * 1.15),
                                      side: THREE.BackSide, depthWrite: false, toneMapped: false })
      ));
    }, undefined, () => dene(i + 1));                            // dosya yoksa siradakini dene
  }
  dene(0);

  return t => { if (mat) mat.uniforms.uZaman.value = t; };
}

// Hic doku bulunamazsa: 6000 nokta yildiz (yedek)
function yapayYildizlar(scene, renderer, R) {
  const N = 6000;
  const poz = new Float32Array(N * 3), boy = new Float32Array(N), faz = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const u = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, s = Math.sqrt(1 - u * u);
    poz.set([R * s * Math.cos(a), R * u, R * s * Math.sin(a)], i * 3);
    boy[i] = 0.6 + Math.pow(Math.random(), 6) * 2.4;
    faz[i] = Math.random() * Math.PI * 2;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(poz, 3));
  g.setAttribute('aBoy', new THREE.BufferAttribute(boy, 1));
  g.setAttribute('aFaz', new THREE.BufferAttribute(faz, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uZaman: { value: 0 }, uPiksel: { value: renderer.getPixelRatio() } },
    vertexShader: `
      attribute float aBoy; attribute float aFaz; uniform float uZaman; uniform float uPiksel;
      varying float vParlak;
      void main() {
        vParlak = 0.55 + 0.45 * sin(uZaman * 1.5 + aFaz);
        gl_PointSize = aBoy * uPiksel;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      varying float vParlak;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        gl_FragColor = vec4(vec3(0.85, 0.9, 1.0) * vParlak, 1.0 - d * 2.0);
      }`,
    transparent: true, depthWrite: false
  });
  scene.add(new THREE.Points(g, mat));
  return mat;
}
