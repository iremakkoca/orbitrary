# SITE_VERI_NOTU (veri tarafı, 2026-11-15T04:45:50)

Bütün dosyalar `C:\Users\USER\orbitrary\sonuc\site\` altında. Site bunları kendi `data\` klasörüne kopyalar; biçim
uymuyorsa siteyi değil kopyalayan hücreyi uyarla. Sayıların hepsi `ozet.json`'dan; elle sayı yok.
Harita durumu: Ay {'tamam': True, 'n': 94864, 'bitmis_blok': 371, 'blok': 371} · Mars {'tamam': True, 'n': 360654, 'bitmis_blok': 1409, 'blok': 1409}. Mars bitince veri tarafı `python kos.py site_veri`'yi tekrar çalıştırır.

## Dosyalar
- `meta.json`: sürüm ("Method v1.2"), `gorev_sira` [genel, mobility, geology, ice, astro] ve `gorev_ad` (General, Mobility test,
  Geology, Ice & resources, Astrobiology), `kategori_ad` (8, radar sırası), `olcek` 250, `yok_u8` 255, `yok_u32` 4294967295,
  `eksik_kod`, `durum_kod`, `izgara` (moon/mars: r_km, Delta_km, M halka sayısı, m[] halka başına pencere, n, `test` 10 nokta:
  enlem, boylam → kimlik, halka, sıra — JS `hucreBul` bunlarla assert edilir), `ayar` (kapı eşikleri, ağırlıklar, analog uzaklık
  eşikleri, referans büyüklükleri, uzaklık ve topoloji ayarları; kod\ayar.json'dan kopya).
- Izgara (kod\izgara.py, belge 4.2): halka i = ⌊(φ + π/2)/Δφ⌋, Δφ = π/M; sıra j = ⌊λ·m_i/2π⌋ (λ 0–360°); kimlik = Σ_{k<i} m_k + j.
- `grid/moon/<i>.bin`, `grid/mars/<i>.bin` (i = 0…M−1, halka başına; Katman B, "fast mode"). m = o halkadaki pencere sayısı.
  Sıra ile art arda, little-endian:
  1. `uint32 earth[m × 5 × 3]` — earth.json satır numarası; 4294967295 = yok (pencere, görev, sıra 1–3)
  2. `uint8 P[m × 5 × 3]` — round(P·250); 255 = yok
  3. `uint8 s[m × 5 × 3 × 8]` — round(s_k·250); 255 = yok (kategori sırası kategori_ad)
  4. `uint8 eksik[m × 5 × 3 × 8]` — 0 var, 1 hedefte (Ay/Mars) yok, 2 Dünya'da yok, 3 iki tarafta yok
  5. `uint8 durum[m × 5]` — 0 hesaplandı, 1 not applicable (kuru hedefte Ice)
  Π bu katmanda yok (her nokta için bütün Dünya taraması gerekir); kart okunuşu s_k'den.
- `earth.json` (82795 satır; yalnız sonuçlarda geçen Dünya pencereleri): `kimlik`, `enlem`, `boylam`, `analog_id`, `analog_km`
  (en yakın bilinen analog saha ve uzaklığı; etiket: < 20 km Known analog, 20–100 Near, > 100 New candidate — eşikler
  meta.ayar.analog_uzaklik_km), kapı değişkenleri `pv` (Pv ortancası), `kar_buz`, `egim_orani` (θ < 20° hücre oranı),
  `permafrost`, `kuraklik` (null = veri yok).
- `hedefler.json`: 26 hedef (kod\hedefler.csv sütunları) + `tam_analiz` + Artemis için `etiket` ve `koordinat_notu` (birebir).
- `liste/liste_<kimlik>.json`: Katman A (bütün E′, ön elemesiz), olduğu gibi. Her görev: `durum`, `ilk10` (kimlik, enlem, boylam,
  P, Q, s[8], d[8], kapsama, eksik_taraf[8], kapi_durumu, eps1/eps2 ve durumları, en_yakin_analog {id, km}), `sampiyonlar`[8],
  `duyarlilik`, `kapi_bilgi`; hedef bloğunda `kategori_var`[8].
- `analog.json`: tek liste, `tur` ∈ validation | mission_prep | candidate; `id` (adres analogs.html#<id>), `hedef_id`, `enlem`,
  `boylam`, `nasa_ne_yapti`, `kaynaklar[]`. validation: `ciftler[]` (sonuc: Pi, Pi_genel, P, s[8], kapidan_kaldi, gorev; yontem_ilk3).
  mission_prep: `kalite`, `harita_igne` (K1/K2 true, K3 false → haritada iğne yok). candidate: Katman A ilk 3'ünde en yakın bilinen
  analoğa > 100 km olan pencereler, `eslesmeler[]`.
- `ozet.json`: bütün sayılar (anahtarlar ve kaynak dosyaları `_kaynak`'ta). `V1.iyi` = V1 Fisher p < 0,05 → "The method finds
  known analogs" cümlesi yalnız bu true ise. V4 harita bitince eklenir.
