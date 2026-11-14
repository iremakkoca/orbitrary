/* Developed with assistance from Claude (Anthropic). */
// =====================================================================
// ORBITRARY — ORTAK GÖKYÜZÜ (ana sayfa ve keşif modu birlikte kullanır)
//
// NASA Deep Star Maps 2020, Samanyolu dahil gerçek gökyüzü, kısık parlaklıkta.
//   Bilgisayarda : textures/stars_8k.jpg (8192×4096) → ekranda yıldızlar net
//   Telefonda    : textures/stars.jpg   (4096×2048) → bellek dostu
// 8K dosya yoksa 4K'ya, o da yoksa rastgele nokta yıldızlara düşer.
// =====================================================================
import * as THREE from 'three';

// Gökyüzü parlaklığı (doku rengiyle çarpılır): 0.03 = çok kısık, 0.08 = belirgin
const GOK_PARLAKLIK = 0.05;

export function gokyuzuEkle(scene, renderer, yaricap = 150) {
  const yukleyici = new THREE.TextureLoader();
  const telefon = window.innerWidth < 800;
  // Ekran kartı 8192 piksellik dokuyu destekliyor mu? (çoğu destekler)
  const sekizK = !telefon && renderer.capabilities.maxTextureSize >= 8192;
  const dosyalar = sekizK ? ['textures/stars_8k.jpg', 'textures/stars.jpg'] : ['textures/stars.jpg'];
  let mat = null;

  function dene(i) {
    if (i >= dosyalar.length) { mat = yapayYildizlar(scene, renderer, yaricap * 0.9); return; }
    yukleyici.load(dosyalar[i], t => {
      t.colorSpace = THREE.SRGBColorSpace;
      t.wrapS = THREE.RepeatWrapping;
      t.repeat.x = -1;                                           // küreye içeriden bakınca aynalamayı düzelt
      t.anisotropy = renderer.capabilities.getMaxAnisotropy();   // eğik bakışta netlik
      const c = GOK_PARLAKLIK;
      scene.add(new THREE.Mesh(
        new THREE.SphereGeometry(yaricap, 96, 48),
        new THREE.MeshBasicMaterial({ map: t, color: new THREE.Color(c, c, c * 1.15),
                                      side: THREE.BackSide, depthWrite: false, toneMapped: false })
      ));
    }, undefined, () => dene(i + 1));                            // dosya yoksa sıradakini dene
  }
  dene(0);

  return t => { if (mat) mat.uniforms.uZaman.value = t; };
}

// ---------- Yedek: rastgele keskin yıldızlar (hiç doku bulunamazsa) ----------
function yapayYildizlar(scene, renderer, R) {
  const gauss = () => Math.sqrt(-2 * Math.log(1 - Math.random())) * Math.cos(2 * Math.PI * Math.random());
  const N = 6000;
  const konum = new Float32Array(N * 3), renk = new Float32Array(N * 3), boyut = new Float32Array(N), faz = new Float32Array(N);
  const v = new THREE.Vector3();
  for (let i = 0; i < N; i++) {
    v.set(gauss(), gauss(), gauss()).normalize().multiplyScalar(R);
    konum.set([v.x, v.y, v.z], i * 3);
    const r = Math.random();
    boyut[i] = 1.3 + 2.0 * Math.pow(r, 12);
    const isik = 0.2 + 0.8 * Math.pow(r, 5);
    renk.set([isik, isik, isik], i * 3);
    faz[i] = Math.random();
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(konum, 3));
  geo.setAttribute('aRenk', new THREE.BufferAttribute(renk, 3));
  geo.setAttribute('aBoyut', new THREE.BufferAttribute(boyut, 1));
  geo.setAttribute('aFaz', new THREE.BufferAttribute(faz, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uZaman: { value: 0 }, uPiksel: { value: renderer.getPixelRatio() } },
    vertexShader: `attribute vec3 aRenk; attribute float aBoyut; attribute float aFaz;
      uniform float uZaman; uniform float uPiksel; varying vec3 vRenk;
      void main() { gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = max(1.0, aBoyut * uPiksel);
        vRenk = aRenk * (0.85 + 0.15 * sin(uZaman * (0.7 + aFaz) + aFaz * 6.2831)); }`,
    fragmentShader: `varying vec3 vRenk;
      void main() { float a = 1.0 - smoothstep(0.15, 0.5, length(gl_PointCoord - 0.5));
        if (a < 0.02) discard; gl_FragColor = vec4(vRenk, a); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending
  });
  scene.add(new THREE.Points(geo, mat));
  return mat;
}
