/* Developed with assistance from Claude (Anthropic). */
// =====================================================================
// ORBITRARY — ANA SAYFA 3D SAHNESİ
// Dönen Dünya (gündüz/gece shader'ı + atmosfer), uzakta Ay ve Mars,
// MOON | MARS kapsülüyle kamera uçuşları.
// =====================================================================
import * as THREE from 'three';
import { gsap } from 'gsap';
import { gokyuzuEkle } from './gokyuzu.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const azHareket = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const kap = document.getElementById('hero-sahne');
const mobil = window.innerWidth < 800;
const SEG = mobil ? 64 : 128;   // küre segment sayısı: telefonda daha az üçgen

// ---------------------------------------------------------------------
// 1) RENDERER, SAHNE, KAMERA
// ---------------------------------------------------------------------
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, mobil ? 1.5 : 2));
renderer.setClearColor(0x000000, 0);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;
kap.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 500);

// ---------------------------------------------------------------------
// 2) GÜNEŞ
// ---------------------------------------------------------------------
// Bu sayfada güneş dünyada SABİT. GUNES_YON: herhangi bir noktadan güneşe doğru birim vektör.
// DirectionalLight her yerde aynı yönden geldiği için Dünya, Ay ve Mars aynı güneşle aydınlanır
const GUNES_YON = V(-1, 0.25, 0.6).normalize();
const GEZEGEN_ISIK = V(0, 0.3, 0.95).normalize();   // Ay ve Mars'ın ışığı
const gunes = new THREE.DirectionalLight(0xfff4e8, 3.0);
gunes.position.copy(GEZEGEN_ISIK).multiplyScalar(50);
scene.add(gunes);
scene.add(new THREE.AmbientLight(0x8fa6ff, 0.03));

// ---------------------------------------------------------------------
// 3) DOKU YÜKLEME YARDIMCISI — dosya yoksa hata vermez, null döndürür
// ---------------------------------------------------------------------
const yukleyici = new THREE.TextureLoader();
const doku = (yol, renkli = true) => new Promise(tamam => {
  yukleyici.load(yol, t => {
    if (renkli) t.colorSpace = THREE.SRGBColorSpace;   // renk görselleri sRGB; bulut maskesi değil
    t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    tamam(t);
  }, undefined, () => { console.warn('Doku bulunamadı (atlanıyor):', yol); tamam(null); });
});

// ---------------------------------------------------------------------
// 4) GÖKYÜZÜ (ortak dosya: js/gokyuzu.js)
// ---------------------------------------------------------------------
const gokyuzuGuncelle = gokyuzuEkle(scene, renderer);

// ---------------------------------------------------------------------
// 5) ORTAK SHADER PARÇASI: dünya koordinatında normal ve konum
// ---------------------------------------------------------------------
// modelMatrix: nesnenin kendi koordinatlarından dünya koordinatlarına dönüşüm.
// Normali de aynı dönüşümle çeviriyoruz ki güneş yönüyle (o da dünya koordinatında) karşılaştırabilelim
const VS = /* glsl */`
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vPosW;
  void main() {
    vUv = uv;
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vec4 w = modelMatrix * vec4(position, 1.0);
    vPosW = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }`;

// ---------------------------------------------------------------------
// 6) DÜNYA
// ---------------------------------------------------------------------
const GOVDE = {
  dunya: { merkez: V(0, 0, 0),      R: 1.0  },
  ay:    { merkez: V(-7, 1.4, -9),  R: 0.7  },   // gerçek ölçek değil, estetik kompozisyon
  mars:  { merkez: V(9, -1.2, -16), R: 0.95 }
};

// Dünya bir grubun içinde: grup 23.4° eğik (eksen eğikliği), Dünya bu eğik eksen etrafında döner
const dunyaGrup = new THREE.Group();
dunyaGrup.rotation.z = THREE.MathUtils.degToRad(23.4);
scene.add(dunyaGrup);

const dunya = new THREE.Mesh(
  new THREE.SphereGeometry(1, SEG, SEG / 2),
  new THREE.MeshStandardMaterial({ color: '#1d4f8a', roughness: 1 })   // dokular gelene kadar düz mavi
);
dunyaGrup.add(dunya);

// GÜNDÜZ / GECE SHADER'I
//   n = yüzey normali, s = güneş yönü (ikisi de birim vektör), d = n · s
//     d > 0 → gündüz, d < 0 → gece, d = 0 → gündüz-gece sınırı (terminatör)
//   Gündüz rengi: albedo · max(d, 0)        (Lambert yasası: aydınlanma ∝ cos θ)
//   Karışım ağırlığı: w = smoothstep(−0.12, 0.18, d)
//     smoothstep(a, b, x) = 3u² − 2u³,  u = clamp((x − a)/(b − a), 0, 1)
//     → d ≤ −0.12'de w = 0 (tam gece), d ≥ 0.18'de w = 1 (tam gündüz), arada yumuşak S-eğrisi
//   Son renk = (1 − w)·gece + w·gündüz
//
//   OKYANUSU GERÇEKÇİ YAPAN ÜÇ EK:
//   1) Su maskesi: bir pikselde mavinin payı b/(r+g+b) yüksekse orası sudur.
//      su = smoothstep(0.35, 0.6, b/(r+g+b)) → kara ≈ 0, açık deniz ≈ 1
//      (Okyanusun dokusu deniz tabanı kabartmasını gösteren Blue Marble 'topography + bathymetry' haritasından gelir.)
//   2) Güneş parlaması (Blinn–Phong): v = kameraya yön, h = normalize(s + v) (güneş ile bakışın ortası).
//      Parlama = (n·h)^80 · su. Üs büyük olduğu için sadece güneşin yansıdığı küçük bir bölge parlar,
//      gerçek fotoğraflardaki gibi okyanusta beyazımsı bir leke oluşur. Kara parlamaz (su = 0).
//   3) Atmosfer saçılması: kenara yaklaştıkça (n·v → 0) yüzeyi daha kalın bir hava tabakasından görürüz;
//      renk, (1 − n·v)³ ağırlığıyla soluk bir maviye karışır.
const DUNYA_FS = /* glsl */`
  uniform sampler2D uGunduz;
  uniform sampler2D uGece;
  uniform vec3 uGunesYon;
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vPosW;
  void main() {
    vec3 n = normalize(vNormalW);
    vec3 v = normalize(cameraPosition - vPosW);
    float d = dot(n, uGunesYon);
    vec3 albedo = texture2D(uGunduz, vUv).rgb;

    // 1) su maskesi ve okyanus rengi
    float su = smoothstep(0.35, 0.6, albedo.b / (albedo.r + albedo.g + albedo.b + 1e-4));
    float parlaklik = dot(albedo, vec3(0.2126, 0.7152, 0.0722));
    // Okyanus dokusu artık deniz tabanı kabartmalı (batimetri) olduğu için rengine çok az dokunuyoruz:
    // sadece %15 soğuk maviye çekiyoruz ki fazla turkuaz durmasın
    vec3 okyanus = mix(albedo, parlaklik * vec3(0.55, 0.75, 1.0) * 1.9, 0.15);
    albedo = mix(albedo, okyanus, su);

    vec3 gunduz = albedo * max(d, 0.0) * 1.7 + albedo * 0.015;   // Lambert + çok hafif ortam ışığı

    // 2) güneş parlaması (sadece suda, sadece gündüz)
    //    İki katman: (n·h)^900 → güneşin yansıdığı küçük, keskin bir nokta;
    //                (n·h)^60  → çevresinde çok hafif, geniş bir parıltı.
    //    Üs ne kadar büyükse leke o kadar küçük olur (önceki 80 fazla büyük ve bulanıktı).
    //    Parlamayı tamamen kapatmak için iki çarpanı (0.35 ve 0.06) 0 yap
    vec3 h = normalize(uGunesYon + v);
    float nh = max(dot(n, h), 0.0);
    float parlama = pow(nh, 1500.0) * 0.18 * su * smoothstep(0.0, 0.2, d);
    gunduz += vec3(1.0, 0.95, 0.88) * parlama;

    // 3) kenarda atmosfer pusu
    float kenar = pow(1.0 - max(dot(n, v), 0.0), 3.0);
    gunduz = mix(gunduz, vec3(0.32, 0.5, 0.9) * max(d, 0.0) * 1.1, kenar * 0.55);

    vec3 gece   = texture2D(uGece, vUv).rgb * 1.3;               // şehir ışıkları: 1.3'ü büyütürsen parlar
    float w = smoothstep(-0.12, 0.18, d);
    gl_FragColor = vec4(mix(gece, gunduz, w), 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }`;

const siyah = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1);   // gece dokusu yoksa
siyah.needsUpdate = true;

Promise.all([doku('textures/earth_day.jpg'), doku('textures/earth_night.jpg')]).then(([gunduz, gece]) => {
  if (!gunduz) return;
  dunya.material.dispose();
  dunya.material = new THREE.ShaderMaterial({
    uniforms: { uGunduz: { value: gunduz }, uGece: { value: gece || siyah }, uGunesYon: { value: GUNES_YON } },
    vertexShader: VS,
    fragmentShader: DUNYA_FS
  });
});

// Bulutlar (dosya varsa): %1.2 büyük saydam küre. alphaMap: parlaklık = opaklık
let bulut = null;
doku('textures/earth_clouds.jpg', false).then(t => {
  if (!t) return;
  bulut = new THREE.Mesh(
    new THREE.SphereGeometry(1.012, SEG, SEG / 2),
    new THREE.MeshStandardMaterial({ color: 0xffffff, alphaMap: t, transparent: true, depthWrite: false, roughness: 1 })
  );
  dunyaGrup.add(bulut);
});

// ---------------------------------------------------------------------
// 7) ATMOSFER PARILTISI (Fresnel)
// ---------------------------------------------------------------------
//   v = yüzeyden kameraya birim vektör, n = normal
//   n·v = 1 → diskin ortası (yüzeye dik bakış), n·v = 0 → diskin kenarı (teğet bakış)
//   Fresnel terimi: F = (1 − n·v)^p → ortada 0, kenarda 1. p büyüdükçe hale incelir
//   Gece tarafında hale olmasın: L = smoothstep(−0.25, 0.4, n·s)
//   Renk = renk · F · L · güç, toplamalı (additive) karıştırma
const ATM_FS = /* glsl */`
  uniform vec3 uRenk;
  uniform vec3 uGunesYon;
  uniform float uGuc;
  uniform float uUs;
  varying vec3 vNormalW;
  varying vec3 vPosW;
  void main() {
    vec3 n = normalize(vNormalW);
    vec3 v = normalize(cameraPosition - vPosW);
    float F = pow(1.0 - clamp(dot(n, v), 0.0, 1.0), uUs);
    float L = smoothstep(-0.25, 0.4, dot(n, uGunesYon));
    gl_FragColor = vec4(uRenk * F * L * uGuc, 1.0);
  }`;

function atmosfer(R, renk, guc, us, yon = GUNES_YON) {
  return new THREE.Mesh(
    new THREE.SphereGeometry(R, SEG, SEG / 2),
    new THREE.ShaderMaterial({
      uniforms: { uRenk: { value: new THREE.Color(renk) }, uGunesYon: { value: yon },
                  uGuc: { value: guc }, uUs: { value: us } },
      vertexShader: VS, fragmentShader: ATM_FS,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending
    })
  );
}
scene.add(atmosfer(1.015, '#8ab8ff', 1.0, 4.5));   // Dünya: ince, soluk mavi hale. guc büyürse parlar, us büyürse incelir

// ---------------------------------------------------------------------
// 8) AY ve MARS
// ---------------------------------------------------------------------
function gezegenYap(ad, yol, tumsek) {
  const g = GOVDE[ad];
  const m = new THREE.Mesh(
    new THREE.SphereGeometry(g.R, SEG, SEG / 2),
    new THREE.MeshStandardMaterial({ color: ad === 'ay' ? '#777' : '#9a4a2b', roughness: 1 })
  );
  m.position.copy(g.merkez);
  scene.add(m);
  doku(yol).then(t => {
    if (!t) return;
    m.material.map = t;
    m.material.bumpMap = t;          // geçici kabartma (gerçek yükseklik haritası ileride)
    m.material.bumpScale = tumsek;
    m.material.color.set(0xffffff);
    m.material.needsUpdate = true;
  });
  return m;
}
const ay = gezegenYap('ay', 'textures/moon_color.jpg', 3);
const mars = gezegenYap('mars', 'textures/mars_color.jpg', 2);

const marsAtm = atmosfer(GOVDE.mars.R * 1.012, '#ff9a5a', 0.6, 5.0, GEZEGEN_ISIK);   // Mars: çok ince turuncu hale
marsAtm.position.copy(GOVDE.mars.merkez);
scene.add(marsAtm);

// ---------------------------------------------------------------------
// 9) KAMERA GÖRÜNÜMLERİ
// ---------------------------------------------------------------------
// Ay ve Mars'a güneşe yakın bir yönden bakıyoruz → gezegenin çoğu aydınlık (şişkin ay evresi)
const BAKIS = V(-0.4, 0.1, 0.91).normalize();
const GORUNUM = {};

function gorunumHesapla() {
  const en = kap.clientWidth / kap.clientHeight;
  const pay = 1 / Math.min(1, en * 1.25);   // dar (dikey) ekranda kamerayı geri al, gezegen taşmasın
  GORUNUM.dunya = { poz: V(0, 0.1, 4.4 * pay), hedef: V(0, 0.3, 0) };   // hedef Dünya'nın üstünde → Dünya ekranın alt yarısında, alt başlığın arkasında
  for (const ad of ['ay', 'mars']) {
    const g = GOVDE[ad];
    // Gezegen ekranın üst kısmında büyük bir YARIM KÜRE olsun:
    //   uzaklık d = 2.6R → görünen yarı yükseklik h = d·tan20° ≈ 0.95R
    //   bakış noktası merkezin 1.05R altında → merkez ekranın üst kenarının biraz üstünde kalır
    //   (NDC y ≈ +1.1); gezegenin alt kenarı ekranın ortasına iner, yazılar hemen altında başlar.
    //   YUKARI'yı büyütürsen gezegen daha yukarı çıkar (daha az görünür), küçültürsen aşağı iner
    const YUKARI = 1.05;
    GORUNUM[ad] = {
      poz: g.merkez.clone().addScaledVector(BAKIS, g.R * 2.6 * pay),
      hedef: g.merkez.clone().add(V(0, -g.R * YUKARI * pay, 0))
    };
  }
}

let aktif = 'dunya';                 // şu an kameranın baktığı gök cismi
let ucusTween = null;
const bakilanNokta = V(0, 0, 0);     // kameranın baktığı nokta (lookAt)

function boyutla() {
  const w = kap.clientWidth, h = kap.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  gorunumHesapla();
  if (!ucusTween || !ucusTween.isActive()) {   // uçuşta değilsek kamerayı yeni görünüme yerleştir
    camera.position.copy(GORUNUM[aktif].poz);
    bakilanNokta.copy(GORUNUM[aktif].hedef);
  }
}
new ResizeObserver(boyutla).observe(kap);
boyutla();

// ---------------------------------------------------------------------
// 10) UÇUŞ: KÜBİK BÉZIER EĞRİSİ
// ---------------------------------------------------------------------
//   B(t) = (1−t)³·P0 + 3(1−t)²t·P1 + 3(1−t)t²·P2 + t³·P3,   t ∈ [0, 1]
//   P0 = başlangıç, P3 = varış
//   P1 = P0'dan çıktığımız gezegenden DIŞARI doğru bir nokta  → önce geri çekilir (zoom-out)
//   P2 = P3'ten varacağımız gezegenden DIŞARI doğru bir nokta → hedefe uzaktan yaklaşır (zoom-in)
//   B'(0) ∝ P1 − P0 ve B'(1) ∝ P3 − P2: kalkışta tam geri, varışta tam ileri hareket.
//   t'yi GSAP 'power2.inOut' sürer: yavaş kalkış, hızlanma, yavaş iniş.
//   Bakılan nokta da smoothstep(0.15, 0.75, t) ile eski merkezden yenisine kayar
function ucus(hedefAd) {
  if (hedefAd === aktif) return;
  const basMerkez = GOVDE[aktif].merkez, sonMerkez = GOVDE[hedefAd].merkez;
  const P0 = camera.position.clone();
  const P3 = GORUNUM[hedefAd].poz.clone();
  const disari0 = P0.clone().sub(basMerkez);
  const disari3 = P3.clone().sub(sonMerkez);
  const P1 = P0.clone().addScaledVector(disari0.clone().normalize(), Math.max(disari0.length() * 1.5, 3.5));
  const P2 = P3.clone().addScaledVector(disari3.clone().normalize(), Math.max(disari3.length() * 2.5, 4.5));
  const basHedef = bakilanNokta.clone(), sonHedef = GORUNUM[hedefAd].hedef.clone();

  aktif = hedefAd;
  const durum = { t: 0 };
  if (ucusTween) ucusTween.kill();
  ucusTween = gsap.to(durum, {
    t: 1,
    duration: azHareket ? 0.01 : 2.8,   // uçuş süresi (saniye)
    ease: 'power2.inOut',
    onUpdate() {
      const t = durum.t, u = 1 - t;
      camera.position.set(0, 0, 0)
        .addScaledVector(P0, u * u * u)
        .addScaledVector(P1, 3 * u * u * t)
        .addScaledVector(P2, 3 * u * t * t)
        .addScaledVector(P3, t * t * t);
      bakilanNokta.lerpVectors(basHedef, sonHedef, THREE.MathUtils.smoothstep(t, 0.15, 0.75));
    }
  });
}

// ---------------------------------------------------------------------
// 11) MOON | MARS KAPSÜLÜ ve GİRİŞ METİNLERİ
// ---------------------------------------------------------------------
const METIN = {
  dunya: { etiket: 'NASA Space Apps Challenge 2026',
           baslik: 'Find the places on Earth that come closest to the Moon and Mars',
           aciklama: 'Pick a world, pick a site, and see its three best analogs on Earth, compared across eight categories and built on NASA and partner space-agency data.',
           buton: 'Explore mode →', link: 'explore.html' },
  ay:    { etiket: 'Destination · The Moon',
           baslik: 'Where on Earth can we rehearse the Moon?',
           aciklama: 'From the south pole base candidates to the Apollo plains: pick a site and see its closest analogs on Earth.',
           buton: 'Explore the Moon →', link: 'explore.html?body=moon' },
  mars:  { etiket: 'Destination · Mars',
           baslik: 'Where on Earth can we rehearse Mars?',
           aciklama: 'From ancient river deltas to volcanic plains: pick a landing site and see its closest analogs on Earth.',
           buton: 'Explore Mars →', link: 'explore.html?body=mars' }
};

const segment = document.querySelector('.segment');
const govdeButonlari = document.querySelectorAll('[data-govde]');
const metinler = document.querySelectorAll('#hero-etiket, #hero-baslik, #hero-aciklama');
const kesifBtn = document.getElementById('kesif-btn');

function arayuz(ad) {
  segment.dataset.secim = ad === 'dunya' ? '' : ad;   // boşsa mavi hap gizlenir
  govdeButonlari.forEach(b => b.classList.toggle('secili', b.dataset.govde === ad));
  kesifBtn.href = METIN[ad].link;
  kesifBtn.textContent = METIN[ad].buton;
  // Yazılar solup yukarı kalkar, değişir, kamera varırken aşağıdan geri gelir
  gsap.to(metinler, {
    opacity: 0, y: -10, duration: 0.3, stagger: 0.04,
    onComplete() {
      document.getElementById('hero-etiket').textContent = METIN[ad].etiket;
      document.getElementById('hero-baslik').textContent = METIN[ad].baslik;
      document.getElementById('hero-aciklama').textContent = METIN[ad].aciklama;
      gsap.fromTo(metinler, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.6, stagger: 0.07, delay: azHareket ? 0 : 1.4 });
    }
  });
}

// Kural: seçili olana tekrar basılırsa Dünya'ya dön; değilse ona uç (Ay ↔ Mars dahil)
govdeButonlari.forEach(btn => btn.addEventListener('click', () => {
  const istenen = btn.dataset.govde;               // 'ay' ya da 'mars'
  const yeni = aktif === istenen ? 'dunya' : istenen;
  ucus(yeni);
  arayuz(yeni);
}));

// GEZEGENLERE TIKLAMA: sahnedeki Ay'a ya da Mars'a tıklamak, üstteki kapsülde seçmekle aynı uçuşu başlatır.
// Dünya'ya tıklamak (Ay ya da Mars'tayken) Dünya'ya döndürür. Zaten baktığın gezegene tıklamak bir şey yapmaz.
// Raycaster: kameradan farenin olduğu yöne bir ışın gönderir, çarptığı ilk gezegeni bulur.
const tiklamaIsini = new THREE.Raycaster();
const fareNokta = new THREE.Vector2();
const TIKLANABILIR = [[dunya, 'dunya'], [ay, 'ay'], [mars, 'mars']];
function fareninAltindaki(e) {
  const r = renderer.domElement.getBoundingClientRect();
  fareNokta.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  tiklamaIsini.setFromCamera(fareNokta, camera);
  const vurus = tiklamaIsini.intersectObjects(TIKLANABILIR.map(([m]) => m), false)[0];
  return vurus ? TIKLANABILIR.find(([m]) => m === vurus.object)[1] : null;
}
renderer.domElement.addEventListener('click', e => {
  const ad = fareninAltindaki(e);
  if (!ad || ad === aktif) return;
  ucus(ad);
  arayuz(ad);
});
// Fare tıklanabilir bir gezegenin üstündeyken imleç el işaretine dönsün
renderer.domElement.addEventListener('pointermove', e => {
  const ad = fareninAltindaki(e);
  renderer.domElement.style.cursor = ad && ad !== aktif ? 'pointer' : '';
});

// ---------------------------------------------------------------------
// 12) ANİMASYON DÖNGÜSÜ
// ---------------------------------------------------------------------
// Giriş ekranı görünmüyorsa (aşağı kaydırıldıysa) çizme: pil ve işlemci tasarrufu
let gorunur = true;
new IntersectionObserver(([g]) => { gorunur = g.isIntersecting; }).observe(kap);

const saat = new THREE.Clock();
renderer.setAnimationLoop(() => {
  const dt = Math.min(saat.getDelta(), 0.05);   // sekmeye geri dönünce ani sıçrama olmasın
  if (!gorunur) return;
  if (!azHareket) {
    dunya.rotation.y += 0.05 * dt;              // rad/sn: bir tur ≈ 2 dakika
    if (bulut) bulut.rotation.y += 0.065 * dt;  // bulutlar biraz daha hızlı
    ay.rotation.y += 0.05 * dt;
    mars.rotation.y += 0.08 * dt;
    gokyuzuGuncelle(saat.elapsedTime);          // yıldız parıltısı
  }
  camera.lookAt(bakilanNokta);
  renderer.render(scene, camera);
});
