# Orbitrary v1.2 — Veri indirme ve analog raporu (Bölüm 16 + B eki)

Hazırlayan: Zeynep Zelal Bilgeç (Claude yardımıyla) · 13 Kasım 2026
**Sürüm: indirme_raporu3.md (13 Kasım 2026, 21:00).** Bu dosya `indirme_raporu.md` ve `indirme_raporu2.md`'nin yerine geçer; eskileri yeni Project'e yüklemeyin. Proje belgesiyle birlikte kullanılır: **v1.2 belgesi (v1.2.1 güncellemesi işlenmiş hâli) + indirme_raporu3.md** (+ SITE_TASARIM_VE_DERSLER.md). Belgede "Zeynep'in indirme raporu (Bölüm 16)" diye geçen dosya budur.

Kullanım: Bu dosya `kod\indir_hepsi.py` için girdidir. Her set için bir blok vardır (şablon: Bölüm 16.1) ve her blok kendi başına yeterlidir. Sıra: Dünya E1–E10, Ay M1–M7, Mars R1–R7, sonra Bölüm 16.3'teki 5 ek bölüm, en sonda **B. Ultimate veri ve analog eki** (üç sorunun cevabı, site analog düzeni, doğrulama ve gelecek görev analogları, Artemis bölge koordinatları, puana girmeyen ek setler X1–X6, 24 setin işlenmesi, kaynaklar, eksikler). B ekindeki her şey öneridir ve puana girmez.

Nasıl doğrulandı: Her adres 13 Kasım 2026'da tarayıcıda açıldı. Klasör listeleri, HEAD istekleri (Content-Length), kısmi indirme (Range) istekleri, üreticinin md5/sha256 dosyaları, PDS etiketleri, zip dosyalarının merkezi dizinleri ve Earthdata için CMR araması bu sırada okundu. Hiçbir adres tahminle yazılmadı. Doğrulanamayan her alan "doğrulanmadı" diye işaretlidir.

## İrem'in dikkatine: belgeden farklı çıkanlar ve doğrulanamayanlar

Belgeden farklı ya da belgede olmayan bulgular:
1. **E1 ETOPO:** Belgedeki "surface" sürümü NOAA'da "Ice Surface" adını taşıyor (`_surface.tif`). Bedrock (`_bed`) klasörü karıştırılmamalı. Üretici checksum yayınlamıyor.
2. **E4 ASTER GED:** Dosyalar HDF5 (.h5) biçiminde. Ürün sayfası Emissivity için Offset'i "N/A" gösteriyor, belgede 0,49 yazıyor → offset dosyanın özniteliğinden okunup assert edilmeli.
3. **E6 MCD43C3:** Tek günlük tarih araması 16 granül döndürüyor. Granüller adla seçilmeli (`A2023{DDD}`). 12 tarihin 12'si de mevcut.
4. **E7/E8 Permafrost:** İki zip de Deflate (8) ile sıkıştırılmış, Deflate64 değil. E7'nin lisansı CC-BY-3.0, E8'inki CC-BY-4.0.
5. **M1 LOLA:** Dosya BigTIFF biçiminde. planetarymaps.usgs.gov adresi Amazon S3'e yönleniyor ve S3 HEAD isteğine boyut veriyor. Üreticinin `.md5` dosyası var.
6. **M2 Ay jeolojisi:** Zip içindeki yolun başında `Unified_Geologic_Map_of_the_Moon_GIS/` klasörü var.
7. **M4 Diviner PRP:** Etikete göre `ice_depth` = 0 "buz yüzeyde kararlı" demek, −999 ise sansürlü değer. Belgedeki −1 değeri etikette tanımlı değil. GCP uzun biçimli bir tablo; yerel saat `ltim` sütununda (0,25 saatlik dilimin ortası).
8. **M6 LP hidrojen:** Dosya ızgara değil, 259 200 satır × 5 sütunluk uzun bir tablo. Bozuk hücre ve 4 180 negatif hücre dosya baştan sona okunarak doğrulandı.
9. **M7 PGDA:** `_COG.TIF` değil düz `.TIF` alınmalı. Sayfadaki iki yanlış LPSR bağlantısı doğrulandı. Dosyalar BigTIFF.
10. **R2 SIM 3292:** Sunucu HEAD isteğine boyut veriyor (808 910 442 bayt). Zip içindeki yolun başında `SIM3292_MarsGlobalGeologicGIS_20M/` klasörü var. 44 birim doğrulandı.
11. **R3 TES mineral:** Sayfanın genel metni ENVI dosyalarını "16-bit" diye anlatıyor, ama bu dosyanın kendi `.hdr`'si float32 big-endian diyor → `.hdr` esas alınmalı. Bant sırası (3, 5, 6, 8, 12, 13) sayfadan doğrulandı.
12. **R4 TI/albedo:** Maske dosyasının adı `nmsk2003.bin` ve se.psi.edu'da duruyor. TI dosyasının big-endian olduğu doğrulandı. Albedo little-endian; boylam düzeni de TI'den farklı.
13. **R6 Odyssey GRS:** MD5 dosyasının adı `odgm_xxxx_130911.md5`. Veri yolunun başında `odgm_xxxx/` klasörü var.
14. **R7 SWIM:** Dosyalar GeoTIFF; GDAL_NODATA = "-30" olarak doğrulandı.

İkinci denemede çözülenler:
- **E9:** Zip içindeki dosyanın adı `ai_v31_yr.tif`. Zip'te ayrıca `__MACOSX/` klasörü var; buradaki `._` ile başlayan dosyalar atlanmalı.
- **E10:** Silt kaydının DOI'si bulundu: 10.17027/isric-soilgrids/08a4990c-ca15-4871-8d12-ea21dae6b354.
- **R4:** Maske boyutu, PSI sayfasındaki biçim tanımından hesaplandı: 25 927 200 bayt. Sunucudan ölçülemedi.

Üçüncü denemede çözülenler:
- **R5 TES DCI:** Tam adres sayfanın Internet Archive kopyasından okundu (`~ruff/DCI/` klasörü). Boyut 66 356 224 bayt, etiket PC_REAL. Arşivdeki kopya yedek adres olarak eklendi.
- **E3 GLiM:** Boyut yaklaşık 1,14 GB (GLiM'i kullanan açık bir projeden). Katman ve sütun adları belgeyle aynı.

Kalan tek açık nokta: **E3 GLiM'in bayt düzeyinde kesin boyutu** (E3 bloğunun "Bilinen sorun" satırının sonunda "EKSİK — İrem için yapılacak" kısmı var). Dropbox bu ağdan açılmıyor ve Internet Archive'da da yok. İndirme kodu zaten boyutu indirmeden sonra kaydedip zip CRC'si ile doğruluyor, yani indirmeyi engellemiyor.

## Dünya

### E1 — ETOPO 2022 15" surface
- Sayfa (DOI / ürün sayfası): doi:10.25921/fd45-gt74 · https://www.ncei.noaa.gov/products/etopo-global-relief-model
- Dosyalar: klasör listesi https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/15s/15s_surface_elev_gtif/ · 288 dosya · ad kalıbı `ETOPO_2022_v1_15s_{N|S}{YY}{E|W}{XXX}_surface.tif` (YY/XXX = karonun üst-sol köşesi; ör. `ETOPO_2022_v1_15s_N00E000_surface.tif`, `..._S75W180_surface.tif`). Tam adres = klasör adresi + dosya adı. Klasörde .tif dışında dosya yok.
- Erişim: doğrudan https (klasör listesi)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: 288 dosya toplamı 5 230 677 335 bayt (≈ 5,23 GB; HEAD Content-Length ile 13 Kasım'da tek tek ölçüldü). En küçük N90E120 = 2 164 292 bayt, en büyük N00W075 = 37 227 671 bayt; örnek N00E000 = 16 434 942 bayt. NOAA sunucusu HEAD isteğine boyut veriyor → her dosyanın beklenen boyutu indirmeden önce HEAD ile alınabilir.
- Sağlama: yok (yalnız boyut). Klasörde ve üst klasörlerde (15s/, data/) md5/sha dosyası yok.
- Kullanılacak katman/bant/değişken: tek bant, yükseklik (m, EGM2008 geoit, EPSG:4326). "Ice Surface" sürümü = `_surface`. `_bed` (Bedrock), `_sid`, `_geoid` klasörleri İNDİRİLMEZ.
- Bilinen sorun: NOAA sayfalarında bu sürümün adı "Ice Surface"; aynı yerde "Bedrock" (`15s_bed_elev_gtif/`) klasörü de var, karıştırılmamalı. Karo adı üst-sol köşedir: `N00E000` karosu enlemde 0° → 15°G, boylamda 0° → 15°D aralığını kapsar; `N90…` en kuzey sıra (90°K → 75°K), `S75…` en güney sıra (75°G → 90°G). nodata ve veri tipi (−99999, float32) Bölüm 10.1'e göre dosyadan assert edilir. Lisans: CC0 1.0 (data.gov kaydı). Atıf: "NOAA National Centers for Environmental Information. 2022: ETOPO 2022 15 Arc-Second Global Relief Model. NOAA National Centers for Environmental Information. DOI: 10.25921/fd45-gt74. Accessed [date]."
- Doğrulandı: evet (13 Kasım 2026, 15:50; klasör listesi + 288 HEAD isteği)

### E2 — MODIS MCD12C1 v061, 2023 (arazi örtüsü, 0,05°)
- Sayfa (DOI / ürün sayfası): doi:10.5067/MODIS/MCD12C1.061 · https://www.earthdata.nasa.gov/data/catalog/lpcloud-mcd12c1-061 (eski lpdaac.usgs.gov/products/mcd12c1v061/ buraya yönleniyor) · CMR concept ID C2484078896-LPCLOUD
- Dosyalar: 1 dosya — `MCD12C1.A2023001.061.2024251212901.hdf` · https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/MCD12C1.061/MCD12C1.A2023001.061.2024251212901/MCD12C1.A2023001.061.2024251212901.hdf
- Erişim: Earthdata (earthaccess) · short_name="MCD12C1", version="061", temporal=("2023-01-01","2023-12-31") → 1 granül (CMR'de 13 Kasım'da sınandı: hits = 1)
- Giriş gerekiyor mu: evet (Earthdata, `_netrc`)
- Beklenen boyut: 1186,6 MB (CMR granül kaydı ve ürün sayfası "Dataset Size")
- Sağlama: yok (yalnız boyut). CMR granül kaydında checksum alanı yok. Bütünlük: boyut + HDF4 dosyasının GDAL ile açılması.
- Kullanılacak katman/bant/değişken: `Land_Cover_Type_1_Percent` (IGBP sınıflarının piksel içi yüzdesi; uint8, %, fill 255, geçerli 0–100; 17 sınıf). Sınıf 0 su, 2 her dem yeşil geniş yapraklı orman, 12 tarım, 15 kar/buz, 16 çıplak. (Aynı dosyada `Majority_Land_Cover_Type_1`, `Type_2/3` de var; kullanılmaz.)
- Bilinen sorun: Dosya adındaki ikinci tarih (2024251…) üretim tarihidir; yeniden işlenirse değişir → adres sabit yazılmaz, earthaccess aramasıyla bulunur. Biçim HDF4 (HDF-EOS2): GDAL'da libgdal-hdf4 gerekir. Lisans: EOSDIS Data Use Policy — kısıtsız açık veri. Atıf (sayfadan, APA): "Friedl, Mark, & Sulla-Menashe, Damien. (2022). MODIS/Terra+Aqua Land Cover Type Yearly L3 Global 0.05Deg CMG V061 [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MCD12C1.061 Date Accessed: 2026-11-13"
- Doğrulandı: evet (13 Kasım 2026, 15:58; CMR API + ürün sayfası)

### E3 — GLiM (Global Lithological Map, Hartmann & Moosdorf 2012)
- Sayfa (DOI / ürün sayfası): resmî sayfa https://www.geo.uni-hamburg.de/geologie/forschung/aquatische-geochemie/glim.html (Hamburg Üniversitesi) · makale doi:10.1029/2012GC004370
- Dosyalar: 1 dosya — `LiMW_GIS 2015.gdb.zip` (adda boşluk var). Resmî sayfanın "original GIS data" bağlantısı: https://www.dropbox.com/s/9vuowtebp9f1iud/LiMW_GIS%202015.gdb.zip?dl=0 → indirme için sondaki `?dl=0` yerine `?dl=1` kullanılır: https://www.dropbox.com/s/9vuowtebp9f1iud/LiMW_GIS%202015.gdb.zip?dl=1
- Erişim: doğrudan https (Dropbox paylaşım bağlantısı; ?dl=1 ile yönlendirme sonrası dosya iner)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: sayfada yok. **Yaklaşık 1,14 GB** — bağımsız bir kaynaktan: GLiM'i bu zip'ten kullanan açık bir GitHub projesi (github.com/Thubaraleii/globo-terreste) dosyayı "LiMW_GIS_2015.gdb.zip (1,14 GB; camada GLiM_export, 1.235.259 polígonos, Eckert IV)" diye tanımlıyor; katman adı `GLiM_export`, sınıf sütunu `xx` ve Eckert IV projeksiyonu belgeyle aynı. Bayt düzeyinde kesin değer doğrulanmadı: Dropbox 13 Kasım'da üç denemede de tarayıcıda "Gizlilik hatası" (sertifika uyarısı) verdi (uyarı atlanmadı), Dropbox Internet Archive'dan da hariç tutulmuş. Bu bizim ağımızdan kaynaklanıyor olabilir — İrem'in bilgisayarında da aynı hata çıkarsa başka bir ağdan (ör. telefon hotspot) denenmeli. İndirme sonrası boyut kaydedilir; 0 bayt ya da HTML sayfası (ilk baytlar `<!DOCTYPE` / `<html`) gelirse indirme başarısızdır.
- Sağlama: zip CRC (açarken `zipfile` testzip). Üretici sağlaması yok.
- Kullanılacak katman/bant/değişken: zip içindeki File Geodatabase; katman `GLiM_export`, sınıf sütunu `xx` (Bölüm 10.1; birinci seviye 16 litoloji sınıfı). Projeksiyon World Eckert IV.
- Bilinen sorun: Resmî sayfa da doğrudan Dropbox'a bağlanıyor; yani önceki Dropbox indirmesi resmî kaynakla aynı bağlantıdır (doğrulandı). PANGAEA'daki GLiM kaydı (doi:10.1594/PANGAEA.788537) yalnız 0,5° ızgaralı kaba sürümdür — İNDİRİLMEZ. Dropbox ?dl=0 bağlantısı dosya değil HTML önizleme sayfası döndürür. **Yedek bağlantı:** 2026'da yayımlanmış iki makale (NHESS 26/3881 ve Remote Sensing 18/3253) GLiM'i Dropbox'ın yeni biçimli adresiyle veriyor: https://www.dropbox.com/scl/fi/5v00i8op7a9brmn4qeg8b/LiMW_GIS-2015.gdb.zip — makalelerden biri "login required" notu düşmüş. Eski `/s/` bağlantısı çalışmazsa bu denenir (sondaki `?dl=1` ile); bu bağlantı da bizim ağımızdan açılamadı. Lisans: sayfada yazmıyor (belge Bölüm 10.5'e göre CC BY; sayfadan doğrulanamadı → "açık"). Atıf: sayfada hazır "How to cite" yok; önerilen künye makale: Hartmann, J., Moosdorf, N. (2012): The new global lithological map database GLiM: A representation of rock properties at the Earth surface. Geochemistry, Geophysics, Geosystems, 13, Q12004, doi:10.1029/2012GC004370. **EKSİK — İrem için yapılacak:** Kesin bayt boyutu bilinmiyor. (1) Bu sette "beklenen boyut" kontrolü yerine indirme sonrası şu üç test yeterli: dosya ≥ 1 GB mi; ilk 2 bayt `PK` mi (HTML değil mi); `zipfile.testzip()` hatasız mı. Üçü geçerse dosya sağlamdır; gerçek boyutu `kayit\indirme.csv`'ye yaz. (2) Dropbox senin bilgisayarında da "Gizlilik hatası" verirse uyarıyı geçme; telefonla mobil veriden aç ya da başka bir ağ kullan. Sorun ağdaysa (okul/yurt ağı, internet sağlayıcısı ya da antivirüs Dropbox'ın sertifikasını engelliyor) başka ağda düzelir. (3) `/s/` bağlantısı çalışmazsa yukarıdaki `/scl/fi/` yedek bağlantıyı dene; giriş isterse ücretsiz bir Dropbox hesabıyla giriş gerekebilir.
- Doğrulandı: kısmen (13 Kasım 2026, 16:18, 16:30 ve 16:40 denemeleri; resmî sayfa, bağlantı ve katman/sütun adları evet; boyut yalnız yaklaşık, üçüncü taraf kaynaktan)

### E4 — ASTER GED AG5KMMOH v041, 2015, 12 ay (yayınım, 0,05°)
- Sayfa (DOI / ürün sayfası): doi:10.5067/COMMUNITY/ASTER_GED/AG5KMMOH.041 · https://www.earthdata.nasa.gov/data/catalog/lpcloud-ag5kmmoh-041 · CMR concept ID C2763268461-LPCLOUD
- Dosyalar: 12 dosya, ad kalıbı `ASTER_GEDv4.1_A2015{DDD}.h5`, DDD = 001, 032, 060, 091, 121, 152, 182, 213, 244, 274, 305, 335 (her ayın ilk günü). Adres kalıbı: https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/AG5KMMOH.041/ASTER_GEDv4.1_A2015{DDD}.h5 (CMR'den okunmuş gerçek adresler; alt klasör yok)
- Erişim: Earthdata (earthaccess) · short_name="AG5KMMOH", version="041", temporal=("2015-01-01","2015-12-31") → 12 granül (CMR'de sınandı: hits = 12)
- Giriş gerekiyor mu: evet (Earthdata)
- Beklenen boyut: CMR kaydında her dosya için 321,366 MB (12 dosyada aynı değer; ≈ 3,86 GB toplam). Değer üst veri tahmini olabilir; gerçek boyut indirmeden sonra kaydedilir.
- Sağlama: yok (yalnız boyut). CMR kaydında checksum yok. Bütünlük: boyut + HDF5 açılış testi.
- Kullanılacak katman/bant/değişken: `Emissivity` (5 bant: bant 10 8,3 µm · 11 8,6 µm · 12 9,1 µm · 13 10,6 µm · 14 11,3 µm; uint8, fill 0, geçerli 1–255, Scale Factor 0,002) ve `NDVI` (uint16, fill 0, Scale Factor 0,001). `Emissivity Uncertainty` ve `QFlag` kullanılmaz.
- Bilinen sorun: Biçim HDF5 (.h5), HDF4 değil. Ürün sayfası Emissivity için Offset'i "N/A" gösteriyor; belgedeki Offset 0,49 (Bölüm 10.1) dosyanın kendi özniteliğinden okunup assert edilmeli — sayfa ile belge burada farklı. Öznitelik adları boşluklu ("Scale Factor"). Sayfaya göre girdi verisi eksik aylarda dosya üretilmemiş olabilir; 2015 için 12/12 granül CMR'de mevcut. Lisans: EOSDIS Data Use Policy (kısıtsız). Atıf (sayfadan, APA): "NASA JPL. (2016). ASTER Global Emissivity Dataset, Monthly, 0.05 deg, HDF5 [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/COMMUNITY/ASTER_GED/AG5KMMOH.041 Date Accessed: 2026-11-13"
- Doğrulandı: evet (13 Kasım 2026, 16:05; CMR API + ürün sayfası)

### E5 — MODIS MYD11C3 v061 (Aqua), 2023, 12 ay (yüzey sıcaklığı, 0,05°)
- Sayfa (DOI / ürün sayfası): doi:10.5067/MODIS/MYD11C3.061 · https://www.earthdata.nasa.gov/data/catalog/lpcloud-myd11c3-061
- Dosyalar: 12 dosya. Adres kalıbı: https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/MYD11C3.061/{GRANÜL}/{GRANÜL}.hdf — 13 Kasım'da CMR'deki granül adları (MB, CMR):
  `MYD11C3.A2023001.061.2023033164343` 68,37 · `MYD11C3.A2023032.061.2023060194236` 69,44 · `MYD11C3.A2023060.061.2023093152049` 73,14 · `MYD11C3.A2023091.061.2023122195853` 71,80 · `MYD11C3.A2023121.061.2023153211939` 71,78 · `MYD11C3.A2023152.061.2023193054214` 70,43 · `MYD11C3.A2023182.061.2023215202151` 69,88 · `MYD11C3.A2023213.061.2023250152704` 70,85 · `MYD11C3.A2023244.061.2023274184351` 71,59 · `MYD11C3.A2023274.061.2023305220624` 74,07 · `MYD11C3.A2023305.061.2023336214254` 73,88 · `MYD11C3.A2023335.061.2024006163117` 70,19
- Erişim: Earthdata (earthaccess) · short_name="MYD11C3", version="061", temporal=("2023-01-01","2023-12-31") → 12 granül (CMR'de sınandı: hits = 12)
- Giriş gerekiyor mu: evet (Earthdata)
- Beklenen boyut: yukarıdaki değerler (CMR granül kaydı, MB); toplam ≈ 855 MB
- Sağlama: yok (yalnız boyut). CMR kaydında checksum yok. Bütünlük: boyut + HDF4 açılış testi.
- Kullanılacak katman/bant/değişken: `LST_Day_CMG` ve `LST_Night_CMG` (Kelvin; uint16; fill 0; geçerli 7500–65535; Scale Factor 0,02). Gerekirse `Day_view_time` / `Night_view_time` (saat; uint8; fill 255; ×0,2).
- Bilinen sorun: **MYD (Aqua) — MOD11C3 (Terra) DEĞİL** (belge D1). Dosya adındaki ikinci tarih üretim tarihidir; adres sabit yazılmaz, earthaccess aramasıyla bulunur. Lisans: EOSDIS Data Use Policy (kısıtsız). Atıf (sayfadan, APA): "Wan, Zhengming, Hook, Simon, & Hulley, Glynn. (2021). MODIS/Aqua Land Surface Temperature/Emissivity Monthly L3 Global 0.05Deg CMG V061 [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MYD11C3.061 Date Accessed: 2026-11-13"
- Doğrulandı: evet (13 Kasım 2026, 16:08; CMR API + ürün sayfası)

### E6 — MODIS MCD43C3 v061, 2023'ün her ayının 15'i, 12 dosya (albedo, 0,05°)
- Sayfa (DOI / ürün sayfası): doi:10.5067/MODIS/MCD43C3.061 · https://www.earthdata.nasa.gov/data/catalog/lpcloud-mcd43c3-061
- Dosyalar: 12 dosya. Adres kalıbı: https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/MCD43C3.061/{GRANÜL}/{GRANÜL}.hdf — Ayın 15'i = gün numarası (DDD) 015, 046, 074, 105, 135, 166, 196, 227, 258, 288, 319, 349. 13 Kasım'da CMR'deki granüller (MB, CMR):
  `MCD43C3.A2023015.061.2023024104905` 182,27 · `MCD43C3.A2023046.061.2023057224937` 220,62 · `MCD43C3.A2023074.061.2023083070952` 232,46 · `MCD43C3.A2023105.061.2023114063822` 196,75 · `MCD43C3.A2023135.061.2023144071438` 189,63 · `MCD43C3.A2023166.061.2023175104425` 185,03 · `MCD43C3.A2023196.061.2023215170711` 182,22 · `MCD43C3.A2023227.061.2023236071848` 180,75 · `MCD43C3.A2023258.061.2023267065355` 200,24 · `MCD43C3.A2023288.061.2023299045841` 223,74 · `MCD43C3.A2023319.061.2023328224454` 196,33 · `MCD43C3.A2023349.061.2023361073709` 174,97
- Erişim: Earthdata (earthaccess) · short_name="MCD43C3", version="061". **Dikkat: temporal ile tek gün araması 16 granül döndürür** (her granül 16 günlük pencereyi kapsar; ör. 2023-01-15 araması A2023008…A2023017 arası 16 dosya verdi). Doğru yol: granül adına göre seçmek — earthaccess.search_data(short_name="MCD43C3", version="061", granule_name="MCD43C3.A2023{DDD}*") ya da temporal=("2023-01-01","2023-12-31") ile arayıp adı `.A2023{DDD}.` içerenleri süzmek.
- Giriş gerekiyor mu: evet (Earthdata)
- Beklenen boyut: yukarıdaki değerler (CMR, MB); toplam ≈ 2 365 MB (≈ 2,4 GB)
- Sağlama: yok (yalnız boyut). CMR kaydında checksum yok.
- Kullanılacak katman/bant/değişken: `Albedo_WSA_shortwave` (beyaz-gök albedo; int16; fill 32767; geçerli 0–32766; Scale Factor 0,001). `Albedo_BSA_shortwave`, `Percent_Snow` vb. kullanılmaz.
- Bilinen sorun: Her tarih için dosya var mı → **12/12 var** (CMR'de 13 Kasım'da tek tek sınandı). Dosya adındaki tarih 16 günlük pencerenin 9. günüdür (sayfa: "temporally weighted to the ninth day"); A2023015 penceresi 7–22 Ocak. Günlük ürün, belgedeki gibi her ayın 15'i alınır. Lisans: EOSDIS Data Use Policy (kısıtsız). Atıf (sayfadan, APA): "Schaaf, Crystal, & Wang, Zhuosen. (2021). MODIS/Terra+Aqua BRDF/Albedo Albedo Daily L3 Global 0.05Deg CMG V061 [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MCD43C3.061 Date Accessed: 2026-11-13"
- Doğrulandı: evet (13 Kasım 2026, 16:12; CMR API + ürün sayfası)

### E7 — Permafrost kuzey yarımküre, Obu ve ark. 2018, PERPROB
- Sayfa (DOI / ürün sayfası): doi:10.1594/PANGAEA.888600 · https://doi.pangaea.de/10.1594/PANGAEA.888600
- Dosyalar: 1 dosya — https://store.pangaea.de/Publications/ObuJ-etal_2018/UiO_PEX_PERPROB_5.0_20181128_2000_2016_NH.zip
- Erişim: doğrudan https
- Giriş gerekiyor mu: hayır
- Beklenen boyut: 106 076 765 bayt (HEAD, 13 Kasım; sayfadaki tablo 103 591 kByte ile tutarlı). Zip içi: `UiO_PEX_PERPROB_5.0_20181128_2000_2016_NH.tif` açılmış hali 1 915 403 885 bayt (≈ 1,9 GB) + `.tfw`, `.tif.aux.xml`, `.tif.ovr`, `UiO_PEX_PERPROBLegend_5.0_20181128.lyr`.
- Sağlama: zip CRC. Zip içindeki CRC-32 değerleri (merkezi dizinden okundu): `.tif` 620a0b80 · `.tif.ovr` f10cc207 · `.tfw` b3b8fdc1 · `.tif.aux.xml` cc959271 · `.lyr` 867bafb5
- Kullanılacak katman/bant/değişken: zip içindeki `UiO_PEX_PERPROB_5.0_20181128_2000_2016_NH.tif` (permafrost olasılığı, kesir 0–1; EPSG:3995 Arctic Polar Stereographic). MAGTM, MAGTSTD, PERZONES ve 5 km .nc İNDİRİLMEZ.
- Bilinen sorun: Sıkıştırma yöntemi 8 = Deflate (Deflate64 DEĞİL; zip merkezi dizininden okundu) → standart `zipfile` ile açılır. Açılmış tif ≈ 1,9 GB, disk planına eklenmeli. Kapsam: kuzey yarımküre kara alanı, 25°K'ye kadar. Lisans: CC-BY-3.0 (sayfadan; belge 10.5'teki "CC BY" ile uyumlu). Atıf (sayfadan, aynen): "Obu, Jaroslav; Westermann, Sebastian; Kääb, Andreas; Bartsch, Annett (2018): Ground Temperature Map, 2000-2016, Northern Hemisphere Permafrost [dataset]. Alfred Wegener Institute, Helmholtz Centre for Polar and Marine Research, Bremerhaven, PANGAEA, https://doi.org/10.1594/PANGAEA.888600"
- Doğrulandı: evet (13 Kasım 2026, 16:25; sayfa + dosya tablosu + HEAD + zip merkezi dizini)

### E8 — Permafrost Antarktika, Obu ve ark. 2019, PERPROB
- Sayfa (DOI / ürün sayfası): doi:10.1594/PANGAEA.902576 · https://doi.pangaea.de/10.1594/PANGAEA.902576
- Dosyalar: 1 dosya — https://store.pangaea.de/Publications/ObuJ-etal_2019/UiO_PEX_PERPROB_5.0_20181205_2000_2017_ANT.zip (sayfadaki tabloda "Permafrost Probability Fraction (PERPROB) [Fraction, 0-1]" satırı bu dosyadır)
- Erişim: doğrudan https
- Giriş gerekiyor mu: hayır
- Beklenen boyut: 733 901 bayt (HEAD; sayfadaki tablo 716,700 kByte = 733 901 / 1024, tutarlı). Zip içi: `UiO_PEX_PERPROB_5.0_20181205_2000_2017_ANT.tif` açılmış hali 347 689 337 bayt + `.tfw`, `.tif.aux.xml`, `.tif.ovr`.
- Sağlama: zip CRC. Zip içi CRC-32: `.tif` a6ec5a8c · `.tif.ovr` 10000634 · `.tfw` 8dae01d8 · `.tif.aux.xml` b373e98c
- Kullanılacak katman/bant/değişken: zip içindeki `UiO_PEX_PERPROB_5.0_20181205_2000_2017_ANT.tif` (kesir 0–1; EPSG:3031; 1 km). MAGTM, MAGTSTD ve Thumbnail_MAGT.jpg İNDİRİLMEZ.
- Bilinen sorun: Sıkıştırma yöntemi 8 = Deflate (Deflate64 DEĞİL; merkezi dizinden okundu). Zip küçük (0,7 MB) ama açılmış tif 348 MB: çok sıkışmış, 0 baytlık açılma kontrolü yine yapılır. Dosya klasörü `ObuJ-etal_2019` (kuzeydeki `_2018`). Lisans: CC-BY-4.0 (sayfadan). Atıf (sayfadan, aynen): "Obu, Jaroslav; Westermann, Sebastian; Kääb, Andreas; Bartsch, Annett (2019): Ground Temperature Map, 2000-2017, Antarctic [dataset]. University of Oslo, PANGAEA, https://doi.org/10.1594/PANGAEA.902576"
- Doğrulandı: evet (13 Kasım 2026, 16:25; sayfa + dosya tablosu + HEAD + zip merkezi dizini)

### E9 — Global Aridity Index v3.1 (yıllık), Zomer & Trabucco
- Sayfa (DOI / ürün sayfası): doi:10.6084/m9.figshare.7504448 (güncel sürüm v7: doi:10.6084/m9.figshare.7504448.v7) · kayıt verisi https://api.figshare.com/v2/articles/7504448
- Dosyalar: yıllık AI dosyası `Global-AI_ET0__annual_v3_1.zip` → https://ndownloader.figshare.com/files/56300327 · ayrıca okuma notu için `Global AI_ET0 v3.1 - Readme.docx` → https://ndownloader.figshare.com/files/56300216 — (Aynı kayıttaki `Global-ET0__monthly_v3_1.zip`, `Global_AI__monthly_v3_1.zip` (3,9 GB) ve `GlobalPET.jpg` İNDİRİLMEZ.)
- Erişim: doğrudan https (ndownloader.figshare.com bağlantısı yönlendirme yapar; yönlendirme izlenmeli)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: zip 645 783 906 bayt · readme 645 897 bayt (figshare API, 13 Kasım)
- Sağlama: üreticinin MD5'i (figshare API `computed_md5`, adres: https://api.figshare.com/v2/articles/7504448 ): zip `ef3f6f53a082fb07365954b468cca55f` · readme `ad026eba14bd5f50c6be2abc603ed74f`. Ayrıca zip CRC.
- Kullanılacak katman/bant/değişken: zip içindeki **`ai_v31_yr.tif`** (yıllık Aridity Index; 30 yay-saniye ≈ 1 km; 1970–2000) + `ai_v31_yr.tfw`, `ai_v31_yr.tif.xml`, `ai_v31_yr.tif.aux.xml`. **Zip içi liste figshare'in dosya önizlemesinden okundu (16:35):** zip'te `Global-AI_ET0__annual_v3_1/` klasörü altında `ai_v31_yr.*`, `et0_v31_yr.*`, `et0_v31_yr_sd.*` (+ .vat.dbf/.cpg), `Global AI_ET0 v3.1 - Readme.docx` ve bir **`__MACOSX/`** klasörü var. `et0_v31_yr*` (ET0) ve `__MACOSX/` içindeki `._` ile başlayan dosyalar KULLANILMAZ (sonu .tif olsa da veri değil, macOS kalıntısı).
- Bilinen sorun: **Çarpan × 10 000 sayfada doğrulandı** — açıklama metni: AI değerleri tamsayı olarak dağıtmak için 10 000 ile çarpılmış (4 ondalık hassasiyet). Kodda AI = DN / 10 000 ve dosyadan assert (belge D9). figshare kaydının sürüm numarası (v7) yazılımsal sürümdür; veri sürümü "Version 3.1". Sayfa notu: v3.0 hatalı (net uzun dalga ışınım hatası, AI'da kuru yönde sapma) ve geri çekildi; v3.1 kullanılmalı — bizim dosyamız v3.1. Sayfanın eski metninde verinin "non-commercial use" için sunulduğu da yazıyor; lisans alanı CC BY 4.0 — proje ticari değil, sorun yok. Lisans: CC BY 4.0 (sayfadan). Atıf (sayfadan, aynen): "Zomer, Robert; Trabucco, Antonio (2019). Global Aridity Index and Potential Evapotranspiration (ET0) Database: Version 3.1. figshare. Dataset. https://doi.org/10.6084/m9.figshare.7504448.v7"
- Doğrulandı: evet (13 Kasım 2026, 16:30; figshare API: dosya adları, boyut, MD5, lisans, açıklama metni)

### E10 — SoilGrids 2.0, kil + silt, 0–5 cm, 1000 m (aggregated)
- Sayfa (DOI / ürün sayfası): kil 1000 m kaydı https://data.isric.org/geonetwork/srv/api/records/5e1605a7-5cae-4f7c-b800-9aa7f315d00d (doi:10.17027/isric-soilgrids/5e1605a7-5cae-4f7c-b800-9aa7f315d00d) · silt 1000 m kaydı https://data.isric.org/geonetwork/srv/api/records/08a4990c-ca15-4871-8d12-ea21dae6b354 (doi:10.17027/isric-soilgrids/08a4990c-ca15-4871-8d12-ea21dae6b354; "Silt content (2-50/63 micro meter) mass fraction in ‰", CC BY 4.0) · klasör https://files.isric.org/soilgrids/latest/data_aggregated/ (README.md ile)
- Dosyalar: 2 dosya — https://files.isric.org/soilgrids/latest/data_aggregated/1000m/clay/clay_0-5cm_mean_1000.tif · https://files.isric.org/soilgrids/latest/data_aggregated/1000m/silt/silt_0-5cm_mean_1000.tif (ad biçimi belgedeki gibi `{özellik}_0-5cm_mean_1000.tif`, doğrulandı). Sağlama için ayrıca her klasördeki `checksum.sha256.txt`.
- Erişim: doğrudan https (klasör listesi)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: clay_0-5cm_mean_1000.tif 191 530 251 bayt · silt_0-5cm_mean_1000.tif 194 638 176 bayt (HEAD, 13 Kasım)
- Sağlama: üreticinin SHA-256 dosyası — https://files.isric.org/soilgrids/latest/data_aggregated/1000m/clay/checksum.sha256.txt ve …/1000m/silt/checksum.sha256.txt (her biri 6 satır, her derinlik için bir). 13 Kasım'daki değerler: clay_0-5cm `20f699cc64686bb5696e395f709232e5957ea3c6a4b39f6676517a502033f424` · silt_0-5cm `4c72f9303aa27fcb5f2527bb1a64b307e9ef37885afc08cdcee063e99c495295`. Kod değeri dosyadan okur; yukarıdaki değerler çapraz kontrol içindir.
- Kullanılacak katman/bant/değişken: tek bant, ortalama tahmin (`mean`); birim ‰ kütle kesri (= g/kg), kayıt: "Clay content (0-2 micro meter) mass fraction in ‰". Diğer derinlikler (5-15, 15-30 … cm) İNDİRİLMEZ.
- Bilinen sorun: Projeksiyon Goode Homolosine (`+proj=igh`, ESRI:54052); kapsam 56°G–84°K (kayıttaki sınır kutusu). 1000 m dosyası 250 m tahminlerin yeniden örneklenmiş ortalamasıdır (README). Dosya COG GeoTIFF. Lisans: CC BY 4.0 (README ve kayıt). Atıf (ISRIC FAQ sayfasındaki künye): "Poggio, L., de Sousa, L. M., Batjes, N. H., Heuvelink, G. B. M., Kempen, B., Ribeiro, E., and Rossiter, D.: SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty, SOIL, 7, 217–240, 2021." (doi:10.5194/soil-7-217-2021)
- Doğrulandı: evet (13 Kasım 2026, 16:36; klasör listesi, checksum dosyaları, HEAD, README, ISRIC kaydı)

## Ay

### M1 — LOLA Global LDEM 118 m (256 ppd)
- Sayfa (DOI / ürün sayfası): https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m (USGS Astropedia "Moon LRO LOLA DEM 118m"; PDS veri seti LRO-L-LOLA-4-GDR-V1.0, ürün LDEM_256)
- Dosyalar: 1 veri dosyası + 2 yardımcı (.md5, .lbl) — https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif (13 Kasım'da planetarymaps.usgs.gov/mosaic/ adresi https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/ adresine yönleniyor; aynı dosya). Sağlama ve etiket için aynı klasörde: `Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif.md5`, `Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.lbl` (ISIS etiketi), `…_pds3.lbl`.
- Erişim: doğrudan https
- Giriş gerekiyor mu: hayır
- Beklenen boyut: 8 494 203 833 bayt (S3 listesi + HEAD + Range isteğinin Content-Range'i; sayfada "8 GB"). Not: yönlendirilen S3 adresi HEAD'e boyut VERİYOR; Range (kaldığı yerden devam) 206 ile çalışıyor.
- Sağlama: üreticinin MD5 dosyası — https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif.md5 → içerik: `40b61c7051c744582ec0a2d153757b5e  Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014.tif`
- Kullanılacak katman/bant/değişken: tek bant. Etiketten (.lbl): 92160 sütun × 46080 satır, 1 bant, SignedWord (int16), Lsb, Base 0,0, Multiplier 0,5 → yükseklik (m) = DN × 0,5. Belgedeki okuma kuralıyla aynı.
- Bilinen sorun: Dosya **BigTIFF** (ilk baytlar `49 49 2B 00`) — eski TIFF okuyucular açamaz; GDAL/rasterio açar. Sıkıştırmasız (etikette BandSequential, StartByte 738234). Dosyanın tamamı belleğe alınmaz; pencere/enlem bandı okunur. Sayfa GDAL ile `gdal_translate -ot Float32 -unscale` önerir. Lisans: Access Constraints "public domain"; Use Constraints "Please cite authors". Atıf (sayfadaki künye alanlarından): LOLA Science Team (2014). Moon LRO LOLA DEM 118m. Originator: Goddard Space Flight Center; Publisher: USGS Astrogeology Science Center; Edition: March 11, 2014. https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m — sayfada hazır tek satırlık "How to cite" metni yok; ayrıca Smith et al. (2010) LOLA makalesine [105] atıf yapılır.
- Doğrulandı: evet (13 Kasım 2026, 16:42; ürün sayfası, S3 listesi, HEAD, .md5, .lbl)

### M2 — Unified Geologic Map of the Moon 1:5M (2020)
- Sayfa (DOI / ürün sayfası): https://astrogeology.usgs.gov/search/map/unified_geologic_map_of_the_moon_1_5m_2020 (Edition 2.0, March 3, 2020)
- Dosyalar: 1 dosya — https://asc-astropedia.s3.us-west-2.amazonaws.com/Moon/Geology/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip (sayfadaki "Online File Link")
- Erişim: doğrudan https
- Giriş gerekiyor mu: hayır
- Beklenen boyut: 224 413 040 bayt (sayfadaki "External File Size" ve S3 listesi aynı)
- Sağlama: zip CRC (298 girdi). Üretici sağlaması yok.
- Kullanılacak katman/bant/değişken: zip içindeki `Unified_Geologic_Map_of_the_Moon_GIS/Lunar_GIS/Shapefiles/GeoUnits.shp` (+ .dbf .shx .prj .cpg; açılmış .shp 126 176 440 bayt). .dbf'den okundu: 12 247 kayıt, alanlar `FIRST_Unit`, `FIRST_Un_1`, `FIRST_Un_2`, `Shape_Leng`, `Shape_Area`, `AREA_GEO`. Birim kodu `FIRST_Unit`, alan `AREA_GEO` (belgeyle aynı).
- Bilinen sorun: Zip içinde bir üst klasör daha var: yol `Unified_Geologic_Map_of_the_Moon_GIS/Lunar_GIS/Shapefiles/…` (belgedeki `Lunar_GIS\Shapefiles\GeoUnits.shp` bu klasörün altında). Zip içindeki GDB açılmaz (belge). Sıkıştırma yöntemleri 0 (stored) ve 8 (Deflate); Deflate64 yok. Lisans: sayfada Use Constraints "CC0, but please cite authors"; Access Constraints "none". Atıf (sayfadaki künye alanlarından): Fortezzo, C.M., Spudis, P.D., Harrel, S.L. (2020). Unified Geologic Map of the Moon, 1:5M, 2020. Edition 2.0, March 3, 2020. USGS Astrogeology Science Center. https://astrogeology.usgs.gov/search/map/unified_geologic_map_of_the_moon_1_5m_2020 — sayfada hazır tek satırlık "How to cite" metni yok; ek bilgi olarak LPSC 2020 özeti 2760 gösteriliyor [38].
- Doğrulandı: evet (13 Kasım 2026, 16:48; ürün sayfası, S3 listesi, zip merkezi dizini, .dbf başlığı)

### M3 — Diviner GHRM ra_sam (kaya bolluğu) + tbol_sam (gece sıcaklığı), 128 ppd, 70°G–70°K
- Sayfa (DOI / ürün sayfası): doi:10.17189/wj0s-w188 (PDS4 bundle "Lunar Reconnaissance Orbiter Diviner Derived Data Bundle 1", sürüm 5.0) · https://pds-geosciences.wustl.edu/missions/lro/diviner.htm · bundle kökü https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/
- Dosyalar: 4 dosya (2 veri + 2 PDS4 etiketi):
  https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_ghrm/geotiff/dghrm_ra_sam_70s70n_tif.tif
  https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_ghrm/geotiff/dghrm_ra_sam_70s70n_tif.xml
  https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_ghrm/geotiff/dghrm_tbol_sam_70s70n_tif.tif
  https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_ghrm/geotiff/dghrm_tbol_sam_70s70n_tif.xml
- Erişim: doğrudan https (klasör listesi)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: dghrm_ra_sam_70s70n_tif.tif 3 303 158 255 bayt · dghrm_tbol_sam_70s70n_tif.tif 3 303 158 255 bayt · .xml 8 345 ve 8 357 bayt (klasör listesi, 13 Kasım)
- Sağlama: üreticinin MD5 listesi — https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/urn-nasa-pds-lro_diviner_derived1.md5 (45 050 842 bayt, 403 062 satır; anahtar biçimi `data_derived_ghrm\geotiff\dosya` — ters eğik çizgi). Değerler: ra_sam .tif `F502BB2837DAC380A2794D56BDEA755C` · ra_sam .xml `D44AD4DDE044CAB441829A89A1B12EA7` · tbol_sam .tif `8DE5FA42F510B6079A0DB622ABE6208D` · tbol_sam .xml `836089C3BF4F2FA4C5D6106F2FF81E65`
- Kullanılacak katman/bant/değişken: tek bant; float32 (IEEE754 LSB), veri-yok NaN (PDS4 etiketinden). ra = kaya bolluğu (slope-adjusted midnight), tbol = bolometrik sıcaklık, K (slope-adjusted midnight). Aynı klasördeki `img/` sürümleri ve tb6–tb9, treg, anom ürünleri İNDİRİLMEZ.
- Bilinen sorun: tbol ≥ 250 K "yok" sayılır (belge 10.2). MD5 listesindeki yollar Windows tipi (\) — kod eşleştirirken `/` ile değiştirmeli. MD5 listesi tüm bundle'ı kapsıyor (45 MB); yalnız ilgili satırlar kullanılır, M4 için de aynı dosya geçerli. Lisans: NASA PDS verisi, kamuya açık (sayfada ayrı lisans metni yok). Atıf (bundle.xml künyesinden): Paige, D.; Sullivan, M.; Williams, J-P. (2022). Lunar Reconnaissance Orbiter Diviner Derived Data Bundle 1 (urn:nasa:pds:lro_diviner_derived1), v5.0. NASA Planetary Data System. https://doi.org/10.17189/wj0s-w188 — sayfada hazır "How to cite" metni yok.
- Doğrulandı: evet (13 Kasım 2026, 16:58; klasör listesi, MD5 listesi, PDS4 etiketi, bundle.xml)

### M4 — Diviner PRP (kuzey/güney) + GCP 0,5° bantları (70n80n, 80n90n, 80s70s, 90s80s)
- Sayfa (DOI / ürün sayfası): doi:10.17189/wj0s-w188 (M3 ile aynı bundle) · PRP: PDS3 veri seti LRO-L-DLRE-5-PRP-V2.0 · GCP: LRO-L-DLRE-5-GCP-V1.0
- Dosyalar: 18 dosya.
  PRP (her biri .tab + .lbl + .xml): https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_prp/dlre_prp_north.{tab,lbl,xml} · https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_prp/dlre_prp_south.{tab,lbl,xml}
  GCP (her biri .tab + .lbl + .xml): https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_gcp/global_cumul_avg_cyl_{70n80n,80n90n,80s70s,90s80s}_002.{tab,lbl,xml}
  (GCP .lbl dosyası yapı için `DLRE_GCP.FMT`'ye bağlanır; aynı bilgi .xml'de var, .xml yeterli.)
- Erişim: doğrudan https (klasör listesi)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: dlre_prp_north.tab 604 800 210 · dlre_prp_south.tab 604 800 210 · .lbl 2 167 · .xml 14 561 (her ikisi) · global_cumul_avg_cyl_*_002.tab 156 211 313 (4'ü de aynı) · GCP .lbl 3 462 (70n80n, 80n90n), 3 464 (80s70s), 3 413 (90s80s) · GCP .xml 16 003 (kuzey), 16 005 (güney) bayt. Toplam ≈ 1,83 GB.
- Sağlama: üreticinin MD5 listesi (M3'teki https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/urn-nasa-pds-lro_diviner_derived1.md5 ). Değerler: prp_north .tab `200108632FB75045597862887E841C01` .lbl `04611C68D7C1D8CF677DAFC61C944343` .xml `D02698E6FF8DC18B11535B3037CEAAC1` · prp_south .tab `80CDFE83592A3419C74B1B55B636711E` .lbl `C209EDAAA10C7AF19D973E252AC589EC` .xml `C0BE50F837784FA478DECB741C003482` · gcp 70n80n .tab `C132354928AD9B09A3DA974B6AF9F215` .lbl `E8908730B7CB7F7D1647E1A93099DD11` .xml `A9FF44AF068B3517298BE2DDF08DE90C` · 80n90n .tab `396E9215AB3925B3B1FACF6D487050C4` .lbl `BABBEDE556C76F829731E00F07A1215E` .xml `81B738FADCDE4618BFAAD9A5E744FC63` · 80s70s .tab `D26AA3C85B82105DCB15825DE076A4CE` .lbl `5B2B9B51C46836ADFF77AE5478F1038C` .xml `9C7B40ECEC295E89EA95AA0A465F0D78` · 90s80s .tab `3200DD1267B676CAD89300D344A88010` .lbl `3A97121C320B450E324FD335B1F6F48B` .xml `DC72C34810B3A90E2900BA1D7B09EC42`
- Kullanılacak katman/bant/değişken:
  PRP: virgüllü ASCII tablo, 2 880 000 kayıt (her yarımküre). Sütunlar: tri1_x…tri3_z, `tri_clon` (doğu boylamı, °), `tri_clat` (°), tri_calt, `temp_avg` (yıllık ortalama, 2 cm derinlikte, K), `temp_max` (yıllık maksimum, yüzeyde, K), `ice_depth` (m).
  GCP: başlık satırı + 1 382 400 satır (= 20 enlem × 720 boylam × 96 yerel saat), virgüllü sabit genişlikli ASCII. Sütunlar: `clon`, `clat` (0,5° hücre merkezi), `ltim` (yerel saat kutusunun merkezi, saat: 0,12, 0,38, … — 0,25 sa kutular), `t3`…`t9` (kanal parlaklık sıcaklıkları, K), `tbol` (bolometrik, K). **Yerel saat tanımı:** her satır bir (hücre, 0,25 sa yerel saat kutusu); gece ortalaması (Bölüm D5, 18:00–06:00) = `ltim` ≥ 18 ya da < 6 olan satırların `tbol` ortalaması. −9999 = gözlem yok.
- Bilinen sorun: PRP `ice_depth`: etikete göre −999 = derinlik 2,8738 m'den büyük (sansürlü, NaN değil); etikete göre **0 = buz yüzeyde kararlı**. Belgedeki (D10) "−1 belgelenmemiş değer" etikette tanımlı değil — etikette yalnız 0 ve −999 geçiyor; −1 bayrakla tutulur, 0 ile ayrı sayılır. GCP'de negatif parlaklık sıcaklıkları geçerli (etiket: kanal duyarlılığının altı), yalnız −9999 veri-yok. Lisans/atıf: M3 ile aynı bundle künyesi; ek olarak GCP için Williams et al. (2017) Icarus 283, 300–325 [123], PRP için Paige et al. (2010) Science 330, 479 [135] (etiketlerin kendi önerdiği kaynaklar).
- Doğrulandı: evet (13 Kasım 2026, 17:02; klasör listeleri, MD5 listesi, .lbl/.xml etiketleri, .tab ilk satırları)

### M5 — Lunar Prospector GRS element bollukları, 2° eş alanlı
- Sayfa (DOI / ürün sayfası): https://pds-geosciences.wustl.edu/missions/lunarp/grs_elem_abundance.html · PDS3 veri seti LP-L-GRS-5-ELEM-ABUNDANCE-V1.0 (PDS4: urn:nasa:pds:lp_grs_derived) · cilt kökü https://pds-geosciences.wustl.edu/lunar/lp-l-grs-5-elem-abundance-v1/lp_9001/
- Dosyalar: 4 dosya —
  https://pds-geosciences.wustl.edu/lunar/lp-l-grs-5-elem-abundance-v1/lp_9001/data/lpgrs_high1_elem_abundance_2deg.tab
  https://pds-geosciences.wustl.edu/lunar/lp-l-grs-5-elem-abundance-v1/lp_9001/data/lpgrs_high1_elem_abundance_2deg.lbl
  https://pds-geosciences.wustl.edu/lunar/lp-l-grs-5-elem-abundance-v1/lp_9001/data/lpgrs_high1_elem_abundance_2deg.xml
  https://pds-geosciences.wustl.edu/lunar/lp-l-grs-5-elem-abundance-v1/lp_9001/data/lpgrs_elem_abundance.fmt
- Erişim: doğrudan https (klasör listesi)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: .tab 9 949 280 · .lbl 8 102 · .xml 37 946 · .fmt 23 574 bayt (klasör listesi, 13 Kasım). Kontrol: .tab = 11 306 satır × 880 bayt = 9 949 280 ✓.
- Sağlama: yok (yalnız boyut). Ciltte md5 dosyası yok. Ek bütünlük testi: satır sayısı = 11 306 (etiketteki FILE_RECORDS) ve satır uzunluğu 880 bayt.
- Kullanılacak katman/bant/değişken: ASCII tablo, 61 sütun. Konum: `Pixel_Index`, `Southernmost_Latitude`, `Northernmost_Latitude`, `Westernmost_Longitude`, `Easternmost_Longitude` (boylam doğuya artar). Değerler: `W_FeO` (FeO ağırlık kesri, g/g) ve `W_Th` (Th, ppm). Diğerleri (W_MgO, W_Al2O3, W_SiO2, W_CaO, TiO2, W_K, W_U, E[i,j] hata matrisi) kullanılmaz.
- Bilinen sorun: Sütun adı tutarsızlığı: titanyum sütunu `TiO2` (W_ öneki yok) — sütunlar adla değil etiket sırasıyla okunursa sorun yok. `W_Th` adı "weight fraction" olsa da birimi ppm (etiketten). 11 306 piksel; alan toplamı = 4πR² testi (belge 10.2). Lisans: kamu malı (data.gov kaydı "public domain"). Atıf (veri seti kataloğundaki CITATION_DESC, aynen): "Prettyman, T.H., Lunar Prospector GRS Elemental Abundance, LP-L-GRS-5-ELEM-ABUNDANCE-V1.0, NASA Planetary Data System, 2012." + makale Prettyman et al. (2006) JGR 111, E12007, doi:10.1029/2005JE002656 [136].
- Doğrulandı: evet (13 Kasım 2026, 17:08; klasör listesi, .lbl, .xml, dataset.cat)

### M6 — Lunar Prospector hidrojen 0,5° (hydrogenhd) + hydrogenlow + epis (çapraz kontrol)
- Sayfa (DOI / ürün sayfası): https://pds-geosciences.wustl.edu/missions/lunarp/reduced_special.html ("Lunar Prospector Reduced Spectrometer Data Special Products"; PDS arşivi değil, LP Spektrometre ekibinin özel ürünleri — sayfa böyle tanımlıyor)
- Dosyalar: 6 dosya —
  https://pds-geosciences.wustl.edu/missions/lunarp/reduced/hydrogenhd.txt · https://pds-geosciences.wustl.edu/missions/lunarp/reduced/hydrogenhd.dat
  https://pds-geosciences.wustl.edu/missions/lunarp/reduced/hydrogenlow.txt · https://pds-geosciences.wustl.edu/missions/lunarp/reduced/hydrogenlow.dat
  https://pds-geosciences.wustl.edu/missions/lunarp/reduced/epis.txt · https://pds-geosciences.wustl.edu/missions/lunarp/reduced/epis.dat
- Erişim: doğrudan https
- Giriş gerekiyor mu: hayır
- Beklenen boyut: hydrogenhd.txt 14 256 401 · hydrogenlow.txt 622 233 · epis.txt 757 837 · her .dat 518 400 bayt (HEAD, 13 Kasım; sayfada 13,9 MB / 0,61 MB / 0,74 MB / 0,51 MB). Sürüm: hydrogenhd 3 Ocak 2002, hydrogenlow 6 Temmuz 2001.
- Sağlama: yok (yalnız boyut). Ek bütünlük testi (13 Kasım'da dosya okunarak doğrulandı): hydrogenhd.txt'de 259 200 veri satırı (= 360 × 720), her satır 5 sütun.
- Kullanılacak katman/bant/değişken: hydrogenhd.txt — "#" ile başlayan 13 başlık satırı, sonra virgüllü 5 sütun: `Lat min, Lat max, Lon min, Lon max, H ppm by weight`. İlk satır −90,00…−89,50 enlem, −180,00…−179,50 boylam (boylam −180'den başlıyor, enlem güneyden kuzeye). Birim: H ppm (ağırlıkça). hydrogenlow ve epis yalnız çapraz kontrol için (60 km × 60 km bin).
- Bilinen sorun: Belgedeki "360 × 720 ASCII tablo" aslında **uzun biçimli** tablodur (259 200 satır × 5 sütun), ızgara değil; satırlar 0,5° hücrelere çevrilir. **Bozuk hücre doğrulandı:** tek hücre `**********` → 43,00–43,50°K, 153,50–154,00°D (NaN). **Negatif hücre sayısı doğrulandı: 4 180** (kırpılmaz). Sayfaya göre yüksek Th / nadir toprak elementi bölgelerinde H değerleri güvenilir olmayabilir. .dat dosyalarının ikili biçimi sayfada tanımlı değil (518 400 bayt = 360 × 720 × 2) → .txt kullanılır, .dat yalnız arşiv için. Lisans: NASA PDS Geosciences Node, kamuya açık (sayfada ayrı lisans yok). Atıf: sayfada hazır künye yok; dosya başlığı "Feldman et al., JGR, 2001" diyor → Feldman, W.C. et al. (2001) J. Geophys. Res. 106(E10), 23231–23251 [34] + PDS Geosciences Node, Lunar Prospector Reduced Special Products [58].
- Doğrulandı: evet (13 Kasım 2026, 17:14; sayfa, HEAD, hydrogenhd.txt tamamı okunarak)

### M7 — PGDA AVGVISIB ve LPSR, 65° kutup, 240 m
- Sayfa (DOI / ürün sayfası): https://pgda.gsfc.nasa.gov/products/69 ("Lunar Polar Illumination", NASA GSFC PGDA)
- Dosyalar: 8 dosya (4 veri + 4 etiket):
  https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_65S_240M_201608.TIF · https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_65N_240M_201608.TIF · https://pgda.gsfc.nasa.gov/data/MoonIllumination/LPSR_65S_240M_201608.TIF · https://pgda.gsfc.nasa.gov/data/MoonIllumination/LPSR_65N_240M_201608.TIF
  https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_65S_240M_201608.LBL · https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_65N_240M_201608.LBL · https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/LPSR_65S_240M_201608.LBL · https://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/LPSR_65N_240M_201608.LBL
- Erişim: veri https (pgda.gsfc.nasa.gov); etiketler imbrium.mit.edu (http adresi https'e yönleniyor, ikisi de çalışıyor)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: AVGVISIB_65S 60 394 652 · AVGVISIB_65N 61 184 010 · LPSR_65S 582 074 · LPSR_65N 613 892 bayt (HEAD) · .LBL: AVGVISIB_65N 4 093, AVGVISIB_65S 4 096, LPSR_65N 3 914, LPSR_65S 3 917 bayt (klasör listesi)
- Sağlama: yok (yalnız boyut). PGDA ve imbrium klasörlerinde md5 dosyası yok.
- Kullanılacak katman/bant/değişken: tek bant; etiketten: 6420 × 6420, LSB_INTEGER 16 bit, polar stereografik, 240 m/piksel. AVGVISIB = DN × 0,00004 (OFFSET 0,0; ortalama görünürlük kesri). LPSR = DN × 0,000025 + 0,5 (OFFSET 0,5; kalıcı gölge, ikili değer). Belgedeki ölçek/ofset ile aynı.
- Bilinen sorun: **Düz TIF seçilmeli, `_COG.TIF` DEĞİL** (sayfada her dosyanın yanında COG sürümü de var). Dosyalar BigTIFF (`49 49 2B 00`). **Sayfadaki yanlış bağlantılar doğrulandı:** LPSR_65S satırında "JP2" bağlantısı IMG klasöründeki .IMG dosyasını gösteriyor; LPSR_65N satırında "IMG" bağlantısı IMG klasöründe .JP2 dosyasını gösteriyor. Bu yüzden etiketler yukarıdaki tam adreslerden alınır. AVGVISIB_65S ve LPSR_65S etiketleri 13 Ekim 2023'te güncellenmiş (kuzeydekiler 28 Eylül 2016). Koordinat: x = ρ sin λ, y = ρ cos λ (kuzey CRS'i yanlış; belge 10.2); anormal piksel 88,435°K 106,602°D NaN. Lisans: NASA verisi, kamuya açık (sayfada ayrı lisans yok). Atıf (sayfanın istediği): "Mazarico, E., et al. (2011), Illumination conditions of the lunar polar regions using LOLA topography, Icarus, Vol. 211, pp. 1066-1081, doi:10.1016/j.icarus.2010.10.030."
- Doğrulandı: evet (13 Kasım 2026, 17:20; ürün sayfası, HEAD, .LBL içerikleri, imbrium klasör listesi)

## Mars

### R1 — MGS MOLA DEM 463 m (128 ppd)
- Sayfa (DOI / ürün sayfası): https://astrogeology.usgs.gov/search/map/mars_mgs_mola_dem_463m (USGS Astropedia "Mars MGS MOLA DEM 463m"; kaynak PDS MEGDR)
- Dosyalar: 1 veri dosyası + 2 yardımcı (.md5, .lbl) — https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif (13 Kasım'da https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/ adresine yönleniyor). Aynı klasörde sağlama: `Mars_MGS_MOLA_DEM_mosaic_global_463m.tif.md5`; etiket: `Mars_MGS_MOLA_DEM_mosaic_global_463m.lbl`.
- Erişim: doğrudan https
- Giriş gerekiyor mu: hayır
- Beklenen boyut: 2 125 771 142 bayt (S3 listesi, HEAD ve Content-Range aynı; belgedeki değerle birebir). Yönlenen S3 adresi HEAD'e boyut veriyor, Range 206 ile çalışıyor.
- Sağlama: üreticinin MD5 dosyası — https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif.md5 → `e7920a303f46707d57fe72eab5f6b1aa  Mars_MGS_MOLA_DEM_mosaic_global_463m.tif`
- Kullanılacak katman/bant/değişken: tek bant, 16 bit, 46080 sütun × 23040 satır, 128 piksel/derece, Simple Cylindrical, planetosentrik enlem, boylam doğuya pozitif, −180…180 (sayfadaki geouzamsal bilgi). Yükseklik metre, areoide göre (GMM-2B).
- Bilinen sorun: Klasik TIFF (BigTIFF değil; ilk baytlar `49 49 2A 00`). Belgeye göre transform kullanılmaz: satır = ⌊(90 − φ)·128⌋, sütun = ⌊(λ + 180)·128⌋ — sayfadaki boyutlar (23040 = 180×128, 46080 = 360×128, boylam −180'den) bununla tutarlı. Kutuplar (87° ötesi) seyrek veriden enterpolasyon; 88–90° boşlukları kutup ürünlerinden doldurulmuş (sayfa). Lisans: Access Constraints "CC0 (public domain)", Use Constraints "None". Atıf: sayfada hazır "How to cite" yok; künye alanları: MOLA Team; Originator Goddard Space Flight Center; Publisher USGS Astrogeology Science Center; Edition 2003-03-21 — ayrıca Smith et al. (2001) JGR 106(E10), 23689–23722, doi:10.1029/2000JE001364 [104].
- Doğrulandı: evet (13 Kasım 2026, 17:25; ürün sayfası, S3 listesi, HEAD, .md5)

### R2 — Geologic Map of Mars, SIM 3292, 1:20M (Tanaka ve ark. 2014)
- Sayfa (DOI / ürün sayfası): doi:10.3133/sim3292 · https://pubs.usgs.gov/sim/3292/
- Dosyalar: 2 dosya — https://pubs.usgs.gov/sim/3292/downloads/sim3292_database.zip · https://pubs.usgs.gov/sim/3292/downloads/sim3292_readme.txt
- Erişim: doğrudan https
- Giriş gerekiyor mu: hayır
- Beklenen boyut: sim3292_database.zip 808 910 442 bayt (HEAD ve Content-Range aynı, 13 Kasım; sayfada "790 MB"). sim3292_readme.txt: sayfada "6 kB"; HEAD 2 322 bayt döndü (sunucu sıkıştırarak gönderiyor olabilir) → readme boyutu indirmeden sonra kaydedilir.
- Sağlama: zip CRC (211 girdi). Üretici sağlaması yok.
- Kullanılacak katman/bant/değişken: zip içindeki `SIM3292_MarsGlobalGeologicGIS_20M/SIM3292_Shapefiles/SIM3292_Global_Geology.shp` (+ .dbf .shx .prj). .dbf'den okundu: 1 311 kayıt, alanlar `OBJECTID`, `Shape_Leng`, `Shape_Area`, `Unit`, `UnitDesc`, `SphArea_km`; `Unit` alanında **44 farklı birim** (belgeyle aynı). Birim `Unit`, alan `SphArea_km`.
- Bilinen sorun: Zip içinde bir üst klasör var (`SIM3292_MarsGlobalGeologicGIS_20M/`). Sıkıştırma yöntemleri 0 ve 8 (Deflate64 yok). Belgede "USGS HEAD isteğine boyut vermez" yazıyor; 13 Kasım'da bu adres HEAD'e boyut VERDİ — yine de kod boyutu indirmeden sonra da kontrol eder. Zip ≈ 0,8 GB (yalnız shapefile gerekli ama zip bütün iner). Lisans: USGS yayını, kamu malı. Atıf (sayfadaki "Suggested citation", aynen): "Tanaka, K.L., Skinner, J.A., Jr., Dohm, J.M., Irwin, R.P., III, Kolb, E.J., Fortezzo, C.M., Platz, T., Michael, G.G., and Hare, T.M., 2014, Geologic map of Mars: U.S. Geological Survey Scientific Investigations Map 3292, scale 1:20,000,000, pamphlet 43 p., https://dx.doi.org/10.3133/sim3292."
- Doğrulandı: evet (13 Kasım 2026, 17:30; ürün sayfası, HEAD, zip merkezi dizini, .dbf başlığı ve kayıtları)

### R3 — TES mineral haritaları 4 ppd, 13 bileşen (Bandfield 2002)
- Sayfa (DOI / ürün sayfası): http://tes.mars.asu.edu/products/ ("MGS-TES Special Products" → "TES Mineral Maps") · makale doi:10.1029/2001JE001510
- Dosyalar: 4 dosya (sayfadaki indirme bağlantıları tes.asu.edu alan adını gösteriyor):
  http://tes.asu.edu/mineral_map/TES_mineral_maps_4_ppd.envi
  http://tes.asu.edu/mineral_map/TES_mineral_maps_4_ppd.envi.hdr
  http://tes.asu.edu/mineral_map/TES_mineral_maps_4_ppd.isis
  http://tes.asu.edu/mineral_map/endmember_list.ascii
- Erişim: **http** (https kesiliyor; belge 10.3)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: .envi 53 913 600 · .envi.hdr 314 · .isis 53 914 624 · endmember_list.ascii 1 105 bayt (HEAD, 13 Kasım). Kontrol: 1440 × 720 × 13 × 4 bayt = 53 913 600 ✓.
- Sağlama: yok (yalnız boyut + fizik testi; belge 17.2)
- Kullanılacak katman/bant/değişken: .envi.hdr'den okundu: samples 1440, lines 720, bands 13, header offset 0, **data type 4 (float32), byte order 1 (big-endian)**, interleave bsq → belgedeki ">f4 big-endian bsq" doğru. **Bant sırası (sayfadaki "13 mineral and error components" listesinin sırası):** 1 Quartz · 2 K-feldspar · 3 Plagioclase · 4 Amphibole · 5 Low-Ca Pyroxene · 6 High-Ca Pyroxene · 7 Olivine · 8 Hematite · 9 Sulfates · 10 Carbonates · 11 Sheet Silicates and High-Si Glass · 12 Surface Dust · 13 RMS Error. Belge D11 ile aynı: bant 3 plajiyoklaz, 5 düşük-Ca piroksen, 6 yüksek-Ca piroksen, 8 hematit, 12 toz, 13 RMS.
- Bilinen sorun: Sayfanın genel "File format descriptions" kısmı ENVI dosyalarını "16-bit integer" diye anlatıyor; **bu dosyanın kendi .hdr'si float32 diyor** — .hdr esas alınır, boyut da float32 ile tutuyor. .hdr'de bant adları yok; sıra yalnız sayfadan bilinir. `endmember_list.ascii` 13 bant değil, haritaları üretmekte kullanılan 36 spektral uç üyenin listesidir (1 Quartz BUR-4120 … 32 Surface Dust …) — bant sırası için kullanılmaz, yalnız belge için. −1 = yok (belge 10.3). .isis aynı veri + ISIS etiketi (yedek). ASU sunucusu bağlantıyı kesebilir (WinError 10054) → tekrar dene. Lisans: sayfada yok (ASU/NASA bilimsel ürün; "açık"). Atıf (sayfanın verdiği): Bandfield (2002), Global mineral distributions on Mars, Journal of Geophysical Research, 10.1029/2001JE001510.
- Doğrulandı: evet (13 Kasım 2026, 17:40; ürün sayfası, HEAD, .envi.hdr içeriği, endmember_list)

### R4 — TES termal eylemsizlik 20 ppd (Putzig 2003, ti_nmap2003.bin) + TES albedo 8 ppd + interpolasyon maskesi
- Sayfa (DOI / ürün sayfası): http://tes.mars.asu.edu/products/ ("TES Thermal Inertia Map" → Putzig; "TES Bolometric Albedo Map") · maske sayfası https://se.psi.edu/inertia/ti2003.html (Putzig/Mellon resmî sayfası, PSI)
- Dosyalar: 4 dosya —
  http://tes.asu.edu/mineral_map/ti_nmap2003.bin (termal eylemsizlik)
  http://tes.asu.edu/mineral_map/global_albedo_8ppd.img · http://tes.asu.edu/mineral_map/global_albedo_8ppd.lbl (albedo)
  https://se.psi.edu/inertia/nmsk2003.bin (interpolasyon maskesi — **maske dosyasının adı bulundu: nmsk2003.bin**; ASU'da yok, ASU'daki ti_mask*.bin adları 404 verdi)
- Erişim: ASU dosyaları **http**; maske https (se.psi.edu)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: ti_nmap2003.bin 51 847 200 bayt (HEAD; = 7200 bayt başlık + 7200 × 3600 × 2) · global_albedo_8ppd.img 16 588 800 (= 2880 × 1440 × 4) · .lbl 2 334 bayt (açılmış metin; ASU sunucusu bu metin dosyasını bazen sıkıştırarak gönderiyor, o zaman HEAD 786 bayt gösterir — ikisi de normal) · nmsk2003.bin: **25 927 200 bayt** — PSI sayfasının kendi biçim tanımından ("7200 x 3600 byte format", "ASCII header 7200 bytes long") hesaplandı: 7200 + 7200 × 3600; sayfadaki "25 MB" ile tutarlı. Sunucudan HEAD ile ölçülemedi (se.psi.edu 13 Kasım'da iki denemede de bizim ağımızdan açılmadı); kod indirmeden sonra bu değerle assert eder.
- Sağlama: yok (yalnız boyut + fizik testi)
- Kullanılacak katman/bant/değişken:
  TI: dosyanın kendi 7200 baytlık metin başlığından okundu — "7200 2-byte integers per record, 3601 records (first is 7200-byte header)", X = 7200 (boylam), Y = 3600 (enlem), no-data 0, min 24, max 800, birim J m⁻² K⁻¹ s⁻½, "Latitudes: -90 to 90", "Longitude: 0 to 360 West". **Bayt sırası big-endian (>i2) — örnek satırda doğrulandı** (BE değerler 39–273, LE anlamsız).
  Albedo: .lbl'den — 2880 × 1440, SAMPLE_TYPE PC_REAL 32 bit (**little-endian float32**), Simple Cylindrical, boylam −180 → 180 doğuya pozitif, enlem 90 → −90.
  Maske: 7200 × 3600 bayt + 7200 baytlık ASCII başlık; 1 = TES verisi, 0 = veri yok ya da interpolasyon.
- Bilinen sorun: **TI ve albedo farklı düzende:** TI boylamı 0–360 batıya, ilk satır güney (−90); albedo −180…180 doğuya, ilk satır kuzey. Albedo little-endian, TI big-endian. PSI sayfasına göre TI 80°G–80°K arasında interpolasyonla doldurulmuş; yalnız gerçek TES verisi istenirse maske ile çarpılır (maske 1 = veri). PSI'daki `nmap2003.bin` ile ASU'daki `ti_nmap2003.bin` aynı harita olmalı (ikisi de 50 MB, aynı başlık) — belgede ASU adı kullanıldığı için ASU'dan indirilir. Lisans: sayfalarda yok. Atıf (dosya başlığı ve PSI sayfası aynı künyeyi istiyor): "Putzig, N. E., M. T. Mellon, K. A. Kretke, and R. E. Arvidson, Global thermal inertia and surface properties of Mars from the MGS mapping mission, Icarus 173, 325-341, 2005." Albedo için sayfa: Christensen et al. (2001), JGR 106, 23,823–23,872 [16].
- Doğrulandı: kısmen (13 Kasım 2026, 17:45; ASU dosyaları evet — HEAD, TI başlığı, bayt sırası, .lbl; maske adı, biçimi ve biçimden hesaplanan boyut PSI sayfasından evet; maske boyutu sunucudan ölçülemedi)

### R5 — TES Dust Cover Index 16 ppd (Ruff & Christensen 2002)
- Sayfa (DOI / ürün sayfası): http://www.mars.asu.edu/~ruff/DCI/dci.html ("TES Dust Cover Index (over MOLA shaded relief)") · ikincil kayıt https://www.mars.asu.edu/data/tes_ruffdust/ · makale doi:10.1029/2001JE001580
- Dosyalar: 1 dosya — **http://www.mars.asu.edu/~ruff/DCI/dci_lo_ice_dust_16ppd_shifted.pds** (sayfadaki "ISIS (PDS) version ~66 Mb" bağlantısı). **Doğrulandı:** canlı sayfa bizim ağımızdan açılmadığı için sayfanın Internet Archive kopyası (8 Temmuz 2024) okundu; bağlantı göreli adres olarak `/~ruff/DCI/dci_lo_ice_dust_16ppd_shifted.pds` (klasör `DQ/` değil `DCI/`). Aynı sayfadaki diğer sürümler: `.vicar`, `.raw` (~66 Mb), `.tif`, `.png`, `.jpg`, `_mola.tif/.jpg` — kullanılmaz. **Yedek kaynak (ASU açılmazsa):** arşivdeki birebir kopya https://web.archive.org/web/2024id_/http://www.mars.asu.edu/~ruff/DCI/dci_lo_ice_dust_16ppd_shifted.pds (Range 206 ile çalışıyor).
- Erişim: http (ASU; https kesiliyor/açılmıyor)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: **66 356 224 bayt** (arşiv kopyasında Content-Range ile ölçüldü; biçimden hesaplanan 1024 + 5760 × 2880 × 4 ile birebir aynı; sayfada "~66 Mb").
- Sağlama: yok (yalnız boyut + fizik testi)
- Kullanılacak katman/bant/değişken: dosyanın kendi PDS etiketinden (ilk 1024 bayt, arşiv kopyasından okundu): RECORD_BYTES 512, LABEL_RECORDS 2 (→ etiket 1024 bayt, veri 1025. bayttan başlar), QUBE, AXES (BAND,SAMPLE,LINE), CORE_ITEMS (1,5760,2880), CORE_ITEM_BYTES 4, **CORE_ITEM_TYPE PC_REAL (little-endian float32)**, CORE_BASE 0,0, CORE_MULTIPLIER 1,0 — belgedeki "1024 bayt etiket, 5760 × 2880 <f4" ile aynı. İkincil kayda göre Simple cylindrical, boylam −180 → 180 doğu, enlem 90 → −90 (üst = kuzey). Değer = 1350–1400 cm⁻¹ ortalama yayınım; düşük değer = ince toz.
- Bilinen sorun: 0,85 = yok (belgelenmemiş, veriden; belge 10.3) — sayfa veri-yok değerini vermiyor (etikette de yok) → veriden assert edilir; bayt sırası etiketten doğrulandı (PC_REAL). Sayfa aynı veriyi TIF, PNG, JPG, VICAR, RAW olarak da sunuyor; renkli TIF/JPG/PNG sayısal değildir, KULLANILMAZ. Sürüm: su buzu bulut opaklığı > 0,07 ve toz opaklığı > 0,29 olan spektrumlar hariç tutulmuş 16 ppd sürüm (sayfa). ASU sunucusu kararsız → ayrı ve tekrar denemeli indirilir. Lisans: sayfada yok. Atıf (sayfa bu makaleyi istiyor; künye ikincil kayıttan): "Ruff, S.W., and P.R. Christensen, Bright and dark regions on Mars: Particle size and mineralogical characteristics based on Thermal Emission Spectrometer data, J. Geophys. Res., 107, DOI10.1029/2001JE001580, 2002."
- Doğrulandı: evet, arşiv üzerinden (13 Kasım 2026, 16:40; dci.html'in 8 Temmuz 2024 arşiv kopyasındaki bağlantı + dosyanın arşiv kopyasının boyutu ve PDS etiketi). Canlı www.mars.asu.edu sunucusu bizim ağımızdan açılmadı; İrem'in ağında açılırsa canlı adres kullanılır, açılmazsa yedek adres.

### R6 — Mars Odyssey GRS, yumuşatılmış 5° × 5° (H₂O, Fe, Si, K, Th, Cl)
- Sayfa (DOI / ürün sayfası): PDS3 veri seti ODY-M-GRS-5-ELEMENTS-V1.0 ("ODY MARS GAMMA RAY SPECTROMETER 5 ELEMENT CONCENTRATION V1.0") · arşiv kökü https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/
- Dosyalar: 12 dosya (6 element × .tab + .lbl), klasör https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/odgm_xxxx/data/smoothed/ — **belgedeki "data/smoothed/" yolunun başında `odgm_xxxx/` klasörü var:**
  h2o_sr_5x5.{tab,lbl} · fe_sr_5x5.{tab,lbl} · si_sr_5x5.{tab,lbl} · k_sr_5x5.{tab,lbl} · th_sr_5x5.{tab,lbl} · cl_sr_5x5.{tab,lbl}
  (aynı klasördeki `kvsth_sr_5x5.*` ve PDS4 `.xml` etiketleri İNDİRİLMEZ; .lbl yeterli)
- Erişim: doğrudan https (klasör listesi)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: h2o/fe/si/cl .tab 186 624 bayt · k/th .tab 171 072 bayt · .lbl: h2o 4 653, fe 4 647, si 4 665, k 4 642, th 4 645, cl 4 649 bayt (klasör listesi). h2o.tab = 2 592 satır × 72 bayt (36 × 72 hücre, 5°).
- Sağlama: üreticinin MD5 listesi — **dosya adı `odgm_xxxx_130911.md5`** (belgedeki "ody-m-grs-5-elements-v1.md5" adı yok): https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/odgm_xxxx_130911.md5 (7 079 bayt). Anahtarlar `odgm_xxxx\data\smoothed\…` biçiminde (ters eğik çizgi). 12/12 değer: h2o .tab `C6B4A8F9387B886EE99EF2F518D5ABE8` .lbl `595A0199FA7C6C0CEBE343235100532F` · fe .tab `FA90A7E62F40BB81BB893524471E2156` .lbl `3BA2FEF040DA91F1F618C0FEAD4B51D0` · si .tab `F24A42FA2C11FEC04D59D4B5FAB20F3F` .lbl `DA4B22AC036EBCD69ADB622B7AD5E06B` · k .tab `06A60428199F8915F6769E51CAFED9EA` .lbl `9AE05D831F4812C473987423B25CFE17` · th .tab `70A7FD2E68CFF9AE9D907B57F1A3BDE4` .lbl `58DD0E5E128BE96AEC8E9A08C86B8363` · cl .tab `6419661A648F4B9D18789B3B86B8BE1D` .lbl `0839F9C3DF458127A12B735A362A8441`
- Kullanılacak katman/bant/değişken: ASCII tablo, 5 sütun: `LATITUDE` (5° hücre merkezi), `LONGITUDE` (hücre merkezi), `CONCENTRATION`, … (etiketten). Veri 2°'lik ham değerlerden 10° kayan kutu ile yumuşatılıp 5°'ye yeniden gruplanmış (etiket açıklaması). Çapraz kontrol içindir, puana girmez.
- Bilinen sorun: 9999,999 = yok; boylam doğuya; H₂O yalnız 57,5°G–57,5°K (belge 10.3) — dosyadan assert edilir. K ve Th tabloları farklı satır uzunluğunda (171 072 bayt) — sütunlar etiketteki START_BYTE'a göre okunmalı. Gözlem dönemi 2002-06-04 → 2005-04-03, ürün sürümü 2.0. Lisans: NASA PDS, kamuya açık. Atıf: Boynton, W.V. et al. (2007), Concentration of H, Si, Cl, K, Fe, and Th in the low- and mid-latitude regions of Mars, J. Geophys. Res. 112, E12S99 [150] — arşivde hazır künye satırı aranmadı ("açık").
- Doğrulandı: evet (13 Kasım 2026, 17:58; klasör listeleri, MD5 listesi, h2o .lbl)

### R7 — SWIM4MIM Ci 0–1 m (+ 1–5 m, > 5 m bilgi için)
- Sayfa (DOI / ürün sayfası): https://swim.psi.edu/SWIM4MIMProducts.php ("SWIM4MIM Data Products and Results", PSI) — "Combined Ice Consistency Map (0-1 m)", son güncelleme 2025-08-04 12:32:04
- Dosyalar: 3 dosya —
  https://swim.psi.edu/output/SWIM4MIM/Global/Composite/SWIM4MIM_Ci_0_1.tif (asıl kullanılan)
  https://swim.psi.edu/output/SWIM4MIM/Global/Composite/SWIM4MIM_Ci_1_5.tif · https://swim.psi.edu/output/SWIM4MIM/Global/Composite/SWIM4MIM_Ci_5.tif (bilgi için)
  Not: Sayfa dosyaları onay kutulu bir indirme formuyla veriyor (doğrudan bağlantı yalnız *_Browse.png için); yukarıdaki doğrudan adresler 13 Kasım'da HEAD ve Range ile 200/206 döndü, yani form kullanmadan inebiliyor.
- Erişim: doğrudan https
- Giriş gerekiyor mu: hayır
- Beklenen boyut: SWIM4MIM_Ci_0_1.tif 70 995 807 · SWIM4MIM_Ci_1_5.tif 70 995 807 · SWIM4MIM_Ci_5.tif 70 995 794 bayt (HEAD, 13 Kasım)
- Sağlama: yok (yalnız boyut + fizik testi)
- Kullanılacak katman/bant/değişken: Ci_0_1.tif'in TIFF başlığından okundu: 7200 × 2400, tek bant, 32 bit float (SampleFormat 3), sıkıştırmasız, 128 × 128 karo; **GeoTIFF etiketleri var** (ModelPixelScale, ModelTiepoint, GeoKeyDirectory); **GDAL_NODATA = "-30"** (belgedeki −30 = yok ile aynı). Değer −1…+1 tutarlılık indeksi (olasılık değil).
- Bilinen sorun: Sunucu ara ara HTTP 522 verir → artan beklemeyle tekrar (belge 17.2). Klasik TIFF (BigTIFF değil). 20 ppd, 60°G–60°K (belge 10.3; 2400 satır / 20 = 120° ile tutarlı). Sayfada aynı satır için "TIFF" (browse) ve "GeoTIFF" seçenekleri ayrı; doğrudan adresteki dosya GeoTIFF etiketli olduğu için doğru dosya. Lisans: sayfada yok. Atıf: sayfa ürünleri "Morgan and Putzig et al. [2025]"e dayandırıyor; hazır künye satırı yok → belgedeki [111] (SWIM4MIM Data Products, 2025), [72] Morgan ve ark., [85] Perry ve ark. kullanılır.
- Doğrulandı: evet (13 Kasım 2026, 18:05; ürün sayfası, HEAD, Range, TIFF başlığı)

## Ek bölümler (Bölüm 16.3)

### 1. Earthdata
Earthdata girişi (`_netrc`) yalnız şu 4 set için gerekir; diğer 20 set girişsiz iner. Hesap bilgisi bu raporda yoktur. Arama küreseldir (bounding box verilmez). Bütün granüller LP DAAC bulutunda (`data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/…`); arama adresi CMR (cmr.earthdata.nasa.gov) girişsiz çalışıyor, indirme girişli.

| Set | short_name | version | temporal | Beklenen granül | Not |
|---|---|---|---|---|---|
| E2 | MCD12C1 | 061 | 2023-01-01 → 2023-12-31 | 1 | HDF4 |
| E4 | AG5KMMOH | 041 | 2015-01-01 → 2015-12-31 | 12 | HDF5 (.h5) |
| E5 | MYD11C3 | 061 | 2023-01-01 → 2023-12-31 | 12 | Aqua (MYD), HDF4 |
| E6 | MCD43C3 | 061 | 2023 + ad süzgeci `MCD43C3.A2023{DDD}.*`, DDD ∈ {015, 046, 074, 105, 135, 166, 196, 227, 258, 288, 319, 349} | 12 | Tarih aramasıyla değil adla seç (her granül 16 günlük pencere) |

Örnek: `earthaccess.search_data(short_name="MYD11C3", version="061", temporal=("2023-01-01","2023-12-31"))`. Sayılar 13 Kasım'da CMR'de sınandı (hits: 1, 12, 12, 12/12).

### 2. Toplam
| Grup | Dosya sayısı | Yaklaşık boyut |
|---|---|---|
| Dünya (E1–E10) | 334 | ≈ 15,8 GB (E3 GLiM ≈ 1,14 GB dahil) |
| Ay (M1–M7) | 45 | ≈ 17,4 GB |
| Mars (R1–R7) | 30 | ≈ 3,4 GB |
| **Toplam** | **409** | **≈ 36,5 GB** |

Dosya sayısına etiket, md5 ve checksum dosyaları dahildir. Earthdata boyutları CMR değeridir (MB = 10⁶ bayt alındı). Zipler açılınca ek yer gerekir: E7 permafrost tif'i tek başına ≈ 1,9 GB, M2 GeoUnits.shp ≈ 0,13 GB. Belgedeki "ham veri yaklaşık 45 GB" tahmini bu toplamın üstünde; 80 GB boş disk hedefi yeterli.

En büyük dosyalar: M1 LOLA 8,49 GB · M3 GHRM 2 × 3,30 GB · E1 ETOPO 288 dosya toplam 5,23 GB · E4 ASTER 12 × 0,32 GB · E6 MCD43C3 12 × ≈ 0,2 GB · R1 MOLA 2,13 GB.

### 3. Sıralama önerisi (en fazla 4 eşzamanlı indirme, belge 17.2)
1. **Önce, paralel (büyük ve kararlı):** M1 LOLA (8,5 GB, S3) · M3 GHRM ra_sam + tbol_sam (2 × 3,3 GB) · E1 ETOPO (288 dosya; kendi içinde sırayla) · E4 ASTER (Earthdata, 12 dosya).
2. **Sonra, paralel:** E6 MCD43C3 · E2 MCD12C1 · E5 MYD11C3 (Earthdata) · R1 MOLA (2,1 GB) · M4 PRP + GCP (1,8 GB) · R2 SIM 3292 (0,8 GB) · E9 Aridity (0,65 GB) · E10 SoilGrids · M2 · E7 · E8 · M5 · M6 · M7 · R6 (+ M3/M4 md5 listesi 45 MB).
3. **Ayrı, kararsız sunucular (tek tek, tekrar denemeli):** R7 SWIM (HTTP 522) · R3, R4 (ASU, http, bağlantı kesilebilir) · R5 DCI (ASU; açılmazsa arşivdeki yedek adres) · R4 maskesi (se.psi.edu) · E3 GLiM (Dropbox).

### 4. Lisanslar (sayfalardan)
| Set | Lisans |
|---|---|
| E1 ETOPO | CC0 1.0 (data.gov kaydı) |
| E2, E4, E5, E6 (LP DAAC) | EOSDIS Data Use Policy — kısıtsız açık veri |
| E3 GLiM | Sayfada yok — "açık" (belge CC BY diyor, doğrulanamadı) |
| E7 Permafrost kuzey | CC-BY-3.0 |
| E8 Permafrost Antarktika | CC-BY-4.0 |
| E9 Aridity Index | CC BY 4.0 (sayfanın eski metni "non-commercial use" da diyor) |
| E10 SoilGrids | CC BY 4.0 |
| M1 LOLA | Access: public domain; Use: "Please cite authors" |
| M2 Ay jeoloji | "CC0, but please cite authors" |
| M3, M4 Diviner · M5, M6 Lunar Prospector · R6 Odyssey GRS | NASA PDS, kamuya açık (M5 data.gov: public domain) |
| M7 PGDA | NASA, kamuya açık (sayfada ayrı metin yok) |
| R1 MOLA | CC0 (public domain); Use: None |
| R2 SIM 3292 | USGS yayını, kamu malı |
| R3, R4, R5 (ASU/PSI) | Sayfalarda lisans yok — "açık" |
| R7 SWIM4MIM | Sayfada lisans yok — "açık" |

### 5. Literatür künyeleri ("How to cite")
"Aynen" yazanlar sayfadaki önerilen atıf metnidir; diğerleri sayfanın künye alanlarından ya da sayfanın gösterdiği makaleden kurulmuştur (sayfada hazır metin yok).
- **E1 (aynen):** NOAA National Centers for Environmental Information. 2022: ETOPO 2022 15 Arc-Second Global Relief Model. NOAA National Centers for Environmental Information. DOI: 10.25921/fd45-gt74. Accessed [date].
- **E2 (aynen):** Friedl, Mark, & Sulla-Menashe, Damien. (2022). MODIS/Terra+Aqua Land Cover Type Yearly L3 Global 0.05Deg CMG V061 [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MCD12C1.061 Date Accessed: 2026-11-13
- **E3 (makale):** Hartmann, J., Moosdorf, N. (2012): The new global lithological map database GLiM: A representation of rock properties at the Earth surface. Geochemistry, Geophysics, Geosystems, 13, Q12004, doi:10.1029/2012GC004370.
- **E4 (aynen):** NASA JPL. (2016). ASTER Global Emissivity Dataset, Monthly, 0.05 deg, HDF5 [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/COMMUNITY/ASTER_GED/AG5KMMOH.041 Date Accessed: 2026-11-13
- **E5 (aynen):** Wan, Zhengming, Hook, Simon, & Hulley, Glynn. (2021). MODIS/Aqua Land Surface Temperature/Emissivity Monthly L3 Global 0.05Deg CMG V061 [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MYD11C3.061 Date Accessed: 2026-11-13
- **E6 (aynen):** Schaaf, Crystal, & Wang, Zhuosen. (2021). MODIS/Terra+Aqua BRDF/Albedo Albedo Daily L3 Global 0.05Deg CMG V061 [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MODIS/MCD43C3.061 Date Accessed: 2026-11-13
- **E7 (aynen):** Obu, Jaroslav; Westermann, Sebastian; Kääb, Andreas; Bartsch, Annett (2018): Ground Temperature Map, 2000-2016, Northern Hemisphere Permafrost [dataset]. Alfred Wegener Institute, Helmholtz Centre for Polar and Marine Research, Bremerhaven, PANGAEA, https://doi.org/10.1594/PANGAEA.888600
- **E8 (aynen):** Obu, Jaroslav; Westermann, Sebastian; Kääb, Andreas; Bartsch, Annett (2019): Ground Temperature Map, 2000-2017, Antarctic [dataset]. University of Oslo, PANGAEA, https://doi.org/10.1594/PANGAEA.902576
- **E9 (aynen):** Zomer, Robert; Trabucco, Antonio (2019). Global Aridity Index and Potential Evapotranspiration (ET0) Database: Version 3.1. figshare. Dataset. https://doi.org/10.6084/m9.figshare.7504448.v7
- **E10 (ISRIC FAQ'deki künye):** Poggio, L., de Sousa, L. M., Batjes, N. H., Heuvelink, G. B. M., Kempen, B., Ribeiro, E., and Rossiter, D.: SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty, SOIL, 7, 217–240, 2021.
- **M1 (künye alanlarından):** LOLA Science Team (2014). Moon LRO LOLA DEM 118m. Goddard Space Flight Center; USGS Astrogeology Science Center, Edition March 11, 2014. https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m
- **M2 (künye alanlarından):** Fortezzo, C.M., Spudis, P.D., Harrel, S.L. (2020). Unified Geologic Map of the Moon, 1:5M, 2020, Edition 2.0. USGS Astrogeology Science Center. https://astrogeology.usgs.gov/search/map/unified_geologic_map_of_the_moon_1_5m_2020
- **M3, M4 (bundle künyesi):** Paige, D.; Sullivan, M.; Williams, J-P. (2022). Lunar Reconnaissance Orbiter Diviner Derived Data Bundle 1, v5.0. NASA Planetary Data System. https://doi.org/10.17189/wj0s-w188 (+ GCP için Williams et al. 2017, PRP için Paige et al. 2010)
- **M5 (aynen, CITATION_DESC):** Prettyman, T.H., Lunar Prospector GRS Elemental Abundance, LP-L-GRS-5-ELEM-ABUNDANCE-V1.0, NASA Planetary Data System, 2012.
- **M6 (dosya başlığının gösterdiği makale):** Feldman, W.C. et al. (2001), Evidence for water ice near the lunar poles, J. Geophys. Res. 106(E10), 23231–23251.
- **M7 (sayfanın istediği, aynen):** Mazarico, E., et al. (2011), Illumination conditions of the lunar polar regions using LOLA topography, Icarus, Vol. 211, pp. 1066-1081, doi:10.1016/j.icarus.2010.10.030.
- **R1 (künye alanlarından):** MOLA Team. Mars MGS MOLA DEM 463m. Goddard Space Flight Center; USGS Astrogeology Science Center, Edition 2003-03-21. https://astrogeology.usgs.gov/search/map/mars_mgs_mola_dem_463m
- **R2 (aynen, "Suggested citation"):** Tanaka, K.L., Skinner, J.A., Jr., Dohm, J.M., Irwin, R.P., III, Kolb, E.J., Fortezzo, C.M., Platz, T., Michael, G.G., and Hare, T.M., 2014, Geologic map of Mars: U.S. Geological Survey Scientific Investigations Map 3292, scale 1:20,000,000, pamphlet 43 p., https://dx.doi.org/10.3133/sim3292 .
- **R3 (sayfanın verdiği):** Bandfield (2002), Global mineral distributions on Mars, Journal of Geophysical Research, 10.1029/2001JE001510.
- **R4 TI (aynen, dosya başlığı ve PSI sayfası):** Putzig, N. E., M. T. Mellon, K. A. Kretke, and R. E. Arvidson, Global thermal inertia and surface properties of Mars from the MGS mapping mission, Icarus 173, 325-341, 2005. · **R4 albedo (sayfanın verdiği):** Christensen et al. (2001), Mars Global Surveyor Thermal Emission Spectrometer experiment: Investigation description and surface science results, Journal of Geophysical Research, 106, pp. 23,823 - 23,872.
- **R5 (sayfanın istediği makale):** Ruff, S.W., and P.R. Christensen, Bright and dark regions on Mars: Particle size and mineralogical characteristics based on Thermal Emission Spectrometer data, J. Geophys. Res., 107, DOI10.1029/2001JE001580, 2002.
- **R6 (makale):** Boynton, W.V. et al. (2007), Concentration of H, Si, Cl, K, Fe, and Th in the low- and mid-latitude regions of Mars, J. Geophys. Res. 112, E12S99.
- **R7:** Sayfada hazır künye yok; ürünler "Morgan and Putzig et al. [2025]"e dayanıyor → belgedeki [111], [72], [85].


## B. Ultimate veri ve analog eki (13 Kasım 2026; 20:45'te gözden geçirmeye göre güncellendi)

Bu ek, 24 setin indirme bloklarına (yukarıda) dokunmaz. Puan formülü, 8 kategori, ağırlık tablosu, kapılar ve ayar.json **değişmez**. Bu ekteki hiçbir şey puana girmez.

### B0. Karar özeti (ekip gözden geçirmesi, 13 Kasım 20:35)

| Madde | Karar | Ne zaman / nasıl |
|---|---|---|
| Artemis etiketi (B5) | **Alındı** | Site ve sunumda "Artemis III'ün iniş bölgeleri" denmez. Etiket: "Artemis III candidate regions (Oct 2024) — first landing now planned as Artemis IV" |
| Artemis koordinatları (B5) | **Alındı** | Sitede "approximate centre" etiketiyle |
| B2 tek "Analog sites" sayfası, 3 sekme, her sahanın tek adresi | **Alındı** | v1.2.1 güncellemesi, D6'dan önce kilitlenir |
| B4 gelecek görev sahaları | **Alındı** | Koordinat kalite etiketi (K1/K2) sitede gösterilir; K3 sahalar haritada iğne değil, yalnız metin; her cümlenin yanında kaynak bağlantısı |
| B1.3 Known / Near / New candidate etiketleri | **Alındı** | 20 km ve 100 km eşikleri sonuçlara bakılmadan, D8'den önce ayar.json'a yazılır |
| B1.1 partner DEM kontrolü (X1–X3) | **Bu koşuda yapılmaz** | Yerine tek cümle (B1.1) |
| B1.2 mağaralar | **Yalnız Mars (MGC3), isteğe bağlı** | 15 Kasım sabahı, site bittikten sonra vakit kalırsa. Ay çukur atlası ve Dünya "lav tüpü kayacı" etiketi alınmaz |
| X1, X2, X3, X5, X6 | **İndirilmez** | Bloklar yalnız bilgi ve sonraki çalışma için duruyor |

**v1.2.1 güncellemesi** (belge → ayar.json → kod sırasıyla; D6 ve D8'den önce kilitlenir):
1. Artemis etiketi. Belgede değişecek yerler:

   | Belgede nerede | Ne değişiyor |
   |---|---|
   | Bölüm 0 tablosu (D3 satırı) | Artemis notu |
   | Bölüm 1.1 | Artemis ifadesi |
   | Bölüm 9.1 başlığı ve paragrafı | Etiket: "Artemis III candidate regions (Oct 2024) — first landing now planned as Artemis IV" |
   | Bölüm 13.1 güçlü yanlar tablosu | Artemis ifadesi |
   | Bölüm 17.6 site tablosu | Target search satırındaki Artemis ifadesi |

   Geçmiş bir çalışmanın adı olarak geçen "Artemis III EVA" ve "Artemis III iniş yeri çalışması" atıfları (Görev tanımları ve ağırlık gerekçesi) olduğu gibi kalabilir.
2. Bölüm 17.6: Analog sites sekmeleri ve analog.json alanları (B2).
3. Bölüm 8.4 parametre tablosu: 20 km ve 100 km eşikleri eklenir, oradan ayar.json'a yazılır (B1.3).

### B1. Üç sorunun cevabı

#### B1.1 Kanada, Avrupa ve Japonya verisi: aynı bağlam için ikinci set ne olacak?

Kısa cevap: **Puana da ağırlığa da girmez, bu koşuda kontrol olarak da kullanılmaz.** Ayırt etme ya da ağırlık sorunu hiç doğmaz, metodoloji değişmez.

- Her kategori için belgede (Bölüm 10) tek bir birincil set var ve puanı yalnız o üretir. Aynı bilgiyi taşıyan ikinci bir set çift sayım yaratır. Ağırlığı bölmek ağırlık tablosunu, set değiştirmek de yüzdelik kalibrasyonunu ve V1–V10'u değiştirir.
- İlk öneri, partner yükseklik haritalarıyla (Copernicus, HRSC–MOLA, SLDEM2015) bağımsız bir kontrol yapmaktı. **Gözden geçirmede bu koşudan çıkarıldı.** Dört neden:
  1. **Dünya kontrolü bağımsız değil.** ETOPO 2022'nin yayımlanmış makalesindeki (ESSD 2025) kaynak tablosuna göre, **bütün ızgaranın** ("% total coverage, surface") ~%10,6'sı Copernicus DEM'den, ~%23,3'ü de Copernicus'tan türetilen FABDEM'den geliyor. Deniz tabanı için kullanılan GEBCO'nun payı ~%58,8. Yani Copernicus ve FABDEM birlikte ızgaranın ~%34'ünü, **kara piksellerinin büyük kısmını** oluşturuyor. Kontrolü ekip arkadaşı makaledeki tablodan yaptı.
  2. **İki harita farklı şeyi ölçüyor.** Copernicus binaları ve ağaçları içeren bir yüzey modeli. ETOPO ise ağaçların ve binaların çıkarıldığı çıplak yer yüzeyini kullanıyor. Fark çıkması kaçınılmaz.
  3. **Yanlış alarm riski.** ε* bir en kötü durum sınırı; çözünürlükleri farklı iki haritanın farkı neredeyse her yerde onu aşar. Adayların çoğu "differs" görünür ve yöntem olduğundan zayıf görünür.
  4. **Büyük indirme, az katkı.** Mars harmanı 11 GB ve MOLA'yı zaten içeriyor. SLDEM2015 22 GB ve Artemis bölgelerini kapsamıyor.
- **Jüriye gösterilecek tek cümle** (ek iş gerektirmez): "ETOPO 2022 incorporates ESA's Copernicus DEM." Kanada'nın katkısı veri seti olarak değil, analog saha ve eğitim ortaklığı olarak gösterilir (B4: Haughton, Kamestastin, Pavilion Lake).

#### B1.2 Mağaralar: 8 saatlik eşleştirmeye nasıl girecek, 20×20 km pencere mi olacak?

Kısa cevap: **Pencere ya da patch olmaz, eşleştirmeye de girmez.** Gerekirse koşudan sonra bir etiket olarak eklenir.

Neden pencere olmaz:
- Mağara girişleri 10–300 m boyutunda (LROC; MGC3 ~25 m'ye kadar).
- DEM'lerimiz bunları göremez: Ay 118 m, Mars 463 m, Dünya ~450 m.
- 9. kategori yapmak ağırlıkları, yani metodolojiyi değiştirir.

Ne yapılır (gözden geçirmeden sonra):
- **Yalnız Mars, isteğe bağlı:** MGC3 kataloğu (X4, ~1,8 MB) indirilir. Mars hedef pencerelerinin içine düşen mağara adayı noktaları sayılır, sitede "Cave candidates in window: N (not part of the score)" diye gösterilir. Birkaç saniye sürer. **15 Kasım sabahı, site bittikten sonra vakit kalırsa yapılır.** Yetişmezse hiçbir şey eksik kalmaz.
- **Ay:** Atlasın indirme adresi bulunamadı, atlanır.
- **Dünya:** "Lav tüpü olabilecek kayaç" etiketi **alınmaz.** GLiM'deki bazik volkanik sınıf çok geniş alanları kapsıyor; etiket neredeyse her volkanik bölgede çıkar ve bir şey söylemez. WOKAM da alınmaz (karst, lav tüpünün analoğu değil).

#### B1.3 Doğruluğunu kanıtlayamayacağımız yeni adayları nasıl öne çıkarırız?

Kısa cevap: **"Keşif" diye değil, "kanıtlı hipotez" diye sunulur.**

Her yeni aday, zaten üretilen çıktılardan bir **kanıt paketi** ile gösterilir:
1. Yüzdelik sırası (P) ve kaç kategoride güçlü olduğu.
2. DEM gürültüsüne dayanıklılık (ε*, P6).
3. Duyarlılık (Kendall τb, Jaccard).
4. "Yenilik" ölçüsü: En yakın bilinen analog sahaya (B3 + B4) uzaklık. Puana girmez.

Etiketler:
- `Known analog`: Bilinen bir sahaya < 20 km.
- `Near known analog`: 20–100 km.
- `New candidate — field check suggested`: > 100 km.

**20 ve 100 km eşikleri sonuçlara bakılmadan, D8 sabitlemesinden önce ayar.json'a yazılır** (v1.2.1).

"Yöntem bilinen analogları buluyor" cümlesi **yalnız V1 testi gerçekten iyi çıkarsa** kullanılır. V1 zayıf çıkarsa site ve makale bunu aynı biçimde gösterir (belge 17.6: "iyi ya da kötü aynı biçimde"), yeni adaylar da yalnız etiket ve kanıt paketiyle sunulur.

Sitede tek cümle: "These are ranked hypotheses for field testing, not confirmed analogs."

### B2. Site: "Analog sites" karışıklığının çözümü

Sorun: Sağ üstteki "Analog sites" menüsü ile arama çubuğunda çıkan analog sonuçları aynı sahaları gösteriyor, ama farklı sayfalar açıyor. Kullanıcı aynı sahanın iki ayrı sayfası olduğunu sanıyor.

Çözüm: **Bir saha = bir kalıcı adres.**
1. Tek bir sayfa olur: `analogs.html` (menüde adı yine "Analog sites"). Sayfada üç sekme bulunur:
   - **Validation analogs:** NASA'nın 11 eğitim çifti (belge 9.3, B3). Yöntemin sınandığı sahalar.
   - **Mission-prep analogs:** Gelecek görevler için kullanılan sahalar (B4).
   - **Orbitrary new candidates:** Bizim önerilerimiz (B1.3).
2. Her sahanın tek bir adresi olur: `analogs.html#<kimlik>` (ör. `#v-ries`, `#m-haughton`, `#c-001`). **Menü, arama çubuğu ve Target search içindeki bağlantıların hepsi bu adrese gider.** Başka bir saha sayfası olmaz.
3. Arama sonuçları türe göre gruplanır ve renkli bir etiket taşır: Validation / Mission-prep / Candidate / Target. Hedefler (Apollo, Artemis, Mars iniş yerleri) Target search'te kalır. Hedef sayfasındaki "Known analogs" kutusu kopya içerik göstermez, `analogs.html#…` adresine bağlantı verir.
4. Listeler **ayrıktır**: Bir saha iki sekmede birden bulunamaz. B3 ile B4 bu raporda ayrık tutuldu ve kontrol edildi.
5. Veri: `analog.json` dosyasının her kaydına şu alanlar eklenir:
   - `tur`: `"validation"` | `"mission_prep"` | `"candidate"`
   - `id`
   - `hedef_id`
   - `enlem`, `boylam`
   - `nasa_ne_yapti`
   - `kaynaklar[]`

   Bu, belgede şeması verilmiş bir dosyaya alan ekler. Alan adları D6'da kilitlenmeden önce eklenmeli (ekip onayı).

### B3. Analog listesi A — yöntemi test etmek için (doğrulama, V1)

Bu liste **belgenin 9.3 bölümüdür ve değişmez.** Sonuçlara bakılmadan sabitlenmiştir. B4'teki hiçbir saha bu listede yer almaz.

| # | Hedef | Dünya sahası (enlem, boylam) | Görev | Kaynak (belgeden) |
|---|---|---|---|---|
| 1 | Apollo 15 | Rio Grande Gorge, Taos, NM (36.47611, −105.73222) | Geology | NASA History; BLM 2021 |
| 2 | Apollo 14 | Nördlinger Ries, Almanya (48.8833, 10.6167) | Geology | NASA ALSJ, Ries gezisi 10–15 Ağustos 1970; Phinney, NASA SP-2015-626 |
| 3 | Apollo 16 | Sudbury, Ontario (46.600, −81.183) | Geology | NASA History; GSA 2008 |
| 4 | Apollo 17 | Sudbury | Geology | CBC 2021 |
| 5 | Ay güney kutbu test noktası | SP Crater, AZ (35.58223, −111.63182) | Mobility test | JETT3, 3–11 Ekim 2022 (NTRS 20230000146); JETT5, 13–17 Mayıs 2024 (NTRS 20250000177) |
| 6 | Mars Pathfinder | Ephrata fanı, WA (47.318, −119.553) | General | Golombek ve ark. 1999 |
| 7 | Gale | Dumont Dunes, Mojave (35.67863, −116.23156) | Mobility test | JPL, 11 Mayıs 2012 (Scarecrow) |
| 8 | Apollo 15 | Kilbourne Hole, NM (31.97194, −106.96472) | Geology | BLM 2021 |
| 9 | Apollo 16 | Rio Grande Gorge | Geology | NASA History (Taos, Eylül 1971) |
| 10 | Apollo 17 | Lunar Crater Volcanic Field, NV (38.40, −116.05) | Geology | Phinney, NASA SP-2015-626 |
| 11 | Ay güney kutbu test noktası | Kilbourne Hole | Mobility test | JETT1 (NTRS 20220015570) |

### B4. Analog listesi B — gelecek görevler için (görev hazırlığı)

Bu listedeki sahalar **puana ve V1'e girmez.** Sitede "Mission-prep analogs" sekmesinde ve "yenilik" uzaklığında (B1.3) kullanılır.

Sitede gösterim kuralları (gözden geçirme):
- Her sahanın koordinat kalitesi (K1/K2) yanında yazılır.
- K3 sahalar haritada iğneyle gösterilmez, yalnız metinde geçer.
- Tarihler ve astronot adları tek tek ikinci kez doğrulanmadı. Sitede her cümlenin yanında kaynak bağlantısı bulunur (B8'deki numaralar).
- "Yenilik" uzaklığı yalnız K1/K2 koordinatlı sahalarla hesaplanır.

Koordinat kalitesi şöyle işaretlendi:
- **K1:** Bilimsel ya da resmî kaynakta yazan koordinat.
- **K2:** İkincil kaynak (tabela, gezi sitesi vb.).
- **K3:** Bulunamadı, doğrulanmadı.

Bu listede kullanılan koordinatlar V1 sahalarına 20 km'den uzak. En yakın çift Black Point–SP Crater (~27 km, aynı volkan sahası). Koordinatı K3 olan İzlanda ve Mistastin'in hiçbir V1 sahasıyla ilgisi yok.

#### Ay için

**M-01 Haughton Krateri, Devon Adası, Nunavut (Kanada)** — 75.3667, −89.6833 (75°22′K 89°41′B; K1, NTRS 20110008151)
- Gelecek hedef: Artemis güney kutup bölgeleri (çarpma krateri, donmuş zemin). Haughton 20 km çapında, Shackleton 19 km.
- NASA ne yaptı, nerede, nasıl:
  - **10 Temmuz–3 Ağustos 2007:** NASA Ames'in iki K10 gezgini, krater içindeki ~700 m × 700 m'lik "Drill Hill" bölgesini lidar ve yere nüfuz eden radarla (CRUX GPR) taradı. HMP üs kampı "Ay üssü" rolünü, JSC ise yer kontrolünü üstlendi.
  - **HMP-2010:** Shackleton'dan Malapert'e uzanan bir robotik konvoyun (uzunluk kaynaklarda farklı: NASA blogunda ~75 mil, bir haber sitesinde 120 mil) simülasyonu yapıldı (K10 gezgini + MARS-1 Humvee "basınçlı gezgin" rolünde). Haughton-Mars Projesi 1997'den beri sürüyor (Mars Institute / SETI, NASA ve CSA desteği).
- Kaynaklar: NTRS 20110008151 · Fong, "2007 Haughton Crater Field Test" (NASA Ames) · blogs.nasa.gov/analogsfieldtesting · spacenews.com (HMP-2010)

**M-02 Meteor Crater (Barringer), Arizona** — 35.0328, −111.0211 (35°01.967′K 111°01.267′B; K2, ziyaretçi merkezindeki tarihî tabela, HMdb)
- Gelecek hedef: Basit çarpma kraterleri, Artemis jeoloji eğitimi.
- NASA ne yaptı: **1963–1970** arasında Apollo astronotları burada eğitildi; eğitimleri Eugene Shoemaker verdi. Bir astronotun giysisinin kayada yırtılması, giysinin iyileştirilmesine yol açtı. USGS bunu hâlâ bir analog saha olarak anlatıyor. Krater 1,2 km çapında ve 180 m derinliğinde.
- Kaynaklar: USGS Astrogeology "Meteor Crater Sample Collection" · HMdb tabela 161618 · IAC-21 (Osinski, Artemis için Meteor Crater + Mistastin önerisi)

**M-03 Black Point Lava Flow, San Francisco volkan sahası, Arizona** — 35.6878, −111.3599 (K2: USGS GNIS'teki "Black Point" sırtı. Akıntının kendisi değil, onun yanındaki adlandırılmış nokta.)
- Gelecek hedef: Basınçlı gezgin operasyonları (Artemis "Mobility test" görevi).
- NASA ne yaptı: Desert RATS. **2008–2012** arasında, akıntının üstü "iniş yeri" seçilerek 3, 14 ve 28 günlük Lunar Electric Rover görevleri simüle edildi. 14 günlük görevde 2 kişilik bir mürettebat, gezginle Colton Crater ve SP Crater'a kadar ilerledi. NASA Earth Observatory de 2009 sonundaki testi duyurdu.
- Not: SP Crater (V1 #5) ~27 km uzakta. Aynı volkan sahasında ama farklı bir saha, yani listeler ayrık kalıyor.
- Kaynaklar: NASA Earth Observatory "Black Point Lava Flow, Arizona" (21 Ağustos 2009) · AZGS blog "Using Arizona to explore the Moon" (2019, Kring)

**M-04 Mauna Kea, Pu'u Hiwahine kül konisi, Hawaii (PISCES sahası)** — 19.7609, −155.4707 (19°45′39.29″K 155°28′14.56″B; K1, NTRS 20140008708)
- Gelecek hedef: "Ice & resources" görevi, yani kutupta buz ve uçucu madde arama.
- NASA ne yaptı:
  - **27 Ocak–11 Şubat 2010:** ISRU analog testi (NASA ile CSA, DLR ve NORCAT birlikte, PISCES işletiyor). KSC'nin RESOLVE prototipi Ay kutbunda uçucu madde aramayı simüle etti.
  - **2012:** Bir robotik kutup görevi simüle edildi ve RESOLVE, CSA'nın gezgininde yeniden test edildi.
  - Kasım 2009'da aynı sahada regolitten oksijen çıkarma denemeleri yapıldı.
- Kaynaklar: NTRS 20140008708 · NTRS 20100033667 (RESOLVE 2010) · NASA ISRU arşiv sayfası (UNT web arşivi) · ASCE J. Aerosp. Eng. 26(1) (2010 ILSO-ISRU)

**M-05 Craters of the Moon, Idaho (Inferno Chasm yarığı)** — 42.9667, −113.1903 (42°58′00″K 113°11′25″B; K1, AGU 2015 özeti)
- Gelecek hedef: Ay'daki ova volkanizması; özeti hazırlayan ekibe göre güneydoğu Mare Serenitatis (19°K 27,5°D) ile benzer. Ayrıca lav tüpleri (B1.2).
- NASA ne yaptı: Ames liderliğinde ve SSERVI çatısı altındaki FINESSE projesi **2014 ve 2015**'te burada çalıştı. Volkanik yer şekilleri LiDAR, diferansiyel GPS ve İHA ile haritalandı ve LRO NAC görüntüleri ile arazi modelleriyle karşılaştırıldı. Gelecekteki insan-robot keşfi için operasyon kavramları (ConOps) da sınandı.
- Kaynaklar: NTRS 20150023448 · NTRS 20190031834 · AGU FM15 P53C-2144 · nasa.gov FINESSE research objectives

**M-06 Kamestastin (Mistastin) Krateri, Labrador (Kanada)** — koordinat K3, doğrulanmadı (28 km çaplı krater, kuzey Labrador, Quebec sınırına yakın)
- Gelecek hedef: Güney kutbunda da beklenen anortozit, karmaşık krater.
- NASA ne yaptı: Eğitimleri CSA ve Western Üniversitesi (Osinski) yürütüyor, NASA astronotları katılıyor.
  - **Eylül 2021:** Kutryk (CSA) ve Dominick (NASA).
  - **Eylül 2023:** Hansen ve Gibbons (CSA) ile Koch ve Chari (NASA).
  - NASA'nın Temmuz 2024 PAC sunumu, Artemis II eğitiminde "Fieldwork – Kamestastin" adımını listeliyor.
- Kaynaklar: asc-csa.gc.ca "Training in geology" · asc-csa.gc.ca blog 2023/09/19 · science.nasa.gov PAC Temmuz 2024 "Artemis geology training" (Evans) · IAC-21 B3.8.11 (Osinski)

**M-07 İzlanda, Vatnajökull Ulusal Parkı'nın kuzeyi** — koordinat K3, doğrulanmadı (kaynaklar tam bir nokta vermiyor)
- Gelecek hedef: Bazalt, breş, buzlu zemin; Artemis astronotlarının jeoloji eğitimi.
- NASA ne yaptı: **24 Temmuz–6 Ağustos 2024**'te Artemis II mürettebatı (Wiseman, Glover, Koch, Hansen) ve yedekleri (Douglas, Gibbons) burada NASA liderliğinde arazi eğitimi aldı. Gündüz ve düşük açılı ışıkta gece yürüyüşleri yapıldı, örnek alma aletleri denendi. Apollo astronotları da İzlanda'da eğitilmişti.
- Kaynaklar: asc-csa.gc.ca (19150; 2024-08-22 haberi) · phys.org (16 Eylül 2024, NASA haberi) · science.nasa.gov PAC Temmuz 2024 sunumu

**M-08 Lanzarote, Kanarya Adaları (ESA PANGAEA)** — koordinat K3, doğrulanmadı
- Gelecek hedef: Mare bazaltları ve lav tüpleri.
- **NASA'nın kendi görevi değil, ESA'nın görevi.** NASA astronotları katılıyor:
  - 2022: Stephanie Wilson.
  - 2023: Jessica Wittner (Corona lav tüpünde).
  - 2026'daki 10. dönem: Jasmin Moghbeli.
- PANGAEA 2016'dan beri ESA, NASA, JAXA ve Roscosmos astronotlarını eğitiyor. Programın bir ayağı da Ries'te yapılıyor. Ries V1'de olduğu için B4'e yalnız Lanzarote alındı.
- Kaynaklar: esa.int "What is PANGAEA" · esa.int Images 2026/09 "Space explorers in the land of volcanoes" · IAC-24 B3 IP 10 (Drozdovskiy ve ark.) · phys.org 2022-11 (AFP)

#### Mars için

**R-01 Atacama, Yungay (Şili)** — −24.0656, −69.8639 (K2, wondermondo. McKay ve ark. 2003'teki koordinat metni, kaynağın PDF'inde bozuk göründü, okunamadı.)
- Gelecek hedef: Aşırı kurak, perklorat ve tuz içeren Mars yüzeyi; astrobiyoloji görevi (Jezero, Phoenix).
- NASA ne yaptı: Ames liderliğindeki ARADS projesi (PSTAR fonlu) burada çalıştı. Mars prototipi bir matkap, örnek aktarma kolu, SOLID (İspanya CAB) ve WCL aletleri birlikte sınandı. **Eylül 2019**'da gezgin, günde iki kez gönderilen komutlarla otomatik olarak "Playa" sahasına gidip örnek aldı. Saha 2003'ten beri Mars analoğu olarak çalışılıyor.
- Kaynaklar: astrobiology.nasa.gov "NASA tests life-detection drill in the Atacama" · PMC10750310 (Astrobiology 2023, doi:10.1089/ast.2022.0126) · Frontiers 10.3389/fspas.2021.810426 · NTRS 20220002136

**R-02 Río Tinto, Peña de Hierro (Nerva, Huelva, İspanya)** — 37.7251, −6.5564 (37°43.507′K 6°33.386′B; K2, waymarking. IGME patrimonio kaydındaki UTM 29 ETRS89 X = 715 470, Y = 4 178 190 ile aynı yeri gösteriyor.)
- Gelecek hedef: Meridiani Planum; jarosit, hematit ve demir-kükürt mineralleri.
- NASA ne yaptı: MARTE, NASA Ames ile İspanya'daki CAB'ın ortak projesi (ASTEP fonlu). **2003–2005** arasında çalıştı. 2005'te Peña de Hierro'daki açık ocağın kenarında 1 ay süren bir robotik kuru delme görevi simüle edildi; bilim ekiplerine sahanın önceden bilinen bilgileri verilmedi.
- Kaynaklar: Astrobiology 8(5) 2008, doi:10.1089/ast.2007.0217 (Stoker ve ark.) · doi:10.1089/ast.2006.0107 · NTRS 20050167747 · astrobiology.nasa.gov "Drilling for weird life"

**R-03 McMurdo Kuru Vadileri, University Valley (Antarktika)** — koordinat K3, doğrulanmadı (~1700 m yükseklik, kıyıdan ~75 km)
- Gelecek hedef: Phoenix iniş yeri, kuzey ovalarındaki yer altı buzu, SWIM buz alanları.
- NASA ne yaptı:
  - **2009'dan başlayarak üç güney yazı:** ASTEP fonlu IceBite projesi (McKay, Ames) "kuru permafrost"un altındaki buza gelecekteki bir Mars kutup görevi için matkaplar denedi.
  - Uluslararası Kutup Yılı sırasında Phoenix'in bilim soruları burada sınandı (Tamppari ve ark. 2012).
- Kaynaklar: phys.org 2009-11 "Taking a bite of Antarctic ice" · NTRS 20100003844 · Antarctic Science 24(3) 2012, doi:10.1017/S0954102011000800 · NTRS 20150023012

**R-04 Svalbard, Bockfjorden / Sverrefjell volkanı (Norveç)** — koordinat K3, doğrulanmadı (~80°K)
- Gelecek hedef: Mars karbonatları (ALH84001 meteoritindeki karbonat kürecikleriyle aynı doku), volkan ve buz etkileşimi.
- NASA ne yaptı: AMASE, Norveç liderliğinde bir sefer; NASA ASTEP ve ESA fonluyor. JPL, Ames ve GSFC'den ekipler katıldı. **2009**'da MSL için 2 alet ve ExoMars için 4 alet, JPL'nin FIDO gezgininde sınandı.
- Kaynaklar: astrobiology.nasa.gov NAI 2009 yıllık raporu (CIW) · planetary.org (Lakdawalla, 2009) · space.com "Expedition turns up life on pseudo-Mars" · ADS 2007amsw.conf...55S

**R-05 Lava Beds Ulusal Anıtı, Valentine Cave (Kaliforniya)** — 41.70925, −121.47778 (K2, Wikipedia; NPS ve USGS Bülten 1673'e dayanıyor)
- Gelecek hedef: Mars lav tüpleri (Tharsis, MGC3 adayları) ve Ay lav tüpleri.
- NASA ne yaptı: Ames'in BRAILLE projesi (PSTAR fonlu) **2018–2019**'da üç haftalık bir görev yaptı. CaveR gezgini, bir gezegen görevi planıyla Valentine Cave'e sürüldü. Lazer tarayıcıyla mağaranın haritası çıkarıldı; 9 mağaradan örnek alındı.
- Kaynaklar: nasa.gov "Using a cave rover, NASA learns to search for life underground" (2019) · astrobiology.nasa.gov (26 Haziran 2019) · nasa-braille.org · geekwire.com 2019

**R-06 Haughton Krateri** — M-01 ile aynı saha. Mars için de analog: kutup çölü, donmuş zemin. Sitede tek kayıt olarak durur, iki hedefe bağlanır.

**(Operasyon analoğu, eşleştirmeye girmez) Pavilion Lake, Britanya Kolumbiyası (Kanada)** — koordinat gerekmez
- Göl, fiziksel olarak Ay ya da Mars analoğu değil; yalnızca operasyon analoğu olduğu için sitede yalnız bilgi olarak geçer.
- PLRP 2004–2015 arasında çalıştı (Lim, Ames; CSA'nın CARN programı). DeepWorker denizaltılarıyla bilim odaklı EVA simüle edildi; 2015'te (PLRP-3) haberleşme gecikmesi altında EVA denendi.
- Kaynaklar: NTRS 20150019631 · nasa.gov PLRP görev özeti · Wikipedia "Pavilion Lake Research Project"

### B5. Artemis bölgeleri ve koordinatları

**Durum (13 Kasım 2026):**
- NASA, 27 Şubat 2026'da Artemis III'ü 2027'de alçak Dünya yörüngesinde yapılacak bir kenetlenme testine çevirdi.
- **İlk iniş artık Artemis IV, 2028.**
- 9 aday bölge Ekim 2024'te açıklandı ve hâlâ yayınlanmış referans set. NTRS 20250011660 bunları "Artemis III candidate regions" adıyla anlatıyor. Artemis IV için yeni bir bölge listesi yayınlandığını bulmadım.

Sitede önerilen etiket: "Artemis III candidate regions (Oct 2024) — first landing now planned as Artemis IV".

**Koordinat yöntemi:**
- NASA bölgelerin sınırlarını sayı olarak yayınlamadı.
- Aşağıdaki merkezler, Wueller ve ark. 2026'nın (JGR Planets 131, e2025JE009434) açık verisindeki (Zenodo doi:10.5281/zenodo.17084058, CC-BY-4.0) her bölgeye ait aday iniş noktalarının küresel vektör ortalamasıdır. Hesabı ben yaptım; n = bölgedeki nokta sayısı.
- Bu yöntem belgenin koordinat önceliğine (1. NASA sınırı ya da merkezi, 2. Peña-Asensio 2025, 3. IAU) tam uymuyor. Gözden geçirmede **kabul edildi**, "approximate centre" etiketiyle kullanılacak (bkz. B9).

| Belge kimliği | Bölge | Enlem | Boylam (doğu +) | n | Çapraz kontrol |
|---|---|---|---|---|---|
| A3-01 | Peak near Cabeus B | −83.576 | −69.076 | 5 | — |
| A3-02 | Haworth | −86.799 | −22.898 | 11 | — |
| A3-03 | Malapert Massif | −86.047 | 0.149 | 5 | Malapert zirvesi 0° boylamında, tutarlı |
| A3-04 | Mons Mouton Plateau | −84.534 | 30.655 | 11 | — |
| A3-05 | Mons Mouton | −85.399 | 31.180 | 10 | IAU Mons Mouton 84.6°G 31.0°D. Bölge merkezi zirveden ~0,8° (≈ 24 km) güneyde; bölge zirvenin kendisi değil. |
| A3-06 | Nobile Rim 1 | −85.188 | 37.240 | 9 | — |
| A3-07 | Nobile Rim 2 | −83.888 | 58.403 | 9 | — |
| A3-08 | de Gerlache Rim 2 | −88.174 | −68.787 | 7 | — |
| A3-09 | Slater Plain | −87.207 | 126.606 | 11 | — |

Kimlikler belge 9.1'deki tabloyla ada göre eşlendi (A3-01 Peak near Cabeus B … A3-09 Slater Plain).

**Bilinen sapma:** Wueller ve ark. aday iniş noktalarını, 2 km içinde kalıcı gölgeli bölgeye (PSR) erişim sağlayacak biçimde seçti. Bu yüzden ortalama merkezler bölgenin tam ortası değil, gölgeye doğru kaymış olabilir. Bölgeler ~15 km, pencerelerimiz 20 km olduğu için bu kayma sonucu fazla değiştirmez. Sitede bu koordinatlar **"approximate centre (mean of candidate landing sites, Wueller et al. 2026)"** diye gösterilir. hedefler.csv'nin kaynak sütununa aynı ifade yazılır.

Bilgi için, hedef değil: 2022'deki 13 bölgeden listeden çıkanların aynı veriden hesaplanan merkezleri.
- Amundsen Rim (−84.250, 68.692)
- Faustini Rim A (−87.932, 90.946)
- Peak near Shackleton (−88.887, 127.425)
- Connecting Ridge (−89.489, −135.390)
- Connecting Ridge Extension (−88.941, −106.097)
- de Gerlache Rim 1 (−88.610, −65.426)
- de Gerlache–Kocher Massif (−85.704, −115.359)

Leibnitz Beta Plateau bu veride yok.

Bölge sınırları için resmî kaynak: USGS'nin 9 bölge için 1 km'lik ızgaraları (McClernan 2024, doi:10.5066/P1MEQ6UK, ScienceBase 671a6fa8d34efed5620f89f8, CC0). Sayfa bir Cloudflare bot doğrulaması gösterdi ve ben bunu geçmeye çalışmadım → bkz. B9.

### B6. Ek veri setleri (hepsi "ek / puana girmez")

**Gözden geçirme kararı:** X1, X2, X3, X5 ve X6 bu koşuda **indirilmez**; bloklar yalnız bilgi ve sonraki çalışma için duruyor. X4 (MGC3) yalnız B1.2'deki isteğe bağlı iş için ve 15 Kasım sabahı vakit kalırsa indirilir. `indir_hepsi.py`'nin ana listesine X blokları **eklenmez**.

Bu bloklar aynı 9 alanlı şablonla yazıldı. Bilgiler 13 Kasım'da ürün sayfalarından okundu. **Hiçbirinde boyut HEAD isteğiyle ölçülmedi.** İndirme kodu dosyayı indirince boyutu kaydetmeli.

#### X1 — Copernicus DEM GLO-90 (ESA / AB Copernicus) — B1.1 için Dünya — **bu koşuda indirilmez**
- Sayfa (DOI / ürün sayfası): https://registry.opendata.aws/copernicus-dem/ · https://copernicus-dem-90m.s3.amazonaws.com/readme.html
- Dosyalar: 1°×1°'lik karolar, ad kalıbı `Copernicus_DSM_COG_30_{N|S}{YY}_00_{E|W}{XXX}_00_DEM/Copernicus_DSM_COG_30_..._DEM.tif`. Örnek: https://copernicus-dem-90m.s3.eu-central-1.amazonaws.com/Copernicus_DSM_COG_30_N05_00_E000_00_DEM/Copernicus_DSM_COG_30_N05_00_E000_00_DEM.tif . **Yalnız Katman A'nın ilk 10 aday penceresine düşen karolar alınır.**
- Erişim: doğrudan https ya da `aws s3 ... --no-sign-request` (bölge eu-central-1)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: doğrulanmadı. Bir gezgin kaynağa göre toplam 26 470 karo var; yalnızca gerekenler indirilir.
- Sağlama: doğrulanmadı (yalnız boyut + GDAL ile açılması)
- Kullanılacak katman/bant/değişken: tek bant yükseklik, float32 (nodata NaN, Digital Earth Africa kaydı). DSM olduğu için binaları ve bitki örtüsünü de içerir.
- Bilinen sorun: GLO-30'un bazı ülke karoları kısıtlı, ama GLO-90 dünya çapında serbest. Lisans metni readme'nin "License" bölümünde, metin bu çalışmada okunmadı → doğrulanmadı. Atıf: "Copernicus Digital Elevation Model (DEM) was accessed on DATE from https://registry.opendata.aws/copernicus-dem"
- Doğrulandı: kısmen (sayfa bilgisi okundu, dosyaya HEAD yapılmadı)

#### X2 — Mars HRSC–MOLA Blended DEM 200 m v2 (ESA Mars Express + NASA MGS) — B1.1 için Mars — **bu koşuda indirilmez**
- Sayfa (DOI / ürün sayfası): https://astrogeology.usgs.gov/search/map/mars_mgs_mola_mex_hrsc_blended_dem_global_200m
- Dosyalar: tek dosya — https://planetarymaps.usgs.gov/mosaic/Mars/HRSC_MOLA_Blend/Mars_HRSC_MOLA_BlendDEM_Global_200mp_v2.tif
- Erişim: doğrudan https. Tüm dosya yerine GDAL `/vsicurl/` ile yalnız pencere okunabilir; dosyanın tile'lı olup olmadığı doğrulanmadı.
- Giriş gerekiyor mu: hayır
- Beklenen boyut: ürün sayfasında "11 GB" (HEAD ile ölçülmedi). Raster 106 694 × 53 347.
- Sağlama: doğrulanmadı
- Kullanılacak katman/bant/değişken: tek bant yükseklik (m)
- Bilinen sorun: Sayfanın kendisi bazı yerlerde birleştirmenin iyi olmadığını söylüyor. MOLA'yı içerdiği için yalnız HRSC kapsanan yerde R1'den bağımsız. Lisans: MOLA CC0, HRSC CC BY-SA 3.0 IGO. Atıf: Fergason, Hare & Laura (2018), HRSC and MOLA Blended DEM at 200m v2, USGS.
- Doğrulandı: kısmen (sayfa bilgisi)

#### X3 — LOLA + Kaguya TC birleşik DEM 60°K–60°G 512 ppd, SLDEM2015 (NASA + JAXA) — B1.1 için Ay — **bu koşuda indirilmez**
- Sayfa (DOI / ürün sayfası): https://astrogeology.usgs.gov/search/map/moon_lro_lola_selene_kaguya_tc_dem_merge_60n60s_59m
- Dosyalar: tek dosya — https://planetarymaps.usgs.gov/mosaic/LolaKaguya_Topo/Lunar_LRO_LOLAKaguya_DEMmerge_60N60S_512ppd.tif (yedek: MIT'de 45° × 30°'lik karolar, https://imbrium.mit.edu/BROWSE/SLDEM2015/TILES )
- Erişim: doğrudan https
- Giriş gerekiyor mu: hayır
- Beklenen boyut: ürün sayfasında "22 GB" (HEAD ile ölçülmedi)
- Sağlama: doğrulanmadı
- Kullanılacak katman/bant/değişken: etikete göre 184 320 × 61 440, SignedWord (int16) × 0,5 m, referans yarıçap 1 737 400 m, 59,2 m/piksel
- Bilinen sorun: **Yalnız ±60°.** Artemis bölgelerini kapsamaz, yalnız Apollo hedefleri için kullanılır. Lisans: USGS medya sayfasında "Public Domain". Atıf: Barker ve ark. 2016, Icarus 273, 346–355.
- Doğrulandı: kısmen (sayfa + etiket)

#### X4 — Mars Global Cave Candidate Catalog, MGC3 (Cushing, USGS) — B1.2 — **isteğe bağlı, 15 Kasım sabahı**
- Sayfa (DOI / ürün sayfası): https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing · PDS4 urn:nasa:pds:mars_mro.odyssey_multi_cavecatalog_cushing_2016
- Dosyalar: `mars_cave_catalog.zip` — http://astropedia.astrogeology.usgs.gov/download/Mars/MarsCaveCatalog/mars_cave_catalog.zip
- Erişim: doğrudan (http)
- Giriş gerekiyor mu: hayır
- Beklenen boyut: ürün sayfasında 1 770 313 bayt
- Sağlama: doğrulanmadı (yalnız boyut)
- Kullanılacak katman/bant/değişken: Her aday için enlem, boylam, tür (lav tüpü tavan açıklığı, derin çatlak, atipik çukur krater …), öncelik (güven) puanı ve yorum. Zip'teki README.TXT okunur.
- Bilinen sorun: Bunlar "aday" girişler; yörüngeden ne kadar derine uzandıkları bilinemiyor. Lisans: kamu malı (data.gov "us-pd"). Atıf: Cushing, G. E. (2015), Mars Global Cave Candidate Catalog PDS4 Archive Bundle.
- Doğrulandı: kısmen (sayfa bilgisi)

#### X5 — LROC Lunar Pit Atlas, çukur konumları shapefile'ı (Wagner & Robinson) — B1.2 — **alınmaz (adres yok)**
- Sayfa (DOI / ürün sayfası): https://data.lroc.im-ldi.com/lroc/view_rdr/SHAPEFILE_LUNAR_PIT_LOCATIONS
- Dosyalar: `LUNAR_PIT_LOCATIONS_180` (boylam −180…180) ya da `LUNAR_PIT_LOCATIONS_360`. **Dosyanın tam indirme adresi okunmadı → EKSİK.**
- Erişim: doğrudan (LROC RDR sayfası)
- Giriş gerekiyor mu: hayır (sayfa açık)
- Beklenen boyut: doğrulanmadı
- Sağlama: doğrulanmadı
- Kullanılacak katman/bant/değişken: çukur noktaları, IAU MOON2000; `Name` sütunu + konum
- Bilinen sorun: Çukurların çoğu çarpma eriyiği havuzlarında ve lav tüpüyle ilgisiz. Mare çukurları ayrıca etiketlenmeli (tür sütunu sayfada açıklanıyor). Atıf: Wagner & Robinson (2021) LPSC 52 #2530; Wagner & Robinson (2022) JGR Planets, doi:10.1029/2022JE007328.
- Doğrulandı: hayır (yalnız sayfanın açıklaması okundu)

#### X6 — WOKAM, Dünya Karst Akifer Haritası (BGR / KIT / IAH / UNESCO) — **alınmaz**, yalnız bilgi
- Sayfa (DOI / ürün sayfası): https://www.deutsche-rohstoffagentur.de/whymap/EN/Maps_Data/Wokam/wokam_node_en.html
- Dosyalar: ESRI Shapefile (GDI-DE kataloğunda "WHYMAP WOKAM (Shapefile)"); tam adres okunmadı
- Erişim: doğrudan (BGR)
- Giriş gerekiyor mu: doğrulanmadı
- Beklenen boyut: doğrulanmadı
- Sağlama: doğrulanmadı
- Kullanılacak katman/bant/değişken: karst akifer poligonları, 1:25 000 000
- Bilinen sorun: Karst mağaraları çözünme mağarasıdır, Ay ve Mars'taki lav tüplerinin analoğu değildir (B1.2). Lisans: BGR genel koşulları (https://www.bgr.bund.de/AGB_en ); atıf zorunlu: "WHYMAP WOKAM, (C) BGR Berlin, IAH Reading, KIT Karlsruhe, UNESCO Paris 2017".
- Doğrulandı: hayır

### B7. 24 setin işlenmesi: nereden, nasıl

Akış (belge 10.4 ve 17.x), her set için aynı:
1. **İndir:** Bu raporun bloğundaki adres ve erişim yöntemiyle (`indir_hepsi.py`) → `veri\` (projenin ham veri klasörü)
2. **Doğrula:** Bloktaki "Beklenen boyut" ve "Sağlama" alanlarıyla. Hata olursa set durdurulur.
3. **Oku ve assert et:** Aşağıdaki tablodaki okuma kuralıyla. Bu kurallar, dosya doğru olsa bile dikkatsiz okumada sonucu sessizce bozan tuzaklardır.
4. **Birime çevir:** Ölçek ve ofset uygulanır, veri-yok değerleri NaN yapılır. Bayraklar (sansürlü, belgelenmemiş kod) NaN'a çevrilmez, ayrı bir bayrak dizisine yazılır.
5. **Yaz:** `temiz\<govde>\<kod>_<ad>\` klasörüne.
   - Raster: tek bantlı float32 GeoTIFF (çok büyük setlerde .npy + .json).
   - Vektör: GeoPackage (`birim`, `alan_km2`).
   - `meta.json`: kaynak URL, DOI, sürüm, lisans, tarih, ham dosyaların SHA-256'sı, CRS, birim, ölçek/ofset, veri-yok kuralı, gerçek-yer testleri.
6. **Kural:** 14 Kasım kodu yalnız `temiz\` klasörünü okur (P0 adımında SHA-256 = meta.json kontrolü yapılır).

| Set | Nereden (blok) | Nasıl okunur — kritik kural (belge 10.1–10.3 + bu rapor) | temiz\ çıktısı |
|---|---|---|---|
| E1 ETOPO | NOAA, 288 karo | Karo adı = üst-sol köşe; float32 m (EGM2008); nodata −99999; yalnız `_surface` | yükseklik GeoTIFF |
| E2 MCD12C1 | Earthdata, 1 HDF4 | `Land_Cover_Type_1_Percent`; 17 sınıfın yüzdesi, toplam 100; 255 = yok | sınıf yüzdeleri (.npy) |
| E3 GLiM | Dropbox zip, GDB | Katman `GLiM_export`, sınıf sütunu `xx`; World Eckert IV | GeoPackage (`birim`) |
| E4 ASTER GED | Earthdata, 12 HDF5 | Emissivity bant 10–14 uint8 × 0,002 + offset (dosyadan; sayfada N/A); 0 = yok; NDVI × 0,001 | yayınım + NDVI |
| E5 MYD11C3 | Earthdata, 12 HDF4 | LST_Day/Night_CMG uint16 × 0,02 K; 0 = yok | Tgündüz/Tgece |
| E6 MCD43C3 | Earthdata, 12 HDF4 (adla seçilir) | Albedo_WSA_shortwave × 0,001; geçerli 0–32 766 | albedo |
| E7 Permafrost K | PANGAEA zip (Deflate) | EPSG:3995, 926,6 m, 0–1; MAGTM alınmaz | PERPROB |
| E8 Permafrost G | PANGAEA zip (Deflate) | EPSG:3031, 1 km | PERPROB |
| E9 Aridity | figshare zip | `ai_v31_yr.tif`, değer × 10 000 (dosyadan doğrulanır); `__MACOSX/` atlanır | AI |
| E10 SoilGrids | ISRIC (checksum.sha256.txt) | ‰ (g/kg); Goode Homolosine; kapsam ~56°G–84°K | kil + silt |
| M1 LOLA | USGS (.md5 var) | int16 × 0,5 m; −32768 = yok; BigTIFF; bant bant okunur | yükseklik |
| M2 Ay jeolojisi | USGS zip | GDB açılmaz; `Lunar_GIS/Shapefiles/GeoUnits.shp`, `FIRST_Unit`, `AREA_GEO` | GeoPackage |
| M3 Diviner GHRM | PDS | float32, NaN = yok; tbol ≥ 250 K yok sayılır | kaya bolluğu, Tgece |
| M4 Diviner PRP + GCP | PDS | PRP: −999 sansürlü (bayrak), 0 = yüzeyde buz, −1 belgelenmemiş (bayrak). GCP: uzun tablo, `ltim` yerel saat | Tmax, T̄, Tgece, ıslak/kuru |
| M5 LP GRS | PDS | 2° eş alanlı, 11 306 piksel, alan toplamı = 4πR²; FeO kesri, Th ppm | FeO, Th maskesi |
| M6 LP hidrojen | PDS | 259 200 satırlık uzun tablo; `**********` hücresi NaN; 4 180 negatif hücre kırpılmaz | H |
| M7 PGDA | GSFC (düz .TIF) | AVGVISIB = DN × 0,00004; LPSR = DN × 0,000025 + 0,5; x = ρ sin λ, y = ρ cos λ; anormal piksel NaN | aydınlanma, gölge |
| R1 MOLA | USGS | int16 m; transform kullanılmaz: satır = ⌊(90 − φ)·128⌋, sütun = ⌊(λ + 180)·128⌋ | yükseklik |
| R2 SIM 3292 | USGS zip | `SIM3292_Global_Geology.shp`, `Unit`, `SphArea_km`; 44 birim | GeoPackage |
| R3 TES mineral | ASU (http) | ENVI float32 big-endian (.hdr esas), 1440 × 720 × 13; −1 = yok; bant 3, 5, 6, 8, 12, 13 | mineral bolluğu |
| R4 TES TI + albedo | ASU + PSI | TI >i2, 7200 bayt başlık, ilk satır güney, boylam batıya; albedo little-endian; maske `nmsk2003.bin` | TI, albedo |
| R5 TES DCI | ASU (yedek: Wayback) | 1024 bayt etiket, 5760 × 2880 <f4; 0,85 = yok; boylam −180'den doğuya | DCI |
| R6 Odyssey GRS | PDS (MD5 listesi) | 9999,999 = yok; H₂O yalnız 57,5°G–57,5°K; **puana girmez** | çapraz kontrol |
| R7 SWIM | PSI (HTTP 522 olabilir) | GeoTIFF 7200 × 2400, −30 = yok; −1…+1 tutarlılık indeksi (olasılık değil) | Ci |

Ek setlerden yalnız X4 (MGC3) alınırsa `temiz\ek\` altına aynı biçimde yazılır. **Puanlayan kod bu klasörü okumaz**; yalnız 15 Kasım'daki isteğe bağlı mağara etiketi okur.

### B8. Kaynaklar (bu ekte kullanılan her şey)

Artemis ve bölgeler:
1. NTRS 20250011660 — Artemis III Site Selection Update (13 → 9 bölge): https://ntrs.nasa.gov/citations/20250011660
2. UPI, 28 Ekim 2024 — 9 bölgenin adları: https://www.upi.com/Science_News/2024/10/28/nasa-artemis-moon-landing-regions/5971730152372/
3. Live Science — Artemis programındaki değişiklik (Artemis III LEO 2027, inişler 2028): https://www.livescience.com/space/space-exploration/nasa-announces-sweeping-overhaul-of-artemis-return-to-moon-targeting-a-2028-landing-and-a-2027-in-orbit-docking-flight
4. The Register, 2 Mart 2026: https://www.theregister.com/2026/03/02/nasa_artemis_reshuffle/
5. Spaceflight Now, 27 Şubat 2026: https://spaceflightnow.com/2026/02/27/nasa-announces-major-overhaul-of-artemis-moon-program/
6. Wueller ve ark. 2026, JGR Planets 131, e2025JE009434; veri: https://doi.org/10.5281/zenodo.17084058
7. McClernan 2024, USGS ızgaraları: https://doi.org/10.5066/P1MEQ6UK

Ay analogları:

8. NTRS 20110008151 (Haughton koordinatı, Shackleton karşılaştırması): https://ntrs.nasa.gov/api/citations/20110008151/downloads/20110008151.pdf
9. Fong, 2007 Haughton Crater Field Test: https://webarchive.library.unt.edu/eot2008/20090117080131/http:/ti.arc.nasa.gov/projects/haughton_field/pdfs/haughton-crater-field-test.pdf
10. NASA Analogs blog (HMP-2010): https://blogs.nasa.gov/analogsfieldtesting/tag/haughton-mars-project-hmp
11. USGS Meteor Crater Sample Collection: https://usgs.gov/centers/astrogeology-science-center/science/meteor-crater-sample-collection
12. HMdb tabela (Meteor Crater, 1963–1970 eğitimi, koordinat): https://www.hmdb.org/m.asp?m=161618
13. NASA Earth Observatory, Black Point Lava Flow: https://earthobservatory.nasa.gov/IOTD/view.php?id=40076
14. AZGS blog (Kring, D-RATS): https://blog.azgs.arizona.edu/index.php/blog/2019-05/using-arizona-explore-moon
15. TopoQuest / GNIS, Black Point: https://topoquest.com/place-detail.php?id=1577
16. NTRS 20140008708 (Mauna Kea ISRU 2010/2012, koordinat): https://ntrs.nasa.gov/citations/20140008708
17. NTRS 20100033667 (RESOLVE 2010): https://ntrs.nasa.gov/api/citations/20100033667/downloads/20100033667.pdf
18. NASA ISRU arşiv sayfası: https://webarchive.library.unt.edu/web/20130221205815/http://www.nasa.gov/exploration/analogs/isru/index.html
19. NTRS 20150023448 (FINESSE 2014–2015): https://ntrs.nasa.gov/api/citations/20150023448/downloads/20150023448.pdf
20. NTRS 20190031834 (FINESSE özeti): https://ntrs.nasa.gov/api/citations/20190031834/downloads/20190031834.pdf
21. AGU FM15 P53C-2144 (Inferno Chasm koordinatı): https://agu.confex.com/agu/fm15/webprogram/Paper63838.html
22. CSA, Training in geology (Mistastin): https://www.asc-csa.gc.ca/eng/astronauts/about-the-job/space-mission-simulations/training-in-geology.asp
23. CSA blog, 19 Eylül 2023: https://asc-csa.gc.ca/eng/blog/2023/09/19
24. NASA PAC Temmuz 2024, Artemis Geology Training (Evans): https://science.nasa.gov/wp-content/uploads/2024/08/7-artemis-science-planning-training.pdf
25. CSA, Artemis II mürettebatı İzlanda'da: https://www.asc-csa.gc.ca/eng/news/articles/2024/2024-08-22-artemis-ii-crew-refines-lunar-geology-skills-in-iceland.asp
26. CSA görsel 19150 (24 Temmuz–6 Ağustos 2024, Vatnajökull): https://www.asc-csa.gc.ca/eng/multimedia/search/image/19150
27. ESA, What is PANGAEA: https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/CAVES_and_PANGAEA/What_is_PANGAEA
28. ESA, Space explorers in the land of volcanoes (2026): https://www.esa.int/ESA_Multimedia/Images/2026/09/Space_explorers_in_the_land_of_volcanoes
29. IAC-24 PANGAEA (Drozdovskiy ve ark.): https://iafastro.directory/iac/paper/id/86963/abstract-pdf/IAC-24,B3,IP,10,x86963.brief.pdf
30. IAC-21 Osinski (Mistastin, Meteor Crater): https://p.iafastro.directory/iac/paper/id/66087/abstract-pdf/IAC-21,B3,8,11,x66087.brief.pdf

Mars analogları:

31. NASA Astrobiology, ARADS: https://astrobiology.nasa.gov/news/nasa-tests-life-detection-drill-in-the-atacama-desert/
32. ARADS 2019 sondaj makalesi: https://pmc.ncbi.nlm.nih.gov/articles/PMC10750310/
33. Azua-Bustos ve ark. 2022, Atacama: https://doi.org/10.3389/fspas.2021.810426
34. Wondermondo, Yungay koordinatı: https://wondermondo.com/yungay
35. Stoker ve ark. 2008, MARTE (core.ac.uk kopyası): https://core.ac.uk/download/36046284.pdf
36. MARTE alt-yüzey jeolojisi: https://core.ac.uk/download/36024766.pdf
37. NTRS 20050167747 (MARTE jeobiyoloji): https://ntrs.nasa.gov/api/citations/20050167747/downloads/20050167747.pdf
38. Waymarking, Peña del Hierro koordinatı: https://www.waymarking.com/waymarks/WM19T97_Mina_de_Pea_del_Hierro_Nerva_Huelva_Espaa
39. IGME, Peña de Hierro maden kaydı (UTM): https://info.igme.es/geofpi/docs/mapas/PATRIMONIO_400K_ZSP_2020/PATRIMONIO_CONJUNTOS_MINEROS/10_Conjunto%20minero_Pe%C3%B1a%20de%20Hierro.pdf
40. phys.org, IceBite: https://phys.org/news177613575.html
41. NTRS 20100003844 (Dry Valleys–Phoenix): https://ntrs.nasa.gov/api/citations/20100003844/downloads/20100003844.pdf
42. NTRS 20150023012 (University Valley): https://ntrs.nasa.gov/citations/20150023012
43. NASA NAI 2009 yıllık raporu, AMASE: https://astrobiology.nasa.gov/nai/annual-reports/2009/ciw/project-6-application-of-laboratory-experimentation-to-flight-instrument-testing/index.html
44. Planetary Society, AMASE 2009: https://www.planetary.org/articles/svalbard
45. NASA, BRAILLE: https://www.nasa.gov/universe/using-a-cave-rover-nasa-learns-to-search-for-life-underground/
46. Valentine Cave koordinatı: https://en.wikipedia.org/wiki/Valentine_Cave
47. NTRS 20150019631 (PLRP 2015): https://ntrs.nasa.gov/citations/20150019631

Ek veri setleri:

48. Copernicus DEM, AWS: https://registry.opendata.aws/copernicus-dem/
49. HRSC–MOLA Blend: https://astrogeology.usgs.gov/search/map/mars_mgs_mola_mex_hrsc_blended_dem_global_200m
50. LOLA–Kaguya (SLDEM2015): https://astrogeology.usgs.gov/search/map/moon_lro_lola_selene_kaguya_tc_dem_merge_60n60s_59m
51. MGC3: https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing
52. USGS, The Caves of Mars: https://usgs.gov/news/caves-mars
53. LROC pit konumları: https://data.lroc.im-ldi.com/lroc/view_rdr/SHAPEFILE_LUNAR_PIT_LOCATIONS
54. WOKAM: https://www.deutsche-rohstoffagentur.de/whymap/EN/Maps_Data/Wokam/wokam_node_en.html

Kaynak dışı bırakılan: Arama sonuçlarındaki bir ansiklopedi kopyası sitesi (cavac.at), sayfa metninin içine okuyan yapay zekâya yönelik talimatlar gömmüştü. Bu site hiçbir bilgi için kullanılmadı.

### B9. Eksikler (açıkça)

1. **Artemis koordinatları belgenin öncelik sırasına uymuyor** (gözden geçirmede "approximate centre" etiketiyle kabul edildi).
   - 1. öncelik (NASA sınırı): USGS McClernan 2024 sayfası Cloudflare doğrulaması yüzünden açılamadı. Doğrulama geçilmeye çalışılmadı. Başka bir ağdan ya da tarayıcıdan elle açılırsa sınır ızgaralarından gerçek merkezler hesaplanabilir.
   - 2. öncelik (Peña-Asensio 2025): Bu çalışmada kontrol edilmedi.
   - Tablodaki merkezler aday iniş noktalarının ortalaması, yani bölge sınırının merkezi değil, ve PSR'ye doğru kaymış olabilir.
2. (Çözüldü) A3-01…A3-09 kimlikleri ada göre eşlendi.
3. Koordinatı K3 olan sahalar: İzlanda (Artemis II eğitimi), Kamestastin/Mistastin, Lanzarote, University Valley, Sverrefjell.
4. Atacama Yungay için birincil kaynaktaki (McKay 2003) koordinat PDF'te bozuk okundu; ikincil kaynak kullanıldı (K2).
5. X1–X6 ek setlerinde boyut ölçülmedi. Lisans metinleri (Copernicus) okunmadı. X5 ve X6'nın tam dosya adresleri bulunmadı.
6. Partner DEM kontrolü bu koşudan çıkarıldı (B1.1); Ay'da zaten Artemis bölgelerini kapsamıyordu.
7. Alınan maddeler (Artemis etiketi, B2 sekmeleri, 20/100 km eşikleri, analog.json alanları) v1.2.1 olarak belgeye işlenmeli ve D6/D8'den önce kilitlenmeli (B0).
8. B4'teki tarih ve astronot adları ikinci kez tek tek doğrulanmadı; sitede kaynak bağlantısıyla gösterilir.

## Kontrol kaydı
- **1. tur (biçim ve aritmetik):** 24 blok sırayla var (E1–E10, M1–M7, R1–R7) ve her blokta şablonun 9 satırının hepsi dolu. 38 sağlama değeri doğru uzunlukta (MD5 32, SHA-256 64 karakter). Adreslerin sonunda noktalama yok. Bölüm 16.2'deki "bilinen not"ların hepsi ilgili blokta yanıtlandı. Toplamlar ve boyut çarpımları kodla yeniden hesaplandı.
- **2. tur (adresler yeniden açıldı):** M3, M4, M5, M6 ve R6'nın 15 boyutu ve 34 MD5 değeri (dosya–değer eşleşmesi dahil) PDS listeleriyle yeniden karşılaştırıldı: hepsi tuttu. M1, R1 (boyut + .md5), M2, M7 (4 tif), E7, E8, E10 (boyut + SHA-256), E9 (boyut + MD5) ve R7 (3 tif) de yeniden doğrulandı. E1, E2/E4/E5/E6 (CMR), R2, R3 ve R4 ikinci turda tarayıcının site güvenlik kontrolü/izni yüzünden yeniden açılamadı; bunların değerleri ilk turda doğrudan sunucudan okunmuştu.
- **3. tur (belgeyle tutarlılık):** "İrem'in dikkatine" listesindeki her madde ilgili blokla, Earthdata tablosu E2/E4/E5/E6 bloklarıyla ve lisans/künye listeleri bloklarla karşılaştırıldı. Doğrulanmamış bir adres kaldı: figshare kayıt sayfası, onun yerine API adresi yazıldı. M1/R1 dosya sayıları netleştirildi. R4'teki bir kaynak ifadesi düzeltildi.
- **Yeniden deneme (16:30):** Açık kalan 5 madde tekrar denendi. E9, E10 ve R4 çözüldü (yukarıdaki listeye bakın). E3 (Dropbox) ve R5 (www.mars.asu.edu) bu ağdan hâlâ açılmıyor; ikisi için de yedek ya da aday adresler eklendi. Tarayıcının güvenlik uyarıları atlanmadı.
- **Üçüncü deneme (16:45):** R5'in bağlantısı ve boyutu Internet Archive üzerinden doğrulandı. E3 için yaklaşık boyut ve katman bilgisi bağımsız bir kaynaktan teyit edildi; kesin bayt değeri hâlâ açık.
- **Son tam kontrol (16:40–16:50, bütün adresler yeniden açıldı):** E1 klasörü 288 dosya ✓ · E2/E4/E5/E6 CMR granül sayıları 1/12/12/12 ve E5 granül adları 12/12 ✓ · E7, E8 boyut ✓ · E9 boyut + MD5 + lisans ✓ · E10 boyut + SHA-256 ✓ · M1, R1 boyut + MD5 ✓ · M2 boyut ✓ · M3–M6, R6 31 dosyanın boyutu ✓ · M7 4 veri + 4 etiket ✓ · R3, R4 dosyaları ✓ (albedo .lbl için sıkıştırma notu eklendi) · R7 3/3 ✓ · R5 arşiv kopyası boyut ve etiket ✓ (16:40). Bu turda yeniden açılamayanlar: R2 (pubs.usgs.gov için tarayıcıda sayfa okuma izni kapalı; değerler ilk turda sunucudan okunmuştu) ve E3 (Dropbox, ağ hatası).
- **B eki kontrolü (20:30):** 24 blok + X1–X6 bloklarının her biri 9 satır ✓ · B4'teki koordinatlı 8 sahanın en yakın V1 sahasına uzaklığı kodla hesaplandı (en yakın: Black Point–SP Crater 27,2 km; hepsi > 20 km) → doğrulama ve gelecek görev listeleri ayrık ✓ · adreslerin sonunda noktalama yok ✓ · Artemis merkezleri Wueller ve ark. 2026 verisinden küresel ortalamayla hesaplandı; Mons Mouton IAU ile, Malapert 0° boylamıyla karşılaştırıldı.
- **Gözden geçirme sonrası (20:45):** B0 karar tablosu eklendi. B1.1 partner DEM kontrolü ve X1–X3, X5, X6 bu koşudan çıkarıldı. B1.2 yalnız Mars MGC3'e indirildi (isteğe bağlı). B1.3'e eşik ve V1 koşulu yazıldı. B4'e site gösterim kuralları, B5'e A3 kimlikleri ve PSR sapması notu eklendi. B7'de ham klasör adı `veri\` yapıldı. 24 blok + 6 X bloğu yine 9'ar satır.
- **indirme_raporu3 (21:00):** ETOPO yüzdeleri "bütün ızgaranın payı" olarak düzeltildi (GEBCO %58,8; Copernicus + FABDEM ≈ %34 = kara piksellerinin büyük kısmı; kaynak ETOPO makalesi, ESSD 2025). v1.2.1 listesindeki metin dosyası satır numaraları kaldırıldı, belge bölüm adlarıyla yazıldı. Başa sürüm ve birlikte kullanım notu eklendi. 24 blok değişmedi.
