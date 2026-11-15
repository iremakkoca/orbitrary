/* Developed with assistance from Claude (Anthropic). */
// ORBITRARY — VERİ KATMANI
// data/ klasöründeki sonuçları okur ve sayfalara hazır nesne verir. Hiçbir puan hesaplamaz.
// Biçim: kayit\SITE_VERI_NOTU.md (veri tarafı). Sayıların hepsi dosyalardan gelir.

export const GOREV_SIRA = ['genel', 'mobility', 'geology', 'ice', 'astro'];
// explore.html'in eski Türkçe görev anahtarları → veri dosyalarındaki anahtarlar
export const SITE_GOREV = { genel: 'genel', hareket: 'mobility', jeoloji: 'geology', buz: 'ice', astrobiyoloji: 'astro' };
export const GOREV_AD = { genel: 'General', mobility: 'Mobility test', geology: 'Geology', ice: 'Ice & resources', astro: 'Astrobiology' };
export const KAT_AD = ['Topography', 'Topology', 'Geology', 'Mineralogy', 'Thermal', 'Water/Ice', 'Dust', 'Illumination'];
export const KAT_ANAHTAR = ['topografya', 'topoloji', 'jeoloji', 'mineraloji', 'termal', 'su_buz', 'toz', 'aydinlanma'];

const onbellek = {};
function json(url) {
  if (!onbellek[url]) onbellek[url] = fetch(url).then(r => { if (!r.ok) throw new Error(url + ' ' + r.status); return r.json(); });
  return onbellek[url];
}
export const meta = () => json('data/meta.json');
export const earth = () => json('data/earth.json');
export const metin = () => json('data/metin.json');
export const ozet = () => json('data/ozet.json');
// Kaynak dosyada Türkçe kalan üç ad, sitede İngilizce gösterilir
export const AD_EN = { 'M-SP': 'Lunar south pole test point', 'M-SHK': 'Shackleton crater', 'R-PHX': 'Phoenix landing site' };
export const hedefler = () => json('data/hedefler.json').then(H => H.map(h => AD_EN[h.kimlik] ? { ...h, ad: AD_EN[h.kimlik] } : h));
export const hedefFoto = () => json('data/hedef_foto.json').catch(() => ({}));
export const analoglar = () => json('data/analog.json');
export const fotolar = () => json('data/analog_foto.json').catch(() => ({}));
export const liste = id => json(`data/liste/liste_${encodeURIComponent(id)}.json`);

// ayar.json yaprakları { deger: … } biçiminde; değeri çıkar
export const deger = x => (x && typeof x === 'object' && 'deger' in x) ? x.deger : x;

// ---------- Izgara: kod\izgara.py Halka.tikla ile birebir ----------
// halka i = ⌊(φ + π/2)/Δφ⌋, Δφ = π/M;  sıra j = ⌊λ·m_i/2π⌋ (λ: 0–360°);  kimlik = Σ_{k<i} m_k + j
export function hucreBul(g, lat, lon) {
  if (!g._ofset) { g._ofset = [0]; for (const m of g.m) g._ofset.push(g._ofset[g._ofset.length - 1] + m); }
  const phi = lat * Math.PI / 180;
  const lam = ((((lon % 360) + 360) % 360)) * Math.PI / 180;
  const dphi = Math.PI / g.M;
  let i = Math.min(Math.floor((phi + Math.PI / 2) / dphi), g.M - 1);
  i = Math.max(i, 0);
  const m = g.m[i];
  const j = Math.min(Math.floor(lam * m / (2 * Math.PI)), m - 1);
  return { halka: i, sira: j, kimlik: g._ofset[i] + j };
}
// meta.json'daki 10 test noktasıyla kendini sınar (sonuç konsolda)
export async function izgaraTesti() {
  const M = await meta();
  let hata = 0;
  for (const ad of ['moon', 'mars']) for (const t of M.izgara[ad].test) {
    const h = hucreBul(M.izgara[ad], t.enlem, t.boylam);
    if (h.kimlik !== t.kimlik || h.halka !== t.halka || h.sira !== t.sira) { hata++; console.error('hucreBul tutmuyor', ad, t, h); }
  }
  console.log(hata ? `hucreBul: ${hata} test FAIL` : 'hucreBul: 20/20 test PASS');
  return hata === 0;
}

// ---------- Harita (Katman B) halka dosyası ----------
const halkaOnb = {};
function halka(cisim, i, m) {
  const k = cisim + i;
  if (!halkaOnb[k]) halkaOnb[k] = fetch(`data/grid/${cisim}/${i}.bin`).then(r => {
    if (!r.ok) throw new Error('grid ' + cisim + ' ' + i); return r.arrayBuffer();
  }).then(buf => {
    const n = m * 15; let o = 0;
    const e = new Uint32Array(buf.slice(0, n * 4)); o = n * 4;
    const P = new Uint8Array(buf, o, n); o += n;
    const s = new Uint8Array(buf, o, n * 8); o += n * 8;
    const ek = new Uint8Array(buf, o, n * 8); o += n * 8;
    const d = new Uint8Array(buf, o, m * 5); o += m * 5;
    if (o !== buf.byteLength) throw new Error('halka dosyası bayt sayısı tutmuyor');
    return { e, P, s, ek, d };
  });
  return halkaOnb[k];
}

let earthKimlik = null;
export async function earthSatir(i) {
  const E = await earth();
  return {
    satir: i, kimlik: E.kimlik[i], enlem: E.enlem[i], boylam: E.boylam[i], analog_id: E.analog_id[i], analog_km: E.analog_km[i],
    pv: E.pv[i], kar_buz: E.kar_buz[i], egim_orani: E.egim_orani[i], permafrost: E.permafrost[i], kuraklik: E.kuraklik[i]
  };
}
export async function earthKimligiyle(kimlik) {
  const E = await earth();
  if (!earthKimlik) { earthKimlik = new Map(); E.kimlik.forEach((k, i) => earthKimlik.set(k, i)); }
  const i = earthKimlik.get(kimlik);
  return i == null ? null : earthSatir(i);
}

// Tıklanan nokta → 5 görevin ilk 3'ü. govde: 'ay' | 'mars'
export async function sonuc(govde, lat, lon) {
  const M = await meta();
  const cisim = govde === 'ay' ? 'moon' : 'mars';
  if (!M.katman_B[govde] || !M.katman_B[govde].tamam) return { hazir: false };
  const g = M.izgara[cisim];
  const h = hucreBul(g, lat, lon);
  const d = await halka(cisim, h.halka, g.m[h.halka]);
  const out = { hazir: true, ...h, gorevler: {} };
  for (let gi = 0; gi < 5; gi++) {
    const durum = d.d[h.sira * 5 + gi];
    const es = [];
    for (let q = 0; q < 3; q++) {
      const b = (h.sira * 5 + gi) * 3 + q;
      if (d.e[b] === 0xFFFFFFFF) continue;
      const s = [], eksik = [];
      for (let k = 0; k < 8; k++) { const v = d.s[b * 8 + k]; s.push(v === 255 ? null : v / M.olcek); eksik.push(d.ek[b * 8 + k]); }
      es.push({ earth: await earthSatir(d.e[b]), P: d.P[b] === 255 ? null : d.P[b] / M.olcek, s, eksik });
    }
    out.gorevler[GOREV_SIRA[gi]] = { durum: durum === 1 ? 'not applicable' : 'computed', eslesme: es };
  }
  return out;
}

// ---------- Yardımcılar ----------
// Görev ağırlıkları: belge 7.3 formülü, değerler meta.ayar.agirlik'ten (ana pay / ana kategoriler)
export async function agirliklar(gorev) {
  const M = await meta();
  if (gorev === 'genel') return Array(8).fill(1 / 8);
  const pay = deger(M.ayar.agirlik.ana_pay), ana = deger(M.ayar.agirlik.ana_kategoriler)[gorev];
  return Array.from({ length: 8 }, (_, k) => ana.includes(k + 1) ? pay / ana.length : (1 - pay) / (8 - ana.length));
}
// Known analog / Near / New candidate (eşikler meta.ayar.analog_uzaklik_km; puana girmez)
export async function analogEtiketi(km) {
  const M = await meta(); const T = await metin();
  const a = deger(M.ayar.analog_uzaklik_km);
  if (km == null || !a) return null;
  const e = T.analog.etiket;
  if (km < a.bilinen_alti) return { tur: 'known', ad: e.known.ad, aciklama: e.known.aciklama };
  if (km <= a.yakin_ust) return { tur: 'near', ad: e.near.ad, aciklama: e.near.aciklama };
  return null;   // 100 km'den uzak: etiket gösterilmez
}
export const puanYuzde = P => P == null ? '—' : Math.round(100 * P) + '%';
export const yuzde = (x, d = 0) => x == null ? '—' : (100 * x).toFixed(d) + '%';
export const enlemYazi = (lat, d = 2) => `${Math.abs(lat).toFixed(d)}°${lat >= 0 ? 'N' : 'S'}`;
export const boylamYazi = (lon, d = 2) => `${Math.abs(lon).toFixed(d)}°${lon >= 0 ? 'E' : 'W'}`;
export const koordYazi = (lat, lon, d = 2) => `${enlemYazi(lat, d)}, ${boylamYazi(lon, d)}`;
// Bilinen analog sahanın adı (analog.json'dan); yoksa kimlikten okunur biçim
const SAHA_AD = {};
analoglar().then(A => A.forEach(x => { if (x.ad) SAHA_AD[x.id] = x.ad; })).catch(() => {});
export const saha = id => SAHA_AD[id] || (id || '').replace(/^[a-z]-/, '').replace(/-/g, ' ');

// Hangi kategoride en yakın / en uzak (yalnız verisi olanlar)
export function guclu_zayif(s, n = 3) {
  const v = s.map((x, k) => ({ k, x })).filter(o => o.x != null).sort((a, b) => b.x - a.x);
  return { guclu: v.slice(0, n), zayif: v.slice(-n).reverse() };
}
// Eksik kategori notları (metin.json → eksik_taraf). kod: 1 hedef, 2 Dünya, 3 iki taraf; ya da 'hedef'/'dunya'/'iki_taraf'
export async function eksikNotlari(eksik) {
  const T = await metin();
  const ad = { 1: 'hedef', 2: 'dunya', 3: 'iki_taraf' };
  const notlar = [];
  eksik.forEach((e, k) => {
    const key = typeof e === 'number' ? ad[e] : e;
    if (key) notlar.push(`${KAT_AD[k]}: ${T.eksik_taraf[key]}`);
  });
  return notlar;
}

// ---------- Radar (8-gen) ----------
// sim: 8 değer (null = veri yok, eksen gri-noktalı; çokgen o ekseni atlar). mis = 1 − sim (turuncu kesikli)
export function radar(svg, sim, { mis = true, boyut = 'normal' } = {}) {
  const cx = 160, cy = 160, R = 110;
  svg.setAttribute('viewBox', '-55 0 430 320');
  const aci = i => -Math.PI / 2 + i * 2 * Math.PI / 8;
  const P = (i, v) => `${cx + R * v * Math.cos(aci(i))},${cy + R * v * Math.sin(aci(i))}`;
  let s = '';
  for (let k = 1; k <= 4; k++) s += `<polygon points="${KAT_AD.map((_, i) => P(i, k / 4)).join(' ')}" fill="none" stroke="#243047" stroke-dasharray="3 4"/>`;
  KAT_AD.forEach((ad, i) => {
    const yok = sim && sim[i] == null;
    s += `<line x1="${cx}" y1="${cy}" x2="${cx + R * Math.cos(aci(i))}" y2="${cy + R * Math.sin(aci(i))}" stroke="${yok ? '#55607a' : '#243047'}" ${yok ? 'stroke-dasharray="2 4"' : ''}/>`;
    const lx = cx + (R + 32) * Math.cos(aci(i)), ly = cy + (R + 32) * Math.sin(aci(i)) + 4;
    s += `<text x="${lx}" y="${ly}" text-anchor="middle" font-size="12.5" font-family="Space Grotesk, sans-serif" fill="${yok ? '#55607a' : '#9aa7bb'}">${ad}${yok ? ' · no data' : ''}</text>`;
  });
  if (sim) {
    const nokt = f => sim.map((v, i) => v == null ? null : P(i, f(v))).filter(Boolean).join(' ');
    if (mis) s += `<polygon points="${nokt(v => 1 - v)}" fill="none" stroke="#ff9f5c" stroke-width="2" stroke-dasharray="6 5"/>`;
    s += `<polygon points="${nokt(v => v)}" fill="#5cc8ff" fill-opacity="0.22" stroke="#5cc8ff" stroke-width="2"/>`;
    sim.forEach((v, i) => { if (v != null) s += `<circle cx="${cx + R * v * Math.cos(aci(i))}" cy="${cy + R * v * Math.sin(aci(i))}" r="3" fill="#5cc8ff"/>`; });
  }
  svg.innerHTML = s;
}

// ---------- Uydu haritası (Leaflet, sayfada global L) ----------
export const KAROLAR = {
  url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  etiket: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
  arazi: 'https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade_Dark/MapServer/tile/{z}/{y}/{x}',
  atif: 'Imagery &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community'
};
export function uyduHaritasi(el, lat, lon, { zoom = 10, kare = true, noktalar = null } = {}) {
  if (!window.L) { el.innerHTML = '<p class="soluk">Map library could not be loaded.</p>'; return null; }
  if (el._harita) { el._harita.remove(); el._harita = null; }
  const sinir = L.latLngBounds([[-85, -180], [85, 180]]);
  const tek = !noktalar;
  // Bütün haritalarda aynı hareket: 4 seviye uzaktan başlar, görünür olunca 2,2 sn'de yaklaşır.
  const bas = tek ? Math.max(3, zoom - 2) : 2;
  const h = L.map(el, { zoomControl: true, attributionControl: true, minZoom: tek ? bas : 2, maxZoom: 17,
    maxBounds: sinir, maxBoundsViscosity: 1.0, worldCopyJump: false, scrollWheelZoom: false,
    zoomSnap: 0.25, fadeAnimation: false }).setView([lat, lon], bas);
  const ortak = { maxZoom: 17, maxNativeZoom: 17, noWrap: true, bounds: sinir, keepBuffer: 4 };
  const uydu = L.layerGroup([L.tileLayer(KAROLAR.url, { ...ortak, attribution: KAROLAR.atif }),
                             L.tileLayer(KAROLAR.etiket, { ...ortak, opacity: 0.9 })]).addTo(h);
  const arazi = L.layerGroup([L.tileLayer(KAROLAR.arazi, { ...ortak, maxNativeZoom: 16, attribution: 'Hillshade &copy; Esri' }), L.tileLayer(KAROLAR.etiket, { ...ortak, opacity: 0.9 })]);
  L.control.layers({ 'Satellite': uydu, 'Terrain': arazi }, null, { position: 'topright' }).addTo(h);
  h.zoomControl.setPosition('bottomright');
  if (tek && kare) {
    const lejant = L.control({ position: 'bottomleft' });
    lejant.onAdd = () => { const d = L.DomUtil.create('div', 'harita-lejant'); d.innerHTML = '<i></i>20 × 20 km comparison window'; return d; };
    lejant.addTo(h);
  }
  h.on('click', () => h.scrollWheelZoom.enable());
  h.on('mouseout', () => h.scrollWheelZoom.disable());
  let hareket;
  if (tek) {
    if (kare) {   // 20 km × 20 km pencere: ±10 km (enlem 1° ≈ 111,32 km)
      const dl = 10 / 111.32, dL = 10 / (111.32 * Math.max(0.05, Math.cos(lat * Math.PI / 180)));
      const kare_ = L.rectangle([[lat - dl, lon - dL], [lat + dl, lon + dL]], { color: '#ffffff', weight: 1.5, fill: false, opacity: 0 }).addTo(h);
      h.once('moveend', () => kare_.setStyle({ opacity: 0.9 }));
    }
    L.marker([lat, lon], { icon: L.divIcon({ className: 'nokta-isaret', iconSize: [14, 14] }), interactive: false }).addTo(h);
    hareket = () => h.flyTo([lat, lon], zoom, { duration: 1.8, easeLinearity: 0.25 });
  } else {
    const grup = [];
    noktalar.forEach(n => {
      const m = L.marker([n.lat, n.lon], { icon: L.divIcon({ className: 'nokta-isaret', iconSize: [12, 12] }) }).addTo(h);
      if (n.etiket) m.bindTooltip(n.etiket);
      if (n.tikla) m.on('click', n.tikla);
      grup.push([n.lat, n.lon]);
    });
    // Çok noktalı harita kendi kendine hareket etmez: hemen sığdırılır
    if (grup.length > 1) h.fitBounds(grup, { padding: [40, 40], maxZoom: 5, animate: false });
    else if (grup.length) h.setView(grup[0], 8, { animate: false });
    hareket = null;
  }
  // Harita ekrana girince bir kez başlar; kaydırırken yarıda başlamış animasyon görünmez
  const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); setTimeout(() => { h.invalidateSize(); hareket && hareket(); }, 250); } }, { threshold: 0.35 });
  io.observe(el);
  el._harita = h;
  setTimeout(() => h.invalidateSize(), 200);
  return h;
}
