# Developed with assistance from Claude (Anthropic).
"""Belge 12 (P9): makale şekilleri, tabloları ve V4. Yalnız sonuç dosyalarını okur; puan yeniden hesaplanmaz.

Okur : sonuc\\liste\\liste_<id>.json (Katman A), sonuc\\dogrulama\\dogrulama.json, sonuc\\ozet.json,
       ara\\katmanb_<cisim> (Katman B deposu), ara\\p3_dunya_kimlik.npy, kod\\hedefler.csv, kod\\ayar.json
Yazar: sonuc\\sekiller\\f*.pdf + .png, sonuc\\tablolar\\t*.tex, sonuc\\dogrulama\\V4.json,
       sonuc\\makale_sayilar.json, ozet.json'a "V4" (sonuc\\ ve sonuc\\site\\)

V4 (uyarlama, MAKALEYİ ETKİLER 89): 26 liste hedefi × 5 görev; Katman A (bütün E′, koordinata ortalı pencere, 64 bit)
ile hedef koordinatının düştüğü Katman B hücresi (Kön = 800, 32 bit) karşılaştırılır: Top-3 Jaccard (pencere kimliği),
B'nin 1. adayının A'nın ilk 10'undaki sırası, P₁ farkı, iki tarafta da bulunan pencerelerde |s − s′|.
Belgedeki 200 rastgele hedefli V4 bu sürümde koşulmadı; bu fark makalede yazılır.

Çalıştırma: python makale_cikti.py   (kod\\ klasöründe, orbitrary ortamında)
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import kos as K
import izgara as Z
import puan as Pn

t0 = time.time()
SON, ARA, KOD = K.SONUC, K.ARA, K.KOD
SEK, TAB = SON / "sekiller", SON / "tablolar"
SEK.mkdir(parents=True, exist_ok=True); TAB.mkdir(parents=True, exist_ok=True)
GOREV = K.GOREVLER                                     # genel, mobility, geology, ice, astro
GAD = K.GOREV_AD
KAD = K.KATEGORI_AD
# Mavi tonları (site ile aynı aile); görevler renk tonu + işaret şekliyle ayrılır (renk körlüğüne dayanıklı)
OI = ["#1F5FA8", "#7CC4EF", "#0B2A55", "#3E9BE0", "#A9D8F5", "#5E86B8", "#C9E8FB", "#0B1F44"]
GRENK = dict(zip(GOREV, ["#0B1F44", "#1F5FA8", "#3E9BE0", "#7CC4EF", "#A9D8F5"]))
GSEKIL = dict(zip(GOREV, ["o", "s", "^", "D", "v"]))
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 200})


def kaydet(fig, ad):
    for uz in ("pdf", "png"):
        fig.savefig(SEK / f"{ad}.{uz}", bbox_inches="tight")
    plt.close(fig)
    print("  şekil:", ad)


def tex(ad, satirlar, sutun, baslik, etiket, hiza=None):
    hiza = hiza or "l" * len(sutun)
    esc = lambda x: str(x).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")
    s = [r"\begin{table}[ht]", r"\centering\small", f"\\caption{{{baslik}}}", f"\\label{{{etiket}}}",
         f"\\begin{{tabular}}{{{hiza}}}", r"\hline", " & ".join(esc(c) for c in sutun) + r" \\", r"\hline"]
    s += [" & ".join(esc(c) for c in r) + r" \\" for r in satirlar]
    s += [r"\hline", r"\end{tabular}", r"\end{table}"]
    (TAB / f"{ad}.tex").write_text("\n".join(s), encoding="utf-8")
    print("  tablo:", ad)


def oku(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


yuz = lambda x, b=1: "—" if x is None else f"{100 * x:.{b}f}%"
krd = lambda la, lo: f"{abs(la):.2f}°{'N' if la >= 0 else 'S'}, {abs(lo):.2f}°{'E' if lo >= 0 else 'W'}"

hed = pd.read_csv(KOD / "hedefler.csv", encoding="utf-8-sig").dropna(subset=["kimlik"])
L = {k: oku(SON / "liste" / f"liste_{k}.json") for k in hed["kimlik"] if (SON / "liste" / f"liste_{k}.json").exists()}
assert len(L) == 26, f"Katman A dosya sayısı {len(L)} (26 olmalı)"
DG = oku(SON / "dogrulama" / "dogrulama.json")
OZ = oku(SON / "ozet.json")
D = K.Dunya()
assert D.n == OZ["E_prime"], (D.n, OZ["E_prime"])
ADI = {k: L[k]["hedef"]["ad"] for k in L}
for k, v in {"M-SP": "Lunar south pole test point", "M-SHK": "Shackleton crater", "R-PHX": "Phoenix landing site"}.items():
    if k in ADI: ADI[k] = v
CISIM = {k: L[k]["hedef"]["cisim"] for k in L}
ART = [k for k in L if k.startswith("A3-")]
MARS = [k for k in L if CISIM[k] == "mars"]
AYD = [k for k in L if CISIM[k] == "ay" and not k.startswith("A3-")]
sayi = {}

# =====================================================================================================
# V4 (uyarlama): Katman A ↔ Katman B, aynı hedef koordinatı
# =====================================================================================================
print("V4 …")
v4 = []
for g in ("ay", "mars"):
    H = Z.Halka(g)
    dp = K.Depo(ARA / f"katmanb_{g}", H.n)
    assert dp.tamam(), f"Katman B {g} bitmemiş"
    t3, PB, sB = np.asarray(dp.oku("top3")), np.asarray(dp.oku("P")), np.asarray(dp.oku("s"))
    for k in [k for k in L if CISIM[k] == g]:
        h = L[k]["hedef"]
        c = int(H.tikla(h["enlem"], h["boylam"]))
        lam_c = np.degrees(H.lam[c]); lam_c = lam_c - 360 if lam_c > 180 else lam_c
        km = float(Z.haversine(np.radians(h["enlem"]), np.radians(h["boylam"]), H.phi[c], H.lam[c], Z.yaricap(g)))
        for gi, gg in enumerate(GOREV):
            o = L[k]["gorevler"].get(gg) or {}
            if o.get("durum") != "computed" or not o.get("ilk10"):
                continue
            rows = t3[c, gi]
            if (rows < 0).all():
                continue
            Bk = [int(D.kim[r]) for r in rows if r >= 0]
            Ak = [int(r["kimlik"]) for r in o["ilk10"][:3]]
            A10 = [int(r["kimlik"]) for r in o["ilk10"]]
            ortak = sorted(set(Ak) & set(Bk))
            ds = []
            for w in set(A10) & set(Bk):
                sa = np.array([np.nan if x is None else x for x in o["ilk10"][A10.index(w)]["s"]], float)
                sb = sB[c, gi, Bk.index(w)].astype(float)
                ds += list(np.abs(sa - sb)[np.isfinite(sa) & np.isfinite(sb)])
            v4.append({"hedef": k, "gorev": gg, "hucre": c, "hucre_km": km,
                       "J_top3": len(ortak) / len(set(Ak) | set(Bk)),
                       "B1_A_sira": (A10.index(Bk[0]) + 1) if Bk[0] in A10 else None,
                       "P1_A": o["ilk10"][0]["P"], "P1_B": float(PB[c, gi, 0]),
                       "fark_s": [float(x) for x in ds]})
J = np.array([x["J_top3"] for x in v4]); dP = np.array([x["P1_A"] - x["P1_B"] for x in v4])
S_ = np.concatenate([x["fark_s"] for x in v4]) if v4 else np.zeros(0)
ilk10de = np.mean([x["B1_A_sira"] is not None for x in v4])
v4oz = {"tanim": "uyarlama: 26 liste hedefi × görev; Katman A (bütün E′) ile hedef koordinatının Katman B hücresi (Kön = 800); belge V4'ün 200 rastgele hedefi koşulmadı",
        "n": len(v4), "J_top3_ortanca": float(np.median(J)), "J_top3_ort": float(J.mean()),
        "J_sifir_orani": float((J == 0).mean()), "B1_A_ilk10_orani": float(ilk10de),
        "P1_fark_ortanca": float(np.median(dP)), "P1_fark_y95": float(np.percentile(dP, 95)),
        "fark_s_n": int(S_.size), "fark_s_ortanca": float(np.median(S_)) if S_.size else None,
        "fark_s_y95": float(np.percentile(S_, 95)) if S_.size else None}
(SON / "dogrulama" / "V4.json").write_text(json.dumps({"ozet": v4oz, "satirlar": v4}, ensure_ascii=False, indent=1), encoding="utf-8")
for p in (SON / "ozet.json", SON / "site" / "ozet.json"):
    if p.exists():
        o_ = oku(p); o_["V4"] = v4oz; o_.setdefault("_kaynak", {})["V4"] = "sonuc\\dogrulama\\V4.json (makale_cikti.py)"
        p.write_text(json.dumps(o_, ensure_ascii=False, separators=(",", ":"), default=float), encoding="utf-8")
print("  V4:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in v4oz.items() if k != "tanim"})

fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.6))
ax[0].hist(S_, bins=40, color=OI[0]); ax[0].set_xlabel("|s − s′| (same Earth window, Layer A vs Layer B)"); ax[0].set_ylabel("count")
ax[1].hist(dP, bins=30, color=OI[3]); ax[1].set_xlabel("P₁(Layer A) − P₁(Layer B)"); ax[1].axvline(0, color="#0B1F44", lw=0.8)
kaydet(fig, "f16_v4_katman")

# =====================================================================================================
# Şekiller
# =====================================================================================================
print("şekiller …")
# F5 / F6: Top-3 Dünya haritaları (arka plan: E′ pencereleri = kara)
arka = np.random.default_rng(20261113).choice(D.n, min(D.n, 60000), replace=False)


def harita(hedefler, ad, baslik):
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.scatter(D.lon[arka], D.lat[arka], s=0.3, c="#e3e7ec", lw=0, rasterized=True)
    for gg in GOREV:
        xs, ys = [], []
        for k in hedefler:
            o = L[k]["gorevler"].get(gg) or {}
            for r in (o.get("ilk10") or [])[:3]:
                xs.append(r["boylam"]); ys.append(r["enlem"])
        if xs:
            ax.scatter(xs, ys, s=22, c=GRENK[gg], marker=GSEKIL[gg], edgecolor="#0B1F44", lw=0.5, label=GAD[gg], zorder=3)
    ax.set_xlim(-180, 180); ax.set_ylim(-60, 85); ax.set_xlabel("longitude (°)"); ax.set_ylabel("latitude (°)")
    ax.set_title(baslik, fontsize=9); ax.legend(fontsize=7, ncol=5, loc="lower center", frameon=False, bbox_to_anchor=(0.5, -0.32))
    kaydet(fig, ad)


harita(ART, "f5_harita_artemis", "Top-3 Earth analogs of the 9 Artemis III candidate regions, by mission")
harita(MARS, "f6_harita_mars", "Top-3 Earth analogs of the 10 Mars landing sites, by mission")


# F7: radar, dört seçilmiş eşleşme (Top-1)
def radar(ax, s, baslik):
    a = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    v = np.array([np.nan if x is None else x for x in s], float)
    ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
    ax.set_xticks(a); ax.set_xticklabels([]); ax.set_ylim(0, 1); ax.set_yticks([0.5, 1]); ax.set_yticklabels([])
    for ai, ad in zip(a, KAD):
        ax.text(ai, 1.22, ad, fontsize=6, ha="center", va="center")
    vv = np.where(np.isfinite(v), v, 0)
    ax.plot(np.r_[a, a[0]], np.r_[vv, vv[0]], color=OI[0]); ax.fill(np.r_[a, a[0]], np.r_[vv, vv[0]], color=OI[0], alpha=0.25)
    for i in np.flatnonzero(~np.isfinite(v)):
        ax.text(a[i], 0.62, "no data", fontsize=5.5, ha="center", va="center", color="grey")
    ax.set_title(baslik, fontsize=7, pad=22)


sec = [("A3-05", "genel"), ("M-A15", "geology"), ("R-JEZ", "astro"), ("R-GAL", "genel")]
fig, axs = plt.subplots(1, 4, figsize=(11, 3.4), subplot_kw={"projection": "polar"})
fig.subplots_adjust(wspace=0.55)
for ax, (k, gg) in zip(axs, sec):
    r = L[k]["gorevler"][gg]["ilk10"][0]
    radar(ax, r["s"], f"{ADI[k]} · {GAD[gg]}\n#1 {krd(r['enlem'], r['boylam'])}\nP = {r['P']:.2f}")
kaydet(fig, "f7_radar")

# F8: V1 Π
V1 = sorted(DG["V1"], key=lambda x: x["cift_no"])
fig, ax = plt.subplots(figsize=(7.2, 2.8))
x = np.arange(len(V1))
ax.bar(x - 0.2, [v["Pi"] for v in V1], 0.4, color=[("#cfd6df" if v["kapidan_kaldi"] else OI[0]) for v in V1], label="own mission")
ax.bar(x + 0.2, [v["Pi_genel"] for v in V1], 0.4, color=OI[1], label="General")
ax.axhline(0.5, color="#0B1F44", lw=0.7, ls="--"); ax.set_ylim(0, 1.02); ax.set_ylabel("Π (share of E′ scoring lower)")
ax.set_xticks(x); ax.set_xticklabels([f"{v['cift_no']} · {v['saha'].split(',')[0]}" for v in V1], fontsize=6.5, rotation=35, ha="right")
for i, v in enumerate(V1):
    if v["kapidan_kaldi"]:
        ax.text(i - 0.2, 0.03, "gate", rotation=90, fontsize=6, ha="center", color="#555")
ax.legend(fontsize=7, frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.15))
kaydet(fig, "f8_v1_pi")

# F9: ROC verisi (PB) dosyada yok → AUC ve %95 GA nokta grafiği
v3 = DG["V3"]
fig, ax = plt.subplots(figsize=(3.2, 1.4))
ax.errorbar([v3["AUC"]], [0], xerr=[[v3["AUC"] - v3["GA95"][0]], [v3["GA95"][1] - v3["AUC"]]], fmt="o", color=OI[0], capsize=4)
ax.axvline(0.5, color="#0B1F44", ls="--", lw=0.7); ax.set_xlim(0.3, 1); ax.set_yticks([]); ax.set_xlabel("AUC (known analogs vs random E′), 95% bootstrap CI")
kaydet(fig, "f9_auc")

# F10: V6 Spearman
r = np.array([[np.nan if x is None else x for x in rr] for rr in DG["V6"]["r"]], float)
fig, ax = plt.subplots(figsize=(4, 3.4))
im = ax.imshow(np.abs(r), vmin=0, vmax=1, cmap="Blues"); fig.colorbar(im, ax=ax, shrink=0.8, label="|Spearman r| (sign in cell)")
ax.set_xticks(range(8)); ax.set_xticklabels(KAD, rotation=45, ha="right", fontsize=7); ax.set_yticks(range(8)); ax.set_yticklabels(KAD, fontsize=7)
for i in range(8):
    for j in range(8):
        if np.isfinite(r[i, j]):
            ax.text(j, i, f"{r[i, j]:.2f}", ha="center", va="center", fontsize=5, color="white" if abs(r[i, j]) > 0.6 else "#0B1F44")
ax.set_title(f"V6: category correlations (n = {DG['V6']['n']}; no |r| > 0.8)", fontsize=8)
kaydet(fig, "f10_spearman")

# F12: V8 ablasyon (τb, kategori çıkarılınca)
abl = np.array([[np.nan if x is None else x for x in v] for v in DG["V8"].values()], float)
fig, ax = plt.subplots(figsize=(5, 2.8))
med = np.nanmedian(abl, axis=0)
ax.barh(range(8), med, color=OI[2]); ax.set_yticks(range(8)); ax.set_yticklabels(KAD); ax.invert_yaxis()
ax.set_xlabel("median Kendall τb vs full ranking when the category is removed"); ax.set_xlim(0, 1)
kaydet(fig, "f12_ablasyon")

# F13: duyarlılık (Top-3 Jaccard, eşit ağırlık / geometrik ortalama)
jr = {"esit": {g: [] for g in GOREV}, "geometrik": {g: [] for g in GOREV}}
for k in L:
    for gg, o in L[k]["gorevler"].items():
        for sch in jr:
            v = ((o or {}).get("duyarlilik") or {}).get(sch) or {}
            if v.get("jaccard_top3") is not None:
                jr[sch][gg].append(v["jaccard_top3"])
fig, ax = plt.subplots(figsize=(5.5, 2.6))
xx = np.arange(len(GOREV))
for q, (sch, ad) in enumerate((("esit", "equal weights"), ("geometrik", "geometric mean"))):
    ax.bar(xx + (q - 0.5) * 0.38, [np.mean(jr[sch][g]) if jr[sch][g] else np.nan for g in GOREV], 0.38, color=OI[q], label=ad)
ax.set_xticks(xx); ax.set_xticklabels([GAD[g] for g in GOREV], fontsize=7); ax.set_ylim(0, 1); ax.set_ylabel("mean Top-3 Jaccard")
ax.legend(frameon=False, fontsize=7)
kaydet(fig, "f13_duyarlilik")

# F14: Katman B kapsama (1. eşleşmede iki tarafta verisi olan kategori sayısı / 8, Genel)
fig, axs = plt.subplots(1, 2, figsize=(8, 2.6))
for ax, g in zip(axs, ("ay", "mars")):
    H = Z.Halka(g)
    s0 = np.asarray(K.Depo(ARA / f"katmanb_{g}", H.n).oku("s"))[:, 0, 0, :]
    kap = np.isfinite(s0.astype(float)).sum(1) / 8
    lo = np.degrees(H.lam); lo = np.where(lo > 180, lo - 360, lo)
    sc = ax.scatter(lo, np.degrees(H.phi), c=kap, s=0.2, cmap="Blues", vmin=0, vmax=1, lw=0, rasterized=True)
    ax.set_title({"ay": "Moon", "mars": "Mars"}[g] + " — Layer B coverage (categories with data / 8)", fontsize=8)
    ax.set_xlim(-180, 180); ax.set_ylim(-90, 90)
    sayi[f"kapsama_B_{g}_ortalama"] = float(np.nanmean(kap))
fig.colorbar(sc, ax=axs, shrink=0.8)
kaydet(fig, "f14_kapsama")

# =====================================================================================================
# Tablolar
# =====================================================================================================
print("tablolar …")
# T3 ağırlıklar
tex("t3_agirlik", [[GAD[g]] + [f"{w:.3f}" for w in Pn.gorev_agirligi(g)] for g in GOREV], ["Mission"] + KAD,
    "Mission weights (Section 7.3: 0.80 shared by the main categories, 0.20 by the others).", "tab:weights", "l" + "r" * 8)
# T4 kapı
rows = []
for k in L:
    rr = [ADI[k]]
    for g in GOREV:
        o = L[k]["gorevler"].get(g) or {}
        rr.append("n/a" if o.get("durum") != "computed" else f"{o['E_g']:,}" + (" (fallback)" if o.get("kapi_yedek") else ""))
    rows.append(rr)
tex("t4_kapi", rows, ["Target"] + [GAD[g] for g in GOREV], f"Earth windows passing each mission gate (of |E′| = {D.n:,}).", "tab:gates", "l" + "r" * 5)
# T6 V1
tex("t6_v1", [[v["cift_no"], v["saha"], ADI.get(v["hedef"], v["hedef"]), GAD.get(v["gorev"], v["gorev"]),
               "gate (Π = 0)" if v["kapidan_kaldi"] else f"{v['Pi']:.3f}", f"{v['Pi_genel']:.3f}"] for v in V1],
    ["#", "Earth site", "Target", "Mission", "Π (mission)", "Π (General)"],
    f"V1: NASA training sites. Fisher p = {DG['V1_gorev']['p']:.3f} (own mission), {DG['V1_genel']['p']:.3f} (General); "
    f"first-pair subset (8) p = {DG['V1_ilk8']['p']:.3f}.", "tab:v1", "rllrrr")
# T7 doğrulama özeti
v9 = DG["V9"]
t7 = [["V1 own mission", f"Fisher X² = {DG['V1_gorev']['X2']:.1f}", f"{DG['V1_gorev']['p']:.3f}", "known sites above chance"],
      ["V1 General", f"X² = {DG['V1_genel']['X2']:.1f}", f"{DG['V1_genel']['p']:.3f}", "above chance"],
      ["V1 first pairs (8)", f"X² = {DG['V1_ilk8']['X2']:.1f}", f"{DG['V1_ilk8']['p']:.3f}", "above chance"],
      ["V2 negative controls (22)", f"X² = {DG['V2']['X2']:.1f}", f"{DG['V2']['p']:.1e}", "controls rank low"],
      ["V3 AUC", f"{v3['AUC']:.3f} [{v3['GA95'][0]:.2f}, {v3['GA95'][1]:.2f}]", f"{v3['p']:.3f}", "CI includes 0.5"],
      ["V4 Layer A vs B (adapted)", f"median Top-3 J = {v4oz['J_top3_ortanca']:.2f}", "—", "see text"],
      ["V5 prefilter recall (K = 800)", f"{OZ['V5']['recall_ort']['800']:.3f}", "—", "below 0.9 (rule K3)"],
      ["V6 max |r_S| (off-diagonal)", f"{np.nanmax(np.abs(np.where(np.eye(8, dtype=bool), np.nan, r))):.2f}", "—", "no pair > 0.8"],
      ["V7 noise stability", "not run", "—", "limitation"],
      ["V9 per category (Holm)", ", ".join(f"{KAD[int(c) - 1]}: {p:.3f}" for c, p in v9["holm_p"].items()), "—",
       "significant: " + ", ".join(KAD[int(c) - 1] for c, rd in v9["holm_red"].items() if rd)],
      ["V10 expert ranking", "not available", "—", "limitation"]]
tex("t7_dogrulama", t7, ["Test", "Statistic", "p", "Reading"], "Validation summary (values from ozet.json / dogrulama.json).", "tab:validation", "llll")


# T8 / T9 hedef tabloları
def hedef_tablo(ad, liste, baslik, et):
    rows = []
    for k in liste:
        for g in GOREV:
            o = L[k]["gorevler"].get(g) or {}
            if o.get("durum") != "computed" or not o.get("ilk10"):
                rows.append([ADI[k], GAD[g], "not applicable", "—", "—", "—"]); continue
            r0 = o["ilk10"][0]; ya = r0.get("en_yakin_analog") or {}
            rows.append([ADI[k], GAD[g], krd(r0["enlem"], r0["boylam"]), f"{r0['P']:.3f}", f"{r0['kapsama']:.3f}",
                         f"{ya.get('km', float('nan')):.0f} km" if ya.get("km") is not None else "—"])
    tex(ad, rows, ["Target", "Mission", "Top-1 Earth window", "P", "coverage", "nearest known analog"], baslik, et, "lllrrr")


hedef_tablo("t8_artemis", ART, "Artemis III candidate regions (Oct 2024; first landing now planned as Artemis IV): Top-1 Earth window per mission.", "tab:artemis")
hedef_tablo("t9_mars", MARS, "Mars landing sites: Top-1 Earth window per mission.", "tab:mars")
hedef_tablo("t8b_ay_diger", AYD, "Apollo sites and other lunar targets: Top-1 Earth window per mission.", "tab:moon")

# T11 süre (kayit\kos_sure.jsonl)
ks = K.KAYIT / "kos_sure.jsonl"
if ks.exists():
    ss = [json.loads(x) for x in ks.read_text(encoding="utf-8").splitlines() if x.strip()]
    son = {}
    for s in ss:
        son[s["asama"]] = s
    tex("t11_sure", [[a, s["zaman"], s.get("sure_s", s.get("sure_dk", "—"))] for a, s in son.items()], ["Stage", "finished", "duration (s)"],
        "Run times (kayit/kos_sure.jsonl).", "tab:runtime", "llr")

# =====================================================================================================
# Makale sayıları (metin içinde geçenler)
# =====================================================================================================
P1 = {g: [L[k]["gorevler"][g]["ilk10"][0]["P"] for k in L if (L[k]["gorevler"].get(g) or {}).get("durum") == "computed" and L[k]["gorevler"][g].get("ilk10")] for g in GOREV}
yeni = sum(1 for k in L for g in GOREV for r in ((L[k]["gorevler"].get(g) or {}).get("ilk10") or [])[:3]
           if (r.get("en_yakin_analog") or {}).get("km", 0) > 100)
top3_toplam = sum(1 for k in L for g in GOREV for r in ((L[k]["gorevler"].get(g) or {}).get("ilk10") or [])[:3])
gecen = [v for v in V1 if not v["kapidan_kaldi"]]
sayi.update({
    "E_prime": D.n, "dunya_pencere": OZ["dunya_pencere"], "ay_pencere": OZ["izgara"]["ay"], "mars_pencere": OZ["izgara"]["mars"],
    "hedef": len(L), "artemis": len(ART), "mars_hedef": len(MARS), "ay_diger": len(AYD),
    "V1_gecen_cift": len(gecen), "V1_gecen_Pi_ortanca": float(np.median([v["Pi"] for v in gecen])),
    "V1_en_iyi": max((v["Pi"], v["saha"], v["hedef"]) for v in gecen),
    "top1_P_ortanca": {g: float(np.median(v)) for g, v in P1.items() if v},
    "top3_100km_otesi": [yeni, top3_toplam],
    "eps1_hepsi_1cm_alti": all((r.get("eps1_durum") or "").startswith("hassas") for k in L for g in GOREV
                               for r in ((L[k]["gorevler"].get(g) or {}).get("ilk10") or [])),
    "eps1_durum_sayim": pd.Series([str(r.get("eps1_durum")) for k in L for g in GOREV
                                   for r in ((L[k]["gorevler"].get(g) or {}).get("ilk10") or [])]).value_counts().to_dict(),
    "V4": v4oz, "sure_s": round(time.time() - t0, 1)})
(SON / "makale_sayilar.json").write_text(json.dumps(sayi, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print("\nmakale_sayilar.json:", {k: v for k, v in sayi.items() if k not in ("V4",)})
print(f"\nbitti ({time.time() - t0:.0f} s): {len(list(SEK.glob('*.pdf')))} şekil, {len(list(TAB.glob('*.tex')))} tablo → sonuc\\sekiller, sonuc\\tablolar")
