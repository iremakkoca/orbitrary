# Denklem → fonksiyon (Emir'in dipnotları için)

<!-- ayar.py -->
## ayar.py
- 7.3 w_k(g) → `ayar.agirliklar(gorev, sema)`
- 8.4 parametreler → `ayar.ayar(anahtar)`, kaynak → `ayar.kaynak(anahtar)`
- 17 rastgelelik → `ayar.rng(alt)`
<!-- /ayar.py -->

<!-- izgara.py -->
## izgara.py
- 4.2 M_B, Δφ, φ_i, m_i, λ_ij → `izgara.Halka(govde)`
- 4.2 (i*, j*) tıklama eşlemesi → `izgara.Halka.tikla`
- 4.2 gc(P1, P2) → `izgara.haversine`; komşular N(T) → `izgara.Halka.komsular`
- 4.3 Lambert k′, x, y → `izgara.lambert_ileri`; ters → `izgara.lambert_geri`
- 4.3 x_i, y_j → `izgara.hucre_merkezleri`, `izgara.pencere`
<!-- /izgara.py -->

<!-- katman.py -->
## katman.py
- 4.4 sürekli katman v_ij (ortalama / coarse) → `katman.hucreye(katman, phi0, lam0, r, genisletme)`
- 4.4 kategorik katman v_ij,c (vektör, 5 × 5 nokta) → `katman.hucreye_sinif(vektor, phi0, lam0, r)`
- 4.4 δv < δ kuralı → `katman.alt_ornek_sayisi`
- temiz\ okuyucuları → `katman.ac(ad)`; aylık Dünya katmanları → `katman.aylik(kod, onek)`
- 6.5 / v1.2 D5 Ay Tgece GCP 18:00–06:00 → `katman.gcp_gece_izgara`
- 6.8 / 10.2 PGDA kutupsal dönüşüm → `katman.pgda_xy`
<!-- /katman.py -->

<!-- uzaklik.py -->
## uzaklik.py
- 5.1 F⁻¹((m − ½)/M), M = 1000 → `uzaklik.yuzdelik`
- 5.1 W₁ → `uzaklik.w1`; referansa karşı matris → `uzaklik.w1_matris`
- 5.2 u_f,B(x) → `uzaklik.Sira`; 1 − u (ters) → `uzaklik.Sira.ters`
- 5.2 u⁺_f,B(x) → `uzaklik.SiraPozitif`
- 5.2 P_f,B (alanca düzgün, ≤ 10⁶, tohum) → `uzaklik.referans_orneklem`
- 5.3 TV → `uzaklik.tv`
<!-- /uzaklik.py -->

<!-- ozellik_topo.py -->
## ozellik_topo.py
- 6.1 h_x, h_y (Horn), h_xx, h_yy, h_xy → `ozellik_topo.turevler`
- 6.1 θ → `ozellik_topo.egim`; VRM → `ozellik_topo.vrm`; H → `ozellik_topo.egrilik`
- 6.1 h⁽⁴⁾ (4 × 4 blok) → `ozellik_topo.blok4`; iki ölçek ve R → `ozellik_topo.ozellikler`
- 6.1 IQR_T(f_s), F_T → `ozellik_topo.iqr_hedef`; d₁ → `ozellik_topo.d1`
- 8.1 Ω_s(W) → `ozellik_topo.ozellikler` (Omega_1, Omega_4)
- 7.1 z'nin (θ̄, θ₀,₉, VRM̄, ln R) bileşenleri → `ozellik_topo.z_topo`
<!-- /ozellik_topo.py -->

<!-- ozellik_topoloji.py -->
## ozellik_topoloji.py
- 6.2 R_top, ĥ, ȇ → `ozellik_topoloji.normalize`
- 6.2 küpsel H₀ (GUDHI) → `ozellik_topoloji.h0_gudhi`; Dgm↓, Dgm↑ → `ozellik_topoloji.diyagramlar`
- 6.2 SW (Mθ = 50) → `ozellik_topoloji.sw`; d₂ → `ozellik_topoloji.d2`
- 7.1 n↓, n↑ → `ozellik_topoloji.n_onemli`
- (test başvurusu) H₀ union-find → `ozellik_topoloji.h0_union_find`
<!-- /ozellik_topoloji.py -->

<!-- ozellik_diger.py -->
## ozellik_diger.py
- 6.3 q_c(W), kar/buz → buz → `ozellik_diger.hucre_grup_paylari`, `ozellik_diger.pencere_jeoloji`; sözlük → `ozellik_diger.sozluk_matrisi`; d₃ → `ozellik_diger.d3`
- 6.4 MI → `ozellik_diger.mafik_indeks`; Mars x → `ozellik_diger.mars_hcp`; d₄ (%50 kuralı) → `ozellik_diger.d4`
- 6.5 C₁ → `ozellik_diger.C1`; I⊕ aylık → `ozellik_diger.I_arti_ay`; yıllık Σ C₁(1 − α)/Σ ΔTg (madde 29) → `ozellik_diger.I_arti_yillik`; δ⊙ → `ozellik_diger.gunes_boylami_ve_deklinasyon`; F₅ → `ozellik_diger.termal_ozellikleri`; d₅ → `ozellik_diger.d5`
- 6.6 sıfır kuralı → `ozellik_diger.sifir_kurali`; π⁺ → `ozellik_diger.pi_arti`; ıslak/kuru → `ozellik_diger.islak_mi`
- 6.8 Q̄_gün → `ozellik_diger.berger_gunluk`; f(φ) → `ozellik_diger.berger_yillik` (tablo `BergerTablosu`)
- 6.3–6.8 pencere temsilleri → `ozellik_diger.pencere_temsili`; P_f,B sıraları → `ozellik_diger.sira`; Dünya CMG ızgaraları → `ozellik_diger.dunya_cmg`
<!-- /ozellik_diger.py -->

<!-- kapi.py -->
## kapi.py
- 7.1 kara_ij, E′ → `kapi.kara_payi`, `kapi.maskeden_gecer`
- 7.2 P_v → `kapi.Pv`; W° değişkenleri → `kapi.degiskenler`
- 7.2 G_mob, G_buz, G_astro, G_jeo → `kapi.kapi_mobility`, `kapi.kapi_buz`, `kapi.kapi_astro`, `kapi.kapi_jeoloji`
- 7.2 kapı yedeği (< 100 pencere) → `kapi.yedek_gerekir_mi`
- 7.2 Uygun(E) → `kapi.uygun`; X ve leave-one-out → `kapi.X_degerleri`
<!-- /kapi.py -->

<!-- teorem.py -->
## teorem.py
- 8.1 Λ_θ,s, Λ_VRM,s, Λ_H,s(W) → `teorem.lambdalar`; ℓ_W, ℓ^top_W → `teorem.ell`, `teorem.ell_top`
- 8.1 Ψ₁ → `teorem.psi1`; Ψ₂ → `teorem.psi2`
- 8.1 Teorem 1 koşulu → `teorem.kosul`; ε*_k (ikiye bölme) → `teorem.eps_yildiz`, `teorem.eps1`, `teorem.eps2`
- 8.1 hareket kapısının değişmezliği (n±) → `teorem.mobility_degismez`
<!-- /teorem.py -->

<!-- onele.py -->
## onele.py
- 7.1 z = (θ̄, θ₀,₉, VRM̄, ln R, n↓, n↑) → `onele.z_vektoru`
- 7.1 medyan, MAD, z̃ (1,4826 · MAD) [96]; Q-1 MAD = 0 bileşeni çıkar → `onele.Olcek` (`.standart`, `.kayit`)
- 7.1 E′_g ve E_K(T, g) (cKDTree, eşitlikte küçük kimlik) → `onele.Agac` (`.sorgu`)
- 7.1 / 8.3 V5 Kön seçimi (Q-9, Q-10) → `onele.kon_sec`; r̄ ± 1,96 s_d/√n → `onele.recall_ozet`
<!-- /onele.py -->

<!-- puan.py -->
## puan.py
- 5.4 s_k(E) (R_k(T, E), kendisi hariç, |R_k| < 100 → null) → `puan.s_k`
- 5.4 ζ_k(E) (kendisi hariç ortanca; Q-11 payda 0 → ζ = 1 / +∞) → `puan.zeta_k`
- 7.3 w_k(g) ayar.json'dan (ana / eşit) → `puan.gorev_agirligi`
- 7.3 w_k(g) = 0,80/m, 0,20/(n − m) → `puan.kademeli_agirlik`; eksik kategoride etkili ağırlık → `puan.etkili_agirlik`
- 7.4 P_g, Q_g → `puan.P_Q`; sıralama (P ↓, Q ↑, kimlik ↑) → `puan.sirala`
- 7.4 Top-3 (≥ 100 km) → `puan.aralikli_liste`; büyük çember (4.2) → `puan.gc_km`
- 7.4 topoloji: ilk 30'un tam puanla yeniden sıralanması → `puan.yeniden_sirala`
- 7.4 kategori şampiyonu E*_k(T) (Q-2) → `puan.sampiyonlar`
- 7.4 duyarlılık: ağırlıklı geometrik ortalama → `puan.P_geometrik`; Kendall τb → `puan.kendall_tau_b`; Jaccard → `puan.jaccard`
<!-- /puan.py -->

<!-- dogrula.py -->
## dogrula.py
- 8.3 V1 Π_a → `dogrula.pi_degeri`; X² ve p → `dogrula.fisher_v1`
- 8.3 V2 X²₋ ve p → `dogrula.fisher_v2`; çift seçimi (Q-3) → `dogrula.v2_sec`
- 8.3 V3 U, AUC → `dogrula.auc`; Mann–Whitney p, bootstrap GA → `dogrula.v3`; B′ → `dogrula.b_prime`
- 8.3 V4 → `dogrula.v4_ozet` (ortalama, ortanca, %5–%95); ortak kümede τb (Q-15) → `dogrula.tau_ortak`; V4/V5 hedefleri (Q-4) → `dogrula.rastgele_hedefler`
- 8.3 V5 recall → `dogrula.recall` (r̄ ± GA ve Kön: `onele.recall_ozet`, `onele.kon_sec`)
- 8.3 V6 r_S matrisi → `dogrula.spearman_matris`
- 8.3 V7 τb, J → `puan.kendall_tau_b`, `puan.jaccard`; özet → `dogrula.v7_ozet`
- 8.3 V8 ablasyon → `dogrula.ablasyon`
- 8.3 V9 Holm → `dogrula.holm`
- 8.3 V10 r_S → `dogrula.v10`
<!-- /dogrula.py -->

<!-- kos.py -->
## kos.py
- 17.5 P1 ızgara → `kos.izgara`, `kos.p1`; P2 kara maskesi + kapı değişkenleri → `kos.p2_blok`, `kos.p2`
- 17.5 P3 pencere özellikleri (topografya, n↓/n↑, z, kategori 3–8, hareket kapısı) → `kos.p3_blok`, `kos.p3`
- 17.5 kaldığı yerden devam (K16) → `kos.Depo`, `kos.bloklari_kos`; süre kaydı → `kos.sure_yaz`
- 17.5 D5 kuru koşu → `kos.d5`; P0 → `kos.p0`
<!-- /kos.py -->

<!-- kos2 -->
## kos.py (2. parça)
- 5.4 R(k) → `kos.referans_kumeleri`; 4.2/6.1 hedef penceresi, N(T), IQR_T → `kos.hedef_hazirla`; K(T) → `kos.hedef_kategorileri`
- 6.3–6.8 bütün E′ için d₃…d₈ (tek geçiş) → `kos.dunya_uzakliklari`
- 7.2 G_g → `kos.kapilar`; X (D7, K-5) → `kos.X_hesapla`
- 7.1–7.4, 8.1 hedef × görev akışı (ön eleme, s_k, ζ_k, P, Q, ilk 30 topoloji, ilk 10, şampiyonlar, duyarlılık, ε*) → `kos.puanla`
- 8.1 iki cisimli Ψ₁, Ψ₂ → `kos._psi1`, `kos._psi2`; B1.3 en yakın analog → `kos.bilinen_analoglar`
- 17.5 Katman A → `kos.katman_a`; D6 pilot → `kos.d6`
<!-- /kos2 -->
