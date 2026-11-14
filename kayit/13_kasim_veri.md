# 13 Kasım — Veri günü raporu (D0–D3)

Orbitrary · NASA Space Apps 2026 · 13–14 Kasım gecesi · belge Bölüm 17.1–17.3
Hazırlayan: İrem (Claude yardımıyla). Bütün sayılar `kayit\` dosyalarından ve koşu çıktılarından.

## 1. Özet

| Adım | Sonuç |
|---|---|
| D0 ortam | conda `orbitrary` (conda-forge): Python 3.12, GDAL 3.13.3, rasterio 1.5.2, numpy 2.5.4, pandas 3.1.1, earthaccess 0.19.0, gudhi 3.13.0 → `kayit\ortam.json` |
| İndirme | 409 dosyadan 408. Ham 36,92 GB; zip'ler açılınca 42,79 GB. Üretici sağlaması olan her dosya tuttu. Eksik: R4 `nmsk2003.bin` (se.psi.edu iki denemede de açılmadı) |
| D1 bütünlük | 76/76 PASS |
| D2 Dünya | 18 PASS, 1 UYARI (ASTER en küçük yayınım 0,604; talimat 7) |
| D2 Ay | 14 PASS, 1 FAIL (PGDA kuzey soğuk/gölge örtüşmesi %88 < %90) |
| D2 Mars | 13/13 PASS (ilk koşuda R3 ve R5 etiketi okunamadı; okuma düzeltildi, eşik değişmedi) |
| D3 Dünya | 10/10 set PASS; `temiz\dunya` 22,55 GB |
| D3 Ay | 7/7 set PASS; `temiz\ay` 9,57 GB |
| D3 Mars | 7/7 set PASS; `temiz\mars` 1,09 GB |

D3 testi her sette: rastgele en az 1000 piksel/satırda ham dosyadan bağımsız yeniden hesaplanan değerle fark 0; NaN sayısı = veri-yok sayısı. Her klasörde `meta.json` (kaynak, DOI, sürüm, lisans, indirme tarihi, ham SHA-256, CRS, ölçek/ofset, veri-yok kuralı, D2 ve D3 testleri).

İlk koşularda kodun kendi kontrollerinin yakaladıkları (hepsi düzeltildi, kayıtta duruyor): E4 NDVI'de fill özniteliği yok; E9'da veri-yok tanımı yok; M1 ve M7'de ölçek TIF içinde de yazılı (etiketle aynı, bir kez uygulandı); M2 `AREA_GEO` birimi m² (km² değil).

## 2. MAKALEYİ ETKİLER — Emir ve Sude için

1. **R6 Mars Odyssey GRS (belge 10.3, 17.3 D1).** PDS bu seti 2026'da PDS4'e taşımış; 2013 tarihli MD5 listesi artık dosyalarla tutmuyor. Bütünlük PDS4 etiketleriyle doğrulandı (12/12). Veri sürümü 1.0; kayıt uzunluğu 72/66 bayt (eski PDS3 etiketinde 71/65). Yöntemde "PDS4 sürümü kullanıldı" denmeli.
2. **R4 Putzig TI interpolasyon maskesi (belge 13.3).** İndirilemedi. Açık kontrol açık kalıyor; Limitations'a bir cümle.
3. **E4 ASTER GED yayınımı (belge 10.1, 17.3 D2).** Ölçülen aralık 0,604–1,000 (belge 0,61 diyordu). Ofset dosyada 0,49; kuvars testi geçti. Talimat 7 gereği UYARI; makalede aralık 0,604–1,000.
4. **Diviner ↔ PGDA kalıcı gölge (belge 13.3, 17.3 D2).** En soğuk 100 PRP üçgeninin (|enlem| ≥ 85°) LPSR = 1'e düşme oranı güneyde %98, kuzeyde %88. Önceden konan %90 eşiği yüzünden kuzey FAIL; eşik değişmedi. Okuma hatası değil: aynı dönüşüm güneyde %98 veriyor ve belgedeki kuzey anormal pikseli (88,435°K 106,602°D) aynı formülle tam yerinde bulundu (LPSR 0,5, komşuları 0). Limitations'a bir cümle.
5. **E4 ASTER NDVI veri-yok kuralı (belge 10.1).** Dosyada veri-yok değeri tanımlı değil; ham 0–999, negatif yok; NDVI ofseti 0. Yayınımın 5 bandının da boş olduğu pikseller "veri yok" (ürünün kendi maskesi). Kara pikselinde NDVI 0 değer olarak kaldı ve bayraklandı (bitki yok ya da kırpılmış negatif). Bayrak sayısı ocakta ~4,0 milyon, temmuzda ~2,7 milyon (kuzey kışında kar/buz) — 0'ların gerçek "bitki yok" gibi davrandığını gösteriyor.
6. **E9 Global Aridity Index v3.1 veri-yok kuralı (belge 10.1).** Readme: değerler × 0,0001; veri-yok tanımlı değil. Okyanus 0 olarak saklanmış (ham 0'ın 550,9 milyonu su, 4,9 milyonu kara). Ham 0 ve MODIS su %100 → veri yok. Karadaki 0 (ör. Atacama) değer olarak kaldı, bayrak 1. 1,2 milyon pikselde uint16 tavanı 65535 (AI 6,5535), çoğu Grönland ve 40–60°G buz alanlarında → bayrak 2 "kırpılmış". Limitations'a bir cümle.

## 3. Belge 13.3 açık kontrollerin durumu

| Açık kontrol | Durum |
|---|---|
| TES bant 3/5/6 sırası | Kapandı: ASU ürün sayfasındaki liste = belge D11. Bant 8 (hematit) ekvator maksimumu Opportunity iniş noktasına 120 km (Meridiani) |
| PGDA kuzey soğuk/gölge oranı | Kapandı: kuzey 0,88, güney 0,98 (madde 4) |
| Putzig TI interpolasyon maskesi | Açık: dosya indirilemedi (madde 2) |
| GLiM pb sınıf kapsamı | Sude'de |

## 4. Talimat 6 ve 7

**Talimat 6 (PRP ice_depth).** Negatif değerler yalnız {−1, −999}; −1 olan bütün üçgenlerde temp_max ≤ 101,3 K (iki yarıda da en büyük 101,299 K). D2 ve D3'te aynı sayılar:

| | 0 | −1 | pozitif | −999 |
|---|---|---|---|---|
| Kuzey | 14 457 | 65 481 | 989 573 | 1 810 489 |
| Güney | 18 375 | 100 319 | 913 867 | 1 847 439 |

temiz'de: −999 → NaN + bayrak 1 (sansürlü, > 2,87 m); −1 değer olarak kalır + bayrak 2.

**Talimat 7 (ASTER ofseti).** `Offset` HDF5 özniteliğinde 0,49 (dosyadan, assert edildi). Kuvars testi PASS. En küçük yayınım 0,604 → UYARI, iş sürdü.

## 5. Okuma notları (iç; makaleye gerekmez)

- TES mineral ve DCI dosyalarında harita konumu yok; ASU ürün tanımından alındı (simple cylindrical, −180 → 180 doğu, 90 → −90). Hematit (Meridiani) ve DCI–albedo (r = −0,84) testleriyle doğrulandı. TES .envi (>f4) ile .isis (<f4) birebir aynı.
- TES TI temiz'de kuzey üstte, −180'den doğuya düzene çevrildi (ham: ilk satır güney, boylam batıya); dönüşüm 1000 noktada test edildi.
- M7 anormal piksel yalnız LPSR'de anormal; belge ürün belirtmediği için iki üründe de NaN yapıldı (AVGVISIB'de 1 piksel, değeri 0,280 / komşu ortancası 0,282).
- R1 MOLA: transform kullanılmaz; konum belgedeki satır/sütun kuralıyla (meta.json'da).
- E1 ETOPO'da veri-yok yok (0); E7/E8 permafrost 0–1; E10 kil 8–796 ‰, silt 3–900 ‰.

## 6. Dosyalar

- `kod\`: d0_ortam.py, liste_denetim.py, indir_hepsi.py, d1_butunluk.py, d2_dunya.py, d2_ay.py, d2_mars.py, d3_dunya.py, d3_ay.py, d3_mars.py, 13_kasim_veri.ipynb
- `kayit\`: ortam.json, rapor_sha256.txt, liste_denetim.json, indirme.csv, indirme_ozet.json, E1_karolar.csv, D1.json, D1_dosyalar.csv, D2.csv, D2_okuma_dunya/ay/mars.json, D3.csv, R6_inceleme.json, R6_satir_sonu.json, R6_karar.json, 13_kasim_log.txt, bu rapor
- `temiz\<govde>\<kod>_<ad>\` + `meta.json` (24 set). 14 Kasım kodu yalnız `temiz\`'i okur.

## 7. Dosyalardan sayım (2026-11-14 02:37)

| Gövde | D2 | D3 | temiz (GB) |
|---|---|---|---|
| dunya | PASS 18, UYARI 1 | PASS 27 | 22.55 |
| ay | FAIL 1, PASS 14 | PASS 41 | 9.57 |
| mars | PASS 13 | PASS 23 | 1.09 |

meta.json sayısı: 24 — ay/M1_lola, ay/M2_jeoloji, ay/M3_diviner_ghrm, ay/M4_diviner_prp_gcp, ay/M5_lp_grs, ay/M6_lp_hidrojen, ay/M7_pgda, dunya/E10_soilgrids, dunya/E1_etopo, dunya/E2_mcd12c1, dunya/E3_glim, dunya/E4_aster_ged, dunya/E5_myd11c3, dunya/E6_mcd43c3, dunya/E7_permafrost_kuzey, dunya/E8_permafrost_antarktika, dunya/E9_aridity, mars/R1_mola, mars/R2_sim3292, mars/R3_tes_mineral, mars/R4_tes_ti_albedo, mars/R5_tes_dci, mars/R6_odyssey_grs, mars/R7_swim
