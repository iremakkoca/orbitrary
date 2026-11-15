# MAKALEYİ ETKİLER — 14 Kasım 2026 (kod günü) toplu kayıt

Orbitrary · belge v1.2 (+ v1.2.1 talimatları). Kod yazılırken çıkan, makaleye giren her şey.
Kaynak: `kayit\degisiklik.md` (tarihli satırlar). Durum sütunu: **kaynaklı** = dış kaynağa dayanıyor; **onaylı** = ekip onayladı; **onay bekliyor** = proje kararı, dış kaynağı yok.

## 1. Parametre ve veri

| # | Ne değişti / netleşti | Belge bölümü | Durum | Makaleye not (Emir / Sude) |
|---|---|---|---|---|
| 1 | σv Ay = 10 m, Mars = 1 m (belgede değer yoktu; Dünya 7,17 m aynı) | 4.1, 8.4, T2 | kaynaklı: [105] Smith ve ark. 2010 "~10 m radial"; [104] Smith ve ark. 2001 "~1 m vertical" | T2'de σv = 7,17 / 10 / 1 m; Method'da iki kaynağa bu değerlerle atıf |
| 2 | MI geçerlilik aralığı [0,133; 7,5] = yayınım aralığından (0,604–1,000) türetilmiş matematiksel sınır | 6.4, 10.1 | onaylı (Sude) | ASTER en küçük yayınım 0,604 (belge 0,61 diyordu; talimat 7 UYARI) |
| 3 | I⊕ üst sınırı ≈ 82,1 = max C₁ (1,6426, ε = 23,44°) / 0,02 K | 6.5 | onaylı (Sude) | ölçülen en büyük 75,3 |

## 2. Yöntemin okunuşu (formül aynı, belgede tek anlama inmeyen yer netleşti)

| # | Karar | Belge bölümü | Durum | Makaleye not |
|---|---|---|---|---|
| 4 | P_f,B: "rastgele piksel" yerine alanca düzgün rastgele noktaların piksel değerleri (≤ 10⁶, tohum 20261113) | 5.2 | onaylı (Sude, 12:17) | "area-uniform random sample"; neden: enlem-boylam pikseli kutbu 1/cos φ ağırlıklandırır |
| 5 | Dünya Tmax = aylık gündüz LST'nin en büyüğü; T̄ = aylık (gündüz+gece)/2 yıllık ortalaması; Tgece = aylık gece yıllık ortalaması | 6.5 | onaylı (Sude, 12:17) | dayanak 6.5 "Aqua öğleden sonra geçişi maksimuma yakın" — veri MYD11C3 = Aqua (kaynak dosya MYD11C3.A2023…hdf; belge D1); Aqua ~13:30 / ~01:30 (NASA MODIS teknik sayfası). Sude'nin 'Terra ~10:30' düzeltmesi uygulanmadı: veri Terra değil |
| 6 | I⊕ aylık; C₁ = 0 ve ΔTg ≤ 0 ayları ortalamaya girmez (ΔTg ≤ 0 NaN, assert ve sayılar kayıtta) | 6.5 | ΔTg ≤ 0: onaylı (Sude); yıllık ortalama belgedeki gibi kalır | δ⊙: Michalsky 1988 (Astronomical Almanac düşük duyarlıklı algoritma) |
| 7 | ASTER MI her bandın 12 aylık ortalamasından; ortalamaya yalnız geçerli aylar (0 = yok → NaN) girer | 6.4 | onaylı (Sude, 12:17) | — |
| 8 | Ay aydınlanması: |φ| ≥ 65° PGDA ve < 65° Berger hücreleri kendi kapsamlarında ayrı sıralanır | 6.8 | onaylı (Sude, 12:17) | iki büyüklük farklı birimde; Limitations'a bir cümle |
| 9 | Sıfır kuralında kara hücresi = MCD12C1 kara payı ≥ 0,5 | 6.6 | onaylı, proje kararı (Sude, 12:17) | kar/buz < 0,5 ile aynı çoğunluk mantığı |
| 10 | Ay π⁺: hücrenin alt örneklerinin ≥ yarısında ice_depth ≠ −999 ise hücre pozitif | 6.6 | onaylı, proje kararı (Sude, 12:17) | — |

## 3. Test tanımı

| # | Ne | Belge bölümü | Not |
|---|---|---|---|
| 11 | "Halka ızgarası" testi: formül aralıkları her halkada 20 km ± %5; gerçek komşu uzaklığı kutup ilk halkası (m = 3, ~17,3 km) dışında ± %5; ≤ 5 km sapan tıklama kendi penceresi = en yakın merkez; her nokta kendi hücresine eşlenir, merkeze uzaklık hücre köşe uzaklığını aşmaz (kutup halka 0: 17,3 km, halka 1: 15,6 km, diğer ≤ 14,7 km); en yakın merkeze uzaklık < 15 km | 8.3, T5 | formülün en yakın merkezi verme oranı %96,2 (`kayit\izgara_bilgi.json`) |
| 12 | K12 kontrolü: belgedeki SW (1/π, yarım çember) = Carrière ve ark. (1/2π, S¹); sabit aynı, K12 tetiklenmedi, Ψ₂ değişmez | 6.2, 8.1, 11 | test: `test_sw_tek_nokta_analitik_ve_K12` |

## 4. Hedefler, jeoloji, doğrulama (Sude dönüşü)

| # | Ne | Belge bölümü | Not |
|---|---|---|---|
| 13 | R-UTO ikiye ayrıldı: R-UTO Viking 2 (47,64 / 134,29, NSSDCA), R-ZHU Zhurong (25,066 / 109,925, Liu ve ark. 2022) | 9.2 | iki iniş yeri ~1600 km uzak |
| 14 | R-OLY = IAU Gazetteer özellik merkezi; sitede "feature centre" | 9.2 | "zirve" denmez |
| 15 | R-JEZ belge değeri 18,44 / 77,45 kaldı (Wikipedia hassas değeri kullanılmadı) | 9.2 | kaynak: JPL basın kiti + belge |
| 16 | GLiM pb = gabro, norit, peridotit (Hartmann & Moosdorf 2012, Ek A4.1.4, para. [71]); anortozit geçmez; Ay → pb eşlemesi değişmez, gerekçe cümlesi düzeltildi | 6.3, 13.3 | açık kontrol kısmen kapandı |
| 17 | lApd (kutup kumulları), Hpe (kutup yapıları), Nhe (yayla yapıları) ön kayıtlı kurala göre gruplandı (DMU tanımından farklı) | 6.3, L12 | Limitations cümlesi |
| 18 | V1: 11 çiftin hepsi kaynakla tutuyor; JETT5 NTRS kimliği doğrulanamadı → makalede yalnız USGS kaynağıyla atıf; Dumont Dunes 11 Mayıs haber tarihi; JETT1 kesin tarih yok | 9.3 | onaylı (Sude) |

## 5. Implementation (yöntem aynı; makale Bölüm 8 için)

- Hücre ortalaması (4.4): hücreden ince katmanda hücre içinde s × s alt nokta (piksel kenarı başına ≥ 2, s ≤ 10) → alan ağırlıklı piksel ortalaması.
- Vektör jeoloji (4.4): her pencerede hücre başına 5 × 5 nokta, poligon içi testi (shapely, hazırlanmış poligon). GLiM rasterleştirilmedi.
- Topografya (6.1): "2 hücre dışarıdan" her ölçekte → DEM 8 ince hücre dışından okunur (2 km'de 2 blok).
- F⁻¹ (5.1): ECDF genelleştirilmiş tersi, k = ⌈n(2m − 1)/2M⌉ tam sayı aritmetiğiyle.
- SW doğrultuları orta nokta θ_j = −π/2 + (j − ½)π/Mθ.
- Diviner PRP hücreye: en yakın üçgen merkezi, ortanca komşu aralığının 3 katı eşik (proje kararı, onaylı Sude 12:17), arama eşikle sınırlı.
- H₀: GUDHI CubicalComplex; bağımsız union-find (8-komşuluk) ile 203 pencerede birebir aynı.
- Berger f(φ): 0,001° tablo + doğrusal ara değer (ölçülen en büyük hata 1,2e-9).

## 6. Bekleyen ölçüm (Sude Limitations cümlesini yazacak)

- I⊕: ΔTg < 1 K olan geçerli ayı bulunan piksel oranı 0,329 (2 913 886 / 8 638 888). I⊕ yüzdelikleri: %1 0,0112; %50 0,0541; %99 0,5152; %99,9 3,9962 (`kayit\iarti_teshis.json`).
- Ek ölçümler (en büyük ayın yıllık toplamdaki payı; |u_ort − u_ortanca|; en büyük farkın 10 pikseli) → `kayit\iarti_olcum.json`.

## 7. Son gönderimden sonra eklenenler (12:17'den itibaren)

| # | Ne | Belge bölümü | Durum | Not |
|---|---|---|---|---|
| 19 | Madde 5 "Terra ~10:30" düzeltmesi önerildi, uygulanmadı: veri MYD11C3 (Aqua, ~13:30 / ~01:30) | 6.5, D1 | Sude'ye bildirildi | Limitations'taki I⊕ cümlesinde Terra etkisi yazılmaz |
| 20 | K-1: kapılarda W° "kara hücresi" = kara payı ≥ 0,5 (madde 9 ile aynı) | 7.2 | onaylı, proje kararı (Sude) | — |
| 21 | K-2: Pv için 12 aylık ASTER NDVI → yıllık ortalama (geçerli aylar) → Pv; pencerede **ortanca** (belge 7.2 açıkça "medyan_{W°} P_v" diyor) | 7.2 | onaylı (Sude) | yıllık en büyük kullanılmaz (yağmur sonrası yeşeren çöller) |
| 22 | K-3: Geology kapısında kar/buz payı = W° üzerinde ortalama | 7.2 | onaylı (Sude) | alan payının beklenen değeri |
| 23 | K-4: hedefte verisi olmayan kategori iki taraftan da çıkar; "en fazla 1 eksik" yalnız hedefin verisi olan kategoriler üzerinden | 7.2 | onaylı (Sude) | — |
| 24 | K-5: X'in leave-one-out'u yalnız V1'in kendi Geology satırlarında; diğer hedeflerde X = 7 Geology çiftinin hepsiyle | 7.2, D7 | onaylı (Sude) | — |
| 25 | Gözlem: Ice kapısı (G_buz) yalnız permafrost ortalaması; kar/buz < 0,5 şartı yalnız Geology'de. Grönland/Antarktika içi (kar/buz ≥ 0,5 hücreleri sıfır kuralında hesap dışı) Ice'ta "could not be checked" ile geçer (belge 7.2 kural 2) | 7.2 | kayda yazıldı, değişiklik yok | sonuç tablosunda görünecek |

## 8. Açık sorular (onele / puan / teorem / dogrula) — 12:25 soruldu, 12:33 cevaplandı

Hepsi KAYNAK YOK — onay gerekir. Öneri İrem/Claude'un; karar ekibin.

| # | Soru | Belge | Öneri | Karar |
|---|---|---|---|---|
| Q-1 | z'de MAD = 0 ise | 7.1 | O bileşende Rousseeuw–Croux Qn [96]; Qn de 0 ise bileşen çıkar | **Değişti (Sude):** Qn kullanılmaz (Qn'nin de dayanma sınırı %50, aynı durumda 0 çıkar); MAD = 0 olan bileşen z'den çıkar, kayda yazılır. z yalnız ön elemede; kaybı V5 ölçer |
| Q-2 | Kategori şampiyonu hangi kümeden | 7.4 | E_K(T, g) içindeki uygun adaylar; k = 2 için son 30 aday | onaylı (Sude) |
| Q-3 | V2 "sınıf 2 ≥ %90" düzeyi | 8.3, D6 | Pencere ortalaması MCD12C1 sınıf payı ≥ %90 | onaylı (Sude) |
| Q-4 | V4/V5 "rastgele 200 hedef" cismi | 8.3 | 100 Ay + 100 Mars ızgara penceresi, tohum 20261113 (alt tohum V4/V5) | onaylı (Sude) |
| Q-5 | V5 tam sıralama topoloji dahil mi | 8.3, 7.4 | Topolojisiz (V1 gibi), iki taraf aynı puan | onaylı (Sude) |
| Q-6 | V7 gürültü nereye | 8.3 | Yalnız hedef + 20 komşusunun DEM'i; Dünya tarafı sabit; liste hedeflerinin hepsi | onaylı (Sude) |
| Q-7 | V6 "bütün (E, T) çiftleri" | 8.3 | Liste hedefleri × E_K adayları (8 s_k'nin hepsi olan) | onaylı (Sude) |
| Q-8 | ε* ikiye bölme hassasiyeti | 8.1 | 0,01 m; aralık σv'den başlayıp ikiye katlanır (≤ 10⁵ m) | onaylı (Sude); sınıra kadar bulunamazsa kayda "bulunamadı" |

## 9. Dış inceleme (12:33) — maddeler ve durumu

| # | Bulgu | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 26 | Makale v0.5'te "I⊕ = C₁/ΔT (MOD11C3 in v1.0)", "Aqua replaces Terra", "Replaces MOD11C3 (Terra) of v1.0" yazıyor; belge D1 ise bunu kaynakça hatası diyor. Bugünkü koşu MYD11C3 (testle doğrulandı). | D1, D12 | Hayır | Makaledeki sonuçlar v1.2 koşusundan gelecek; D12 gereği v1.0 karşılaştırma cümleleri makaleden çıkar (Emir/Sude) |
| 27 | Aqua gece geçişi 01:30, günlük minimum gün doğumuna yakın → ΔTg = T₁₃:₃₀ − T₀₁:₃₀ < T_max − T_min → I⊕ olduğundan büyük | 6.5 | Hayır | Limitations cümlesi sapmanın yönünü söyler (Sude) |
| 28 | Puan sıra tabanlı: her yerde aynı oranda sapma sırayı değiştirmez; etkiyi yalnız yerden yere değişen sapma yapar (tarama açısı, enlem, açık gün seçimi) | 5.2, 6.5 | Hayır | Limitations cümlesi "olduğundan büyük" yerine bunu söyler (Sude) |
| 29 | I⊕ yıllık değeri: oranların ortalaması (belge) küçük paydalı aylara duyarlı. **Karar (Sude, 12:57; D8'den önce, sonuçlara bakılmadan):** ortalamaların oranı, I⊕ = Σ C₁(1 − α) / Σ ΔTg, toplam C₁ > 0, ΔTg > 0 (ve α var) olan geçerli aylar üzerinden. Cebirsel olarak aylık I⊕'nin ΔTg ağırlıklı ortalaması; ΔTg ≈ 0 olan ay yıllık değeri ele geçiremez. MI'deki "önce ortalama" (madde 7) ile tutarlı | 6.5 | Evet: yalnız ozellik_diger yıllık I⊕ (`I_arti_yillik`) ve ara\cmg_iarti.npy yeniden üretildi; sınır (≤ 82,1) aynı | uygulandı; gerekçe büyüklüğü `kayit\iarti_olcum.json` (|u_eski − u_yeni|: ortanca, %95, en büyük); Sude gerekçe cümlesini yazdı (13:14): sıra farkı ortanca 0,021, %95 0,228 |
| 30 | Pv'de ortanca: Pv NDVI'nin azalmayan fonksiyonu → medyan Pv < 0,5 ⇔ medyan NDVI < 0,2 + 0,3√0,5 ≈ 0,412; belgedeki "NDVI < 0,41" cümlesi tam doğru | 7.2 | Hayır | Method'a gerekçe olarak (Emir) |
| 31 | Buz tabakası pencereleri Ice kapısından "could not be checked" geçer, s₆ tanımsız, ağırlık termal/aydınlanmaya kayar → Ay kutup hedeflerinde üst sıralara çıkabilir. Kavramsal soru: buz tabakası "donmuş zemin" mi? | 6.6, 7.2 | Şimdi hayır | Koşudan sonra Ice Top-3/ilk 10'da "could not be checked" oranı ozet.json'a otomatik yazılır; yorum ekip |
| 32 | Madde 8 (PGDA/Berger) gerekçesi: bu "cisim içi sıra"nın kendisi değil; Ay iki referansa bölünüyor, 65°'de süreksizlik (64,9° ve 65,1° çok farklı sıra alabilir) | 6.8 | Hayır | Limitations cümlesi süreksizliği açıkça söyler (Sude) |
| 33 | Sude'nin numaralandırması kayıttakiyle farklı ("6. MI" = madde 7, "7. aydınlanma" = 8, "8." = 9 ve 10) | — | Hayır | Bu belgede numaralar düzeltilmiş halde |

## 10. teorem.py (12:45)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 34 | Lemma 1 (a)–(e), Ψ₁, Ψ₂ ve Teorem 1 sayısal testten geçti (rastgele DEM + |e| ≤ ε; sınırlar her tekrarda tuttu; 0,9·ε* gürültüde s₁ sırası değişmedi). **Erken uyarı:** sentetik arazide ε*₁ ≈ 0,02–2 mm (σv = 7,17 m). Ψ₁'i H₄ terimi büyütüyor (IQR_T(H₄) ~1e-5). Gerçek dağılım D6/uzun koşuda (F15) | 8.1 | Hayır | Emir: "güvenli hata yarıçapı ölçülür ve raporlanır" cümlesini büyüklükten bağımsız doğru kalacak biçimde yazar; sayılar ozet.json'dan |
| 35 | ε* < 0,01 m (Q-8 hassasiyeti) ise kayda "0,01 m'den küçük" yazılır (0 yalnız gerçek eşitlikte) | 8.1, Q-8 | Hayır (kayıt biçimi) | — |

## 11. onele.py (12:55)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 36 | Q-1 uygulandı: MAD = 0 olan z bileşeni çıkar; hangi bileşenin çıktığı `ozet.json`'a yazılır. **Olası durum:** n↓ ve n↑ sayım; Dünya pencerelerinin yarısından fazlasında aynı değer (ör. 0) çıkarsa MAD = 0 olur ve bileşen düşer. Sonuç P4'te görülür | 7.1, Q-1 | Hayır (karar onaylı) | makalede "z'den çıkan bileşenler" cümlesi ozet.json'dan |
| 37 | Okuma (formül aynı): z'si eksik (NaN) Dünya penceresi KD-ağacına girmez, sayısı kayda yazılır. Bu yalnız DEM'i eksik pencerelerde olur; bunlar topoloji kategorisi olmadığı için zaten uygun değil (7.2). Aynı uzaklıkta pencere kimliği küçük olan önce | 7.1, 7.2 | Hayır | kayda yazıldı |
| 38 | **Q-9 (onaylı, proje kararı, Sude 12:51):** V5'te {100, 200, 400, 800} hiçbiri ortalama recall ≥ 0,9 sağlamazsa Kön = 800 (denenenlerin en büyüğü), koşu durmaz. Listeye yeni değer eklenmez (sonuçtan sonra ayarı genişletmek önceden kilitleme ilkesine aykırı) | 7.1, 8.3 V5 | onele.kon_sec → (K, eşik sağlandı mı) | makaleye "recall did not reach 0.9 (mean ± CI)" sınırlılığı; ozet.json'da bayrak |
| 39 | **Q-10 (onaylı, proje kararı, Sude 12:51):** şart ortalama recall'a (r̄) uygulanır. GA = r̄ ± 1,96 s_d/√200 (s_d örneklem std, ddof = 1) hesaplanır, ozet.json'a yazılır; r̄ ≥ 0,9 ama alt uç < 0,9 ise makalede tek cümleyle belirtilir | 8.3 V5 | onele.recall_ozet | — |
| 40 | Hedef penceresinin z'sinde (tutulan bileşende) NaN varsa ön eleme yapılmaz, hata verir (sessiz karar yok). Ay/Mars DEM'leri küresel tam olduğu için beklenmiyor; olursa pilotta görülür | 7.1 | Hayır | kayda yazıldı |

## 12. I⊕ formülü uygulaması (13:10)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 41 | **(1 − α) çarpanı kaldı.** Sude'nin notunda "21 sette Dünya albedosu yok, çarpan alınmayacak" deniyor; ama belge 6.5'teki formül I⊕ = C₁(1 − α)/ΔTg, veri tablosunda MCD43C3 beyaz gök albedo (E6, 2023'ün her ayının 15'i) var, set temiz\ altında (P0 24/24 PASS) ve kod 13 Kasım'dan beri çarpanı kullanıyor. Çarpanı atmak belgeden sapma olurdu. v1.0'daki seçim gerekçe olamaz (D12: eski sürümle karşılaştırma yok) | 6.5, 10.1 | Hayır (zaten öyleydi) | Sude'ye bildirildi; makalede formül belge 6.5'teki gibi (1 − α)'lı yazılır, albedo kaynağı [67] |
| 42 | Yalnız yıllık I⊕ değişti; Tmax, T̄, Tgece, MI dosyaları yeniden yazılmadı (değiştirilmedikleri kontrol edildi). I⊕'nin cisim içi sıra referansı (ara\ref_dunya_iarti.npy) silinip yeni değerden üretilir | 6.5, 5.2 | iç iş | — |

## 13. puan.py (13:25)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 43 | **Q-11 (onaylı, proje kararı, Sude 13:14; öneri değişti):** ζ_k'nın paydası (R_k uzaklıklarının ortancası) 0 ise d = 0 → **ζ = 1**, d > 0 → ζ = +∞. Payda 0 iken referansların yarıdan fazlası hedefe tam eşit uzaklıktadır; d = 0 olan pencere istisnai değil, tipik bir referans kadar yakındır (s_k'nin ½ eşitlik sayımıyla tutarlı). Paydası 0 olan aday sayısı kayda/ozet.json'a | 5.4, 7.4 | Evet: puan.zeta_k (uygulandı) | — |
| 44 | **Q-12 (onaylı, proje kararı, Sude 13:14):** 100 km kuralı sitedeki ilk 10 listesine de uygulanır; Top-3 = ilk 10'un ilk üçü | 7.4, 17.6 | Yalnız kos.py | — |
| 45 | **Q-13 (onaylı, proje kararı, Sude 13:14):** τb ana koşunun son 30 adayı üzerinden; alternatif şemada (eşit ağırlık, geometrik ortalama) aynı 30 aday yeniden puanlanır, iki sıralama aynı küme üzerinde karşılaştırılır. Top-3 Jaccard'da üç sıralamaya da 100 km kuralı | 7.4 | Yalnız kos.py | — |
| 46 | Okuma: eşitlik kırıcı zinciri P azalan → Q artan → **pencere kimliği artan** (belge 8.3 "tekrar koşuda aynı" şartı; Q de eşitse sıra yine deterministik) | 7.4, 8.3 | Hayır | kayda yazıldı |
| 47 | Okuma: "en az 100 km" ≥ 100 km (tam 100 km olan aday alınır) | 7.4 | Hayır | kayda yazıldı |
| 48 | Test tanımı: 8.2 "sıra biçimi N = 5, (1, 2, 2, 3, 4)" satırı formül sınaması; |R_k| < 100 → null kuralı bu testte devre dışı (en_az = 1), kural ayrı testte (8.3 "99 / 100") | 5.4, 8.2 | Hayır | T5 tablosunda not |
| 49 | Görev ağırlıkları belge 7.3 formülünden (0,80/m, 0,20/(n − m)) üretilir; tablo testle doğrulandı. kos.py çalışırken ayar.json'daki ağırlıklarla birebir aynı olduğunu assert eder | 7.3 | Hayır | — |
| 50 | puan.py sabitleri ayar.json'dan okunur ve belge 8.4 ile assert edilir: referans.en_kucuk 100, siralama.top3_en_az_km 100, topoloji.aday_sayisi 30, agirlik.ana_pay 0,8; ana kategoriler belge 7.3 tablosuyla testte karşılaştırıldı | 8.4, 7.3 | Hayır | — |

## 14. dogrula.py (13:40)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 51 | V1–V3, V6, V9 formülleri belge 8.3'teki gibi; H₀ altında (Π ~ U(0, 1)) Fisher p-değerinin düzgün dağıldığı 4000 tekrarlı testle doğrulandı. V1 kapıdan kalan analog Π = 0 (K14). V3 p-değeri tek yönlü Mann–Whitney [63] | 8.3 | Hayır | — |
| 52 | Okuma: V3 %95 GA = 2000 bootstrap, A ve B′ ayrı ayrı yerine koyarak yeniden örneklenir, yüzdelik yöntemi (Efron & Tibshirani [28]); alt tohum V3. B′ hedef başına ayrı rastgele akış | 8.3 V3 | Hayır | kayda yazıldı |
| 53 | Okuma: V2'de aynı pencere iki çiftte seçilmez (22 farklı pencere); alt tohum V2 | 8.3 V2, D6 | Hayır | kayda yazıldı |
| 54 | **Q-14 (onaylı, proje kararı, Sude 13:22):** ayar.json'a `alt_tohum.V4_hedef = 6` eklendi, D8'de kilitlenir; V4 ve V5'in 200 hedefi ayrı kümeler (Q-4'ün amacı) | 8.3 V4, Q-4 | ayar.json + kos.py | uygulandı |
| 55 | **Q-15 (onaylı, proje kararı, Sude 13:22):** rastgele 200 hedefte τb, E_K adaylarının R ve R′ ile iki topolojisiz sıralaması arasında; Katman A–B'de liste hedeflerinin son 30 adayı; Top-3 değişimi Jaccard ile. **Ek:** τb iki sıralamanın ortak aday kümesinde (E_K R'ye bağlıysa kesişim; kesişim boyutu kayda). ozet.json: 200 hedefin τb ortancası ve %5–%95 aralığı (K4 kuralı belgedeki gibi τ̄b ortalamasıyla) | 8.3 V4 | dogrula.tau_ortak, dogrula.v4_ozet | uygulandı |

## 15. D5 kuru koşu (14:03) ve K1 / K2

Ölçüm (`kayit\D5.json`; her cisimde 500 pencere, tek süreç, AMD Family 25 Model 97, Windows 11): Dünya E′ oranı örneklemde 0,264 → |E′| ≈ 336 727 (kesin sayı P2'den, ozet.json'a). Pencere başına P3 süresi: Dünya 0,097 s, Ay 0,224 s, Mars 0,061 s. Tek süreç tahmini: P2 Dünya 3,6 sa, P3 Dünya 9,1 sa, **Katman B'nin yalnız özellik kısmı (Ay + Mars) 12,1 sa** (Ay 5,9 sa, Mars 6,2 sa); puanlama süresi henüz eklenmedi. Disk tahmini 39,7 GB (boş 107,6 GB). Bütün pencerelerde DEM tam (dem_tam oranı 1,0).

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 56 | **K1 — karar (İrem, 14:19, proje sahibi):** Katman B (tıklama haritası, 3D küre) **Ay ve Mars'ın ikisinde de** yapılır; K1'in "yalnız Ay" seçeneği uygulanmaz. Katman A (bütün Ay ve Mars hedefleri, 8 kategori), V1 analog doğrulaması ve analog saha yorumları zaten hiçbir koşulda düşmez (17.5). D5 tek süreç ölçümü (özellik kısmı 12,1 sa) paralel işçilerle (4–6) karşılanır; sonuç tek süreçliyle aynı. Belge 11 K1'den sapma olduğu için makalede Implementation'da tek cümle: "Layer B was computed for both bodies using parallel workers (results identical to a single-process run)." | 3.2, 11 K1, 17.5 | Yalnız koşu düzeni | karar verildi; Emir/Sude bilgilendirilir |
| 57 | İç iş: P2/P3 paralel işçilerle (blok mod K); aynı fonksiyon, aynı bloklar, sonuç tek süreçliyle birebir aynı (testle) | 17.5 | Hayır | — |

## 16. Dünya özellikleri (P2–P3, 15:45) ve site metinleri

P2 + P3 Dünya bitti (5 işçi; P2 5 dk, P3 66 dk; toplam 73,3 dk). |E′| = 346 064 (Dünya 1 275 482 pencerenin %27,1'i). Kategori kapsaması (E′ içinde, 1000 noktanın hepsi dolu): topografya, termal (4 özellik), aydınlanma %100; jeoloji %99,99; mineraloji %99,96; su/buz %90,2 (kar/buz ≥ 0,5 buz tabakası hücreleri hesap dışı, belge 6.6); toz %90,3 (SoilGrids Antarktika'yı kapsamaz, belge 6.7). Bütün pencerelerde DEM tam. z bileşenlerinin hiçbirinde MAD = 0 çıkmadı (Q-1 tetiklenmedi): n↓ ortanca 2 (MAD 2), n↑ ortanca 5 (MAD 5). Kesin sayılar kayit\P3_dunya_ozet.json → ozet.json.

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 58 | **Ad kuralı:** makalede "Overall", "Ice & Resources", "dust and surface" geçiyor; belge 2.3'e göre adlar her yerde metin.json'daki gibi: General, Mobility test, Geology, Ice & resources, Astrobiology; Topography … Dust, Illumination | 2.3 | Hayır | Sude/Emir makaleyi metin.json adlarına çevirir |
| 59 | **Artemis etiketi:** makalede "Artemis candidate landing regions"; v1.2.1 madde 1'e göre etiket "Artemis III candidate regions (Oct 2024) — first landing now planned as Artemis IV" (makalede ilk geçişte bu, sonra "Artemis III candidate regions") | v1.2.1, 9.1 | Hayır | Sude/Emir |
| 60 | **Use of AI:** belge 2.3 beyan cümlesi üç parça ister: kod ve metin düzenlemesi Claude yardımıyla; problem yorumu, yöntem, eşik ve kararlar ekibe ait; çıktılar testlerle doğrulandı. Site, makale ve form aynı cümle | 2.3 | Hayır | Emir (metin.json about.use_of_ai) |
| 61 | Kapı durumlarında "requirement" kelimesi (Emir): sitede kapı başlığı "Mission requirement (gate)"; durum adları belgedeki gibi sabit | 2.3, 7.2 | Hayır | onaylı (İrem) |
| 62 | V1 kontrolü (Sude, 15:42): 11 çiftin kaynakları açıldı; tarih, ekip ve hedef belgeyle tutuyor, değişiklik gerekmiyor | 9.3, 15.1 | Hayır | kapandı |

## 17. kos.py 2. parça (P4–P6, D6 pilot) — 16:30

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 63 | **Q-17 (Claude kararı, 17:20; İrem'in 16:14 talimatıyla):** Liste hedefinin penceresi T **hedef koordinatına ortalanır**; N(T) = T + en yakın 20 ızgara penceresi. Dayanak: belge 9 hedefleri kaynaklı koordinatlarla verir (ör. Artemis: aday iniş noktalarının ortalaması, Wueller ve ark. 2026); ızgara penceresine kaydırmak hedefi 10–15 km yerinden oynatır (Malapert: 14 km) ve kaynaklı koordinatı bozar. Lambert pencere tanımı (4.3) merkezi serbest bırakır, yani koordinata ortalamak formülü değiştirmez. Katman B'de (tıklama) T zaten ızgara penceresidir | 4.2, 4.3, 9 | Evet (kos.HEDEF_MERKEZ = "koordinat") | karara bağlandı; makalede 4.2'ye bir cümle |
| 64 | Okuma: Genel görevde kapı yok (G ≡ 1, belge 7.2 kural 4); sitede kapı durumu "not applicable" | 7.2 | Hayır | kayda yazıldı |
| 65 | Okuma: R(1) = 2000, R(2) = R(8) = 200 tek permütasyondan (alt tohum R_orneklem): R(2) ve R(8) aynı örnek (belge 5.4 "aydınlanma aynı örneği kullanır"), R(1)'in ilk 200'ü | 5.4 | Hayır | kayda yazıldı |
| 66 | Pilot (D6) Kön = 800 (adayların en büyüğü; V5 henüz koşmadı). Uzun koşu V5'in seçtiği Kön ile | 7.1, 17.5 | Hayır | — |
| 67 | Teorem uygulaması: Ψ₁ ve Ψ₂'de ℓ ve ℓ^top her pencerenin kendi cisminin σv'siyle (Dünya penceresi 7,17 m; Ay hedefi 10 m; Mars 1 m). Belge 8.1 tek σv yazıyor; iki cisimli çiftte her pencere kendi R tabanını kendi σv'siyle aldığı için (6.1, 6.2) ℓ de öyle | 8.1 | Hayır (formül aynı) | Emir'e bilgi: ispattaki ℓ_A, ℓ_B tanımı pencere başına |

## 18. D6 pilot (16:28) — Jezero, Apollo 15, A3-03 Malapert

Pilot uçtan uca çalıştı (2,5 dk; hedef başına 5 görev 13–15 s). JSON alanları belge 17.6 şemasıyla uyumlu; her kategori sayı ya da nedenli null (Jezero'da su/buz null, neden "hedef": π⁺ = 0, kuru hedef → Ice "not applicable", belge 6.6).

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 68 | **K7 tetiklendi: X = 0.** V1 Geology çiftlerinden üçünde (2 Ries→Apollo 14, 9 Rio Grande Gorge→Apollo 16, 10 Lunar Crater VF→Apollo 17) Dünya sahasında hedefin baskın kayaç grubunun payı 0 (paylar: çift 1 0,526; 2 0; 3 0,226; 4 0,226; 8 0,613; 9 0; 10 0). Önceden yazılmış kural: "X = 0 çıkarsa kayaç payı koşulu fiilen kapalıdır ve bu yazılır" (belge 7.2, 11.1 K7). Geology kapısı bitki örtüsü ve kar/buz koşullarıyla çalışır | 7.2, 11.1 K7 | Hayır (kural) | Makale ve site Geology kapı metni: "rock-share condition effectively disabled (X = 0, pre-registered rule K7)"; sayılar ozet.json |
| 69 | **ε* bulgusu (madde 34 doğrulandı):** pilotta ilk 10'daki bütün adaylarda ε*₁ ve ε*₂ < 0,01 m ("hassasiyetten küçük"). Neden: Ψ₁'deki eğrilik terimi Λ_H,s'nin sabit kısmı 9/(2δ_s²), IQR_T(H) çok küçük olduğu için (500 m'de ortalama eğrilik dağılımı dar) ε başına çok büyür; referans uzaklıkları arasındaki boşluklar (~1/2000) bundan küçük kalır. Teorem doğru (testler geçti), ama verdiği sınır bu veride pratikte bilgi vermiyor; belge 8.1 sınır (i) bunu ε*₂ için zaten söylüyor, ε*₁ için de geçerli. **Yöntem değişmez.** Makalede "güvenli hata yarıçapı" sonucu dürüstçe "ε* < 1 cm for all top-10 candidates; the worst-case bound is uninformative at DEM noise level, robustness is shown empirically by V7" diye yazılır; 13.1'deki "matematiksel garanti" güçlü yanı bu cümleyle yumuşatılır | 8.1, 13.1 | Hayır | **Emir/Sude için önemli**: teorem bölümü ve güçlü yanlar cümlesi buna göre; F15 (ε*₁ dağılımı) yine üretilir |
| 70 | İç iş: bütün E′ için H₀ diyagramları önbelleğe alınır (belge 7.1 "diyagramlar önceden hesaplanıp saklanır"); her diyagramın n↓, n↑ sayısı P3'teki z ile birebir assert edilir | 7.1 | Hayır | — |

## 19. D7 kimlik testi ve V5 (17:30)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 71 | **D7 okuması (matematik aynı):** belge 17.5 "her s_k = 1" der. s_k tanımı (5.4) eşit uzaklıktaki referansa ½ sayar; hedefe uzaklığı tam 0 olan başka bir referans varsa (ör. iki pencerede de kayaç dağılımı %100 aynı grup → TV = 0) s_k = 1 − ½·n₀/|R_k| olur, 1 değil. D7 bu yüzden şunu sınar: pencere ilk sırada; hesaplanabilen her k'da d_k(T, T) = 0; s_k tanımla birebir. n₀ > 0 olan kategoriler D7.json'a yazılır. Tanımı değiştirmeden testin amacını (hat kendi penceresini tanıyor mu) tam karşılar | 5.4, 17.5 | Hayır | kayda yazıldı |
| 72 | D7 hedefleri: V1'in 8 farklı Dünya sahasının E′ penceresi (yeni tohum gerekmez), görev genel, Kön = 800. Ek kontrol: hedef özellikleri DEM'den yeniden hesaplanır ve P2/P3 kaydıyla karşılaştırılır (rtol 1e-5). Dünya penceresi için π⁺ tanımlı değil (6.6 Ay/Mars içindir) → su/buz kategorisi hedefte null; D7 bunu "hedefte yok" diye bekler | 6.6, 17.5 | Hayır | kayda yazıldı |
| 73 | **V5 okuması:** "Top-3_{E′}(T)" belge 7.4'teki Top-3 tanımıyla (sıralama + 100 km aralık kuralı, Q-12) bütün E′ üzerinde; görev genel (7.1 "görev seçilmemişse E′_g = E′"); Q-5 gereği topolojisiz, iki taraf aynı puan. Tam sıralama ve Katman A aynı puan fonksiyonunu kullanır (kos.skor_topolojisiz); bir pencerenin s_k'si aday kümesinden bağımsız olduğu testle gösterildi. E_K'lar iç içe olduğu için 4 Kön değeri tek sorguyla ölçülür | 7.1, 7.4, 8.3 | Hayır | kayda yazıldı; ozet.json: r̄, GA, Kön, eşik bayrağı |

## 20. Katman B hedef tarafı (17:55)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 74 | D7 sonucu (17:45): 8 sahanın 8'i PASS; her sahada pencere ilk sırada, yeniden hesaplanan özellikler kayıtla birebir aynı (en büyük fark 0). 7 hesaplanabilir kategoriden 6'sında s = 1 (sahaların ikisinde 7/7); kalanı madde 71'deki ½ eşitlik kuralı (sayılar sonuc\dogrulama\D7.json) | 17.5 | Hayır | PASS |
| 75 | İç iş: Ay ve Mars'ın bütün ızgara pencerelerinin özellikleri (P3B) Katman A'daki hedef hesabıyla aynı fonksiyonla (p3_blok) hesaplanır; IQR_T için 6 topografya alanının ham değerleri ve topoloji için diyagramlar da saklanır, böylece Katman B'de IQR_T ve d₂ Katman A ile aynı formülle (yaklaşıksız) bulunur | 3.2, 6.1, 6.2 | Hayır | — |
| 76 | Katman B puanlaması Katman A ile **aynı fonksiyonlarla** (skor_topolojisiz, topoloji_ve_sira, aralikli_liste) yapılır; tek fark belge 3.2'deki: kategori 3–7 referansı E′'den sabit rastgele 2000 pencere (alt tohum katman_B_R), kategori 1, 2, 8 referansı Katman A ile aynı. Yalnız aday ve referans satırlarının uzaklığı hesaplanır; bunun tam (bütün E′) hesapla birebir aynı Top-3 ve s_k verdiği testle gösterildi | 3.2, 5.4 | Hayır | — |
| 77 | Katman B çıktısı (belge 3.2): her pencere ve 5 görev için Top-3 (≥ 100 km kuralıyla), P, sekiz s_k, kapsama, eksik veri tarafı (hedef / Dünya / iki taraf). Kuru pencerede Ice "not applicable" (6.6). X, Katman A'daki gibi 7 Geology çiftinin hepsiyle (K-5) | 3.2, 7.2 | Hayır | site Explore "fast mode" etiketi (belge 3.2) |
| 78 | Okuma: jeoloji verisi olmayan bir Ay/Mars penceresinde baskın kayaç grubu c*(T) tanımsızdır; Geology kapısının kayaç payı koşulu o pencerede "could not be checked" sayılır (belge 7.2 kural 2: verisi olmayan koşul 1 sayılır ve işaretlenir). X = 0 olduğu için (K7) bu koşul zaten fiilen kapalı; sonuç değişmez | 7.2 | Hayır | kayda yazıldı |

## 21. V5 sonucu (19:50) — önemli

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 79 | **V5: ön elemenin kaybı çok büyük.** 200 rastgele hedefte (100 Ay + 100 Mars) ortalama recall: Kön = 100 → 0,005; 200 → 0,005; 400 → 0,008; 800 → 0,013 (%95 GA 0,004–0,022). Hiçbiri 0,9'a ulaşmadı → **önceden yazılmış K3 / Q-9 kuralı: Kön = 800**, ölçülen recall sınırlılık olarak yazılır. Yani bütün E′ üzerinde (topolojisiz, Genel ağırlık) en yüksek P'yi alan 3 pencere, z uzayında en yakın 800 pencerenin içine çoğunlukla düşmüyor (rastgele seçimde beklenen 800/346 064 ≈ 0,002; ölçülen bunun yaklaşık 6 katı). **Neden (belge 7.1 "Sınırlar" bunu önceden yazıyor):** z yalnız arazi şeklinden (eğim, pürüzlülük, rölyef, çukur/tepe sayısı) gelir; Genel puanın 8 kategorisinden yalnız 1–2'siyle ilgilidir. Tam sıralamanın tepesini jeoloji, termal, aydınlanma gibi kategoriler belirliyor. **Ne değişmez:** formüller, kapılar, ağırlıklar; V1–V3 doğrulaması (belge 8.3: doğrulama puanı E_K değil bütün E′ üzerinde) → analog saha doğrulaması bu bulgudan etkilenmez. **Ne değişir (anlatım):** Katman A ve B'nin Top-3'ü "Dünya'nın tamamındaki en yüksek P" değil, "arazi şekli en benzer 800 Dünya penceresi içinde en yüksek P"dir. Makalede ve sitede "Earth's land surface is scanned" cümlesi bu iki aşamayla yazılmalı: "terrain-shape prefilter (800 nearest windows), then full eight-category score" | 7.1, 8.3 V5, 11.1 K3 | Hayır (kural önceden yazılı) | **Emir/Sude için önemli:** Method + Limitations + site Method kartı; recall sayıları ozet.json'dan. Takım isterse (ek, değiştirmez): 26 liste hedefi için bütün E′ üzerindeki topolojisiz Top-3 ayrıca raporlanabilir (V5 ile aynı kod, ~15 dk) |
| 80 | **Ön elemenin puan kaybı (20:30, `python kos.py kayip`, sonuc\dogrulama\V5_kayip.json):** V5'in 25 Ay + 25 Mars hedefinde, Kön = 800, topolojisiz P. Fark ortancası (P_tüm − P_ön): genel 0,040 · mobility 0,014 · geology 0,029 · ice 0,060 (n = 6 ıslak hedef) · astro 0,062 (en kötü %5'te 0,37). Π_ön ortancası (belge 8.3 Π tanımı, bütün E′, kapıdan kalan P = 0): 0,99986 · 0,99997 · 0,99991 · 0,99995 · 0,99996. **Ekip eşiği (Sude, tablodan önce; kaynak yok, proje kararı): fark ortancası ≤ 0,02 ve Π_ön ≥ 0,99 → yalnız mobility sağladı.** Eşik değiştirilmedi. Sude'nin Plan B'si (ön elemeyi s₃…s₈ tam + s₁ kaba ile bütün E′ üzerinde yapmak) ölçülen süreyle sığmadı: kategori 3–8 bütün E′'ye hedef başına ~8,9 s (aynı koşu: 50 hedef 7,4 dk) → Katman B'nin 455 518 noktası tek süreçte ~47 gün, 6 işçiyle ~8 gün. Sude'nin önceden yazdığı kural gereği **Plan C: Katman B fast mode** (mevcut ön eleme, Kön = 800) | 7.1, 3.2, 11 K1/K3 | Hayır | **Makale (Emir/Sude):** Method + Limitations: "pre-set threshold 0.02 met for 1 of 5 missions; measured gaps …; in a typical point the shown site scores above X% of E′" (sayılar ozet.json'dan). Plan B → Future work. Π_ön harita noktalarında tek tek hesaplanamaz (her nokta için bütün E′ taraması gerekir); sitede örneklem istatistiği olarak verilir |
| 81 | **Karar (İrem + ekip, 20:48): Katman A (26 liste hedefi) ön elemesiz, bütün E′ üzerinde.** Belge 11 K3'ten sapma (K3: Kön = 800). Gerekçe: ön eleme belge 7.1'de yalnız hız için; 26 hedefte bütün E′ taraması ölçülen süreyle mümkün (V5: hedef başına ~25 s); ana formül 3.1 P_g'yi her E için tanımlar. Kapı yine önce uygulanır (kapıdan geçen bütün E′ aday); topoloji tam sıralamanın ilk 30'unda; formül, eşik, ağırlık değişmez. Kön = 800 yalnız Katman B'de. JSON'da `parametre.K_on = "tam (bütün E′, ön elemesiz)"` | 7.1, 11 K3, 3.1 | Evet (kos.puanla Kön = None) | Makalede tek cümle: "List targets are scored against all of E′; the terrain prefilter (Kön = 800) is used only for the map layer." |
| 82 | İç iş (21:40): Katman B hızlandırması, sonuç değişmez — d₁ özellik özellik hesaplanır (ozellik_topo.d1 ile bayt bayt aynı, testli; ~3 kat hızlı), Dünya diyagramları tek memmap dosyada (blok deposuyla her pencerede birebir aynı, dönüştürmede denetlenir), sliced Wasserstein doğrultuları önbellekte (aynı dizi). Profil: 30 Mars noktasında zamanın %63'ü uzaklıklar (d₁ %26), %26'sı topoloji (diyagram okuma %15) | 3.2 | Hayır | — |
| 83 | **Karar (İrem, 21:12):** 0,02 / 0,99 eşiği kullanılmaz (hiçbir dosyaya kilitlenmemişti, D8'de yok). Makalede ölçülen değerler eşiksiz verilir: Π_ön ve fark ortancası, en kötü %5 (madde 80) | — | Hayır | Emir/Sude: Limitations'ta eşik cümlesi yok, ölçülen sayılar var |
| 84 | **Harita (Katman B) uzaklıkları 32 bit** (21:55; Görev Yöneticisi: CPU sınırı, disk %1). Dünya ve hedef dağılımları diskte zaten 32 bit; yalnız uzaklık aritmetiği 64'ten 32 bite indi. Sentetik testte Top-3 64 bitle birebir aynı, s farkı < 1e-5. Ay'ın ilk ~90 bloğu 64 bitle hesaplandı, kalanı 32 bit. Katman A (26 hedef) ve doğrulama 64 bit kalır. Ayrıca 11 işçi | 3.2 | Evet (yalnız Katman B) | Implementation'a tek cümle: "The map layer computes distances in single precision (differences < 1e-5 in s_k in tests)"; V4 (A–B farkı) bunu da kapsar |
| 85 | **Karar (İrem, 22:15): V7 (gürültü testi) bu sürümde koşulmadı** (26 hedef × 20 tekrar ≈ 3–4 sa; işlemci haritaya ayrıldı). Sonuç: DEM hatasına dayanıklılık iddiası için kanıt yok (ε* bilgi vermedi, madde 69). **Makalede "robust to DEM noise" cümlesi yazılmaz**; Limitations: "the noise-stability test (V7) was not run in this version" | 8.3 V7, 13.1 | Hayır | **Emir/Sude:** teorem bölümü + Limitations |
| 86 | Okumalar (P8): V1–V3 puanı bütün E′ üzerinde, topolojisiz (belge 4.1 tablosu, Q-5); V1 her çift kendi göreviyle + Genel; Geology çiftlerinde X leave-one-out (K-5); ilk-çift tekrarı her sahanın en küçük cift_no'lu çiftiyle (8 çift); V9 = V1'in kategori başına Fisher p-değerleri (topoloji hariç 7) + Holm. V6 (Q-7 uyarlaması): Katman A ön elemesiz olduğu için "E_K adayları" yerine 26 hedefin 5 görevdeki ilk 10 adayı (8 s'nin hepsi olan; topoloji dahil). V8: her hedef ve görevde kapıdan + uygunluktan geçen bütün E′, topolojisiz P; kategori k çıkarılınca τb. V4 (Katman A–B) harita bitince; V10 için Lambert & Reimold tablosu dosyada yok → açık | 8.3 | Hayır | kayda yazıldı; sayılar sonuc\dogrulama\dogrulama.json → ozet.json |

## 22. Doğrulama sonuçları (22:54) ve site verisi

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 87 | **V1–V3, V6 sonuçları** (sonuc\dogrulama\dogrulama.json → ozet.json): V1 kendi görevi Fisher p = 0,044, Π ortancası 0,756, 11 çiftin 3'ü kapıdan kaldı (Ries → Apollo 14; Sudbury → Apollo 16 ve 17; hepsi Geology, bitki örtüsü kapısı Pv < 0,5); ilk-çift (8) p = 0,041; Genel p = 0,015 (Π ortancası 0,794). V2 (22 negatif kontrol) p ≈ 1,9·10⁻⁴⁴, Π ortancası 0 (çoğu kapıdan elenir). V3 AUC 0,68, Mann–Whitney p = 0,016, bootstrap %95 GA 0,49–0,86 (alt uç 0,5'in altında; 11 analog az). V6: |r_S| > 0,8 çift yok → K5 tetiklenmedi. **"The method finds known analogs" ölçütü:** V1 p < α₀ = 0,05 (belge 8.3) → ozet.json `V1.iyi`. Önerilen cümle (yumuşak): "Known NASA training sites rank above chance (Fisher p = …); the median site scores higher than …% of Earth windows" | 8.3, v1.2.1 madde 4 | Hayır | **Emir/Sude:** Validation bölümü; Ries/Sudbury: "excluded by the Geology vegetation gate (Pv ≥ 0.5); belge 7.1 bitki örtüsünü maskede tutmamayı seçmişti ama Geology kapısı onları dışarıda bırakır" → Limitations'a tek cümle. Sitede başarısızlık cümlesi yok; kapı durumu nötr ("did not pass — vegetation cover") |
| 88 | İç iş: site verisi `python kos.py site_veri` → sonuc\site\ (biçim kayit\SITE_VERI_NOTU.md). Halka dosyaları (Ay 273, Mars 532 halka), Dünya pencere tablosu, hedefler, Katman A dosyaları, analog.json (validation / mission_prep / candidate; candidate = Katman A ilk 3'ünde en yakın bilinen analoğa > 100 km), ozet.json, meta.json (JS hucreBul için 10 test noktası) | 17.6 | Hayır | site sohbetine SITE_VERI_NOTU.md |
