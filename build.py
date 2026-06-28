#!/usr/bin/env python3
"""
MedTech Daily — Build-Skript

Läuft nachts auf GitHub Actions und schreibt eine fertige, in sich geschlossene
Seite nach public/index.html. Zur Laufzeit wird nichts nachgeladen — alle Daten
sind eingebacken. Damit kann nie etwas "rot" werden.

Zwei Dimensionen, zwei Datenquellen:
  • THEMEN     → 7 kuratierte MedTech-Fachfeeds (RSS)
  • UNTERNEHMEN → Google-News-Suche je Firma (echte, firmenspezifische Treffer)
"""

import feedparser, json, re, html, os, time, urllib.parse
from datetime import datetime, timezone

# ── Fachfeeds für die Themen-Dimension ──────────────────────────────────────
FEEDS = [
    ("MedTech Dive",           "https://www.medtechdive.com/feeds/news/"),
    ("MassDevice",             "https://www.massdevice.com/feed/"),
    ("Medical Device Network", "https://www.medicaldevice-network.com/feed/"),
    ("MedCity News",           "https://medcitynews.com/feed/"),
    ("Medgadget",              "https://www.medgadget.com/feed"),
    ("MedTech Intelligence",   "https://www.medtechintelligence.com/feed/"),
    ("ScienceDaily Devices",   "https://www.sciencedaily.com/rss/health_medicine/medical_devices.xml"),
]

# ── Top 50 MedTech-Unternehmen mit HQ in Europa (ungefähr nach Umsatz) ───────
# n=Name, f=Flagge, c=Land, s=Bereich, q=optionaler Such-Override für Google News
# (ohne q wird exakt nach "Name" gesucht).
COMPANIES = [
    {"n":"Siemens Healthineers","f":"🇩🇪","c":"DE","s":"Bildgebung & Diagnostik"},
    {"n":"Philips","f":"🇳🇱","c":"NL","s":"Bildgebung & Connected Care",
     "q":'Philips (medical OR healthcare OR imaging OR MRI OR "health technology" OR hospital)'},
    {"n":"Fresenius Medical Care","f":"🇩🇪","c":"DE","s":"Dialyse"},
    {"n":"Roche Diagnostics","f":"🇨🇭","c":"CH","s":"Diagnostik",
     "q":'Roche (diagnostics OR diagnostic OR assay OR sequencing OR "point of care")'},
    {"n":"EssilorLuxottica","f":"🇫🇷","c":"FR","s":"Optik"},
    {"n":"B. Braun","f":"🇩🇪","c":"DE","s":"Infusion & Chirurgie"},
    {"n":"Smith & Nephew","f":"🇬🇧","c":"UK","s":"Orthopädie & Wundversorgung"},
    {"n":"Getinge","f":"🇸🇪","c":"SE","s":"OP & Intensivmedizin"},
    {"n":"Coloplast","f":"🇩🇰","c":"DK","s":"Stoma & Kontinenz"},
    {"n":"Sonova","f":"🇨🇭","c":"CH","s":"Hörlösungen"},
    {"n":"Demant","f":"🇩🇰","c":"DK","s":"Hörlösungen"},
    {"n":"Sartorius","f":"🇩🇪","c":"DE","s":"Bioprocess & Labor"},
    {"n":"Straumann","f":"🇨🇭","c":"CH","s":"Dental"},
    {"n":"bioMérieux","f":"🇫🇷","c":"FR","s":"Diagnostik"},
    {"n":"Drägerwerk","f":"🇩🇪","c":"DE","s":"Beatmung & Sicherheit"},
    {"n":"Mölnlycke","f":"🇸🇪","c":"SE","s":"Wundversorgung & OP"},
    {"n":"ConvaTec","f":"🇬🇧","c":"UK","s":"Wundversorgung & Stoma"},
    {"n":"Qiagen","f":"🇳🇱","c":"NL","s":"Molekulardiagnostik"},
    {"n":"Carl Zeiss Meditec","f":"🇩🇪","c":"DE","s":"Ophthalmologie"},
    {"n":"Paul Hartmann","f":"🇩🇪","c":"DE","s":"Wundversorgung & Hygiene"},
    {"n":"Elekta","f":"🇸🇪","c":"SE","s":"Strahlentherapie"},
    {"n":"Gerresheimer","f":"🇩🇪","c":"DE","s":"Drug Delivery & Verpackung"},
    {"n":"Ottobock","f":"🇩🇪","c":"DE","s":"Prothetik & Orthopädie"},
    {"n":"Ambu","f":"🇩🇰","c":"DK","s":"Endoskopie"},
    {"n":"Karl Storz","f":"🇩🇪","c":"DE","s":"Endoskopie"},
    {"n":"Bracco","f":"🇮🇹","c":"IT","s":"Kontrastmittel"},
    {"n":"LivaNova","f":"🇬🇧","c":"UK","s":"Kardio & Neuromodulation"},
    {"n":"DiaSorin","f":"🇮🇹","c":"IT","s":"Diagnostik"},
    {"n":"Tecan","f":"🇨🇭","c":"CH","s":"Laborautomation"},
    {"n":"Biotronik","f":"🇩🇪","c":"DE","s":"Herzrhythmus"},
    {"n":"Amplifon","f":"🇮🇹","c":"IT","s":"Hörakustik"},
    {"n":"Arjo","f":"🇸🇪","c":"SE","s":"Patientenmobilität"},
    {"n":"Brainlab","f":"🇩🇪","c":"DE","s":"OP-Navigation & Software"},
    {"n":"Ypsomed","f":"🇨🇭","c":"CH","s":"Injektionssysteme"},
    {"n":"Fresenius Kabi","f":"🇩🇪","c":"DE","s":"Infusion & Ernährung"},
    {"n":"Stratec","f":"🇩🇪","c":"DE","s":"Diagnostiksysteme"},
    {"n":"Sectra","f":"🇸🇪","c":"SE","s":"Bildgebungs-IT"},
    {"n":"Eppendorf","f":"🇩🇪","c":"DE","s":"Laborgeräte"},
    {"n":"Stevanato","f":"🇮🇹","c":"IT","s":"Drug Delivery"},
    {"n":"Guerbet","f":"🇫🇷","c":"FR","s":"Kontrastmittel & Radiologie"},
    {"n":"Vitrolife","f":"🇸🇪","c":"SE","s":"Fertilität"},
    {"n":"MED-EL","f":"🇦🇹","c":"AT","s":"Cochlea-Implantate"},
    {"n":"Nemera","f":"🇫🇷","c":"FR","s":"Drug Delivery"},
    {"n":"Hamilton Medical","f":"🇨🇭","c":"CH","s":"Beatmung"},
    {"n":"Eckert & Ziegler","f":"🇩🇪","c":"DE","s":"Radiopharma"},
    {"n":"Sebia","f":"🇫🇷","c":"FR","s":"Diagnostik"},
    {"n":"Lohmann & Rauscher","f":"🇩🇪","c":"DE","s":"Wundversorgung"},
    {"n":"Richard Wolf","f":"🇩🇪","c":"DE","s":"Endoskopie"},
    {"n":"Esaote","f":"🇮🇹","c":"IT","s":"Ultraschall & MRT"},
    {"n":"Bauerfeind","f":"🇩🇪","c":"DE","s":"Orthopädie & Bandagen"},
]

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
TAG_RE = re.compile(r"<[^>]+>")

def clean(text, limit=240):
    if not text:
        return ""
    text = html.unescape(TAG_RE.sub("", text))
    text = re.sub(r"\s+", " ", text).strip()
    return (text[: limit - 1] + "…") if len(text) > limit else text

def to_ms(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return int(time.mktime(t) * 1000)
            except Exception:
                pass
    return 0

# ── Themen-Feeds einsammeln ─────────────────────────────────────────────────
def collect_feeds():
    items, status = [], []
    for name, url in FEEDS:
        try:
            d = feedparser.parse(url)
            n = 0
            for e in (d.entries or []):
                title = (e.get("title") or "").strip()
                link = (e.get("link") or "").strip()
                if not title or not link:
                    continue
                items.append({"title": title, "link": link,
                              "summary": clean(e.get("summary") or e.get("description") or ""),
                              "date": to_ms(e), "source": name})
                n += 1
            status.append({"name": name, "ok": n > 0, "count": n})
            print(f"  Feed {name}: {n}")
        except Exception as ex:
            status.append({"name": name, "ok": False, "count": 0})
            print(f"  Feed {name}: FEHLER {ex}")
    seen, unique = set(), []
    for it in items:
        k = it["title"].lower()
        if k not in seen:
            seen.add(k); unique.append(it)
    unique.sort(key=lambda x: x["date"], reverse=True)
    return unique, status

# ── Unternehmens-News via Google News einsammeln ────────────────────────────
def fetch_company_news(co, top=8):
    query = co.get("q") or '"%s"' % co["n"]
    url = GOOGLE_NEWS.format(q=urllib.parse.quote(query))
    out = []
    try:
        d = feedparser.parse(url)
        for e in (d.entries or []):
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            if not title or not link:
                continue
            # Publisher ermitteln und ggf. aus dem Titel entfernen ("Schlagzeile - Reuters")
            src = ""
            s = e.get("source")
            if s and getattr(s, "get", None):
                src = (s.get("title") or "").strip()
            if not src and " - " in title:
                title, src = title.rsplit(" - ", 1)
            out.append({"title": title.strip(), "link": link,
                        "summary": "", "date": to_ms(e), "source": src or "Google News"})
    except Exception as ex:
        print(f"  Firma {co['n']}: FEHLER {ex}")
        return []
    seen, uniq = set(), []
    for it in out:
        k = it["title"].lower()
        if k not in seen:
            seen.add(k); uniq.append(it)
    uniq.sort(key=lambda x: x["date"], reverse=True)
    return uniq[:top]

def collect_companies():
    result = []
    for co in COMPANIES:
        news = fetch_company_news(co)
        item = {k: co[k] for k in ("n", "f", "c", "s")}
        item["news"] = news
        result.append(item)
        print(f"  Firma {co['n']}: {len(news)}")
        time.sleep(0.25)  # höflich gegenüber Google News
    return result

def build_html(items, status, companies):
    built = datetime.now(timezone.utc).isoformat()
    tpl = TEMPLATE
    tpl = tpl.replace("__DATA__", json.dumps(items, ensure_ascii=False))
    tpl = tpl.replace("__STATUS__", json.dumps(status, ensure_ascii=False))
    tpl = tpl.replace("__COMPANIES__", json.dumps(companies, ensure_ascii=False))
    tpl = tpl.replace("__BUILT__", built)
    tpl = tpl.replace("__SOURCES__", str(sum(1 for s in status if s["ok"])))
    tpl = tpl.replace("__TOTAL__", str(len(FEEDS)))
    return tpl

def main():
    print("Sammle Themen-Feeds…")
    items, status = collect_feeds()
    print("Sammle Unternehmens-News (Google News)…")
    companies = collect_companies()
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(build_html(items, status, companies))
    total_co = sum(len(c["news"]) for c in companies)
    print(f"Fertig: {len(items)} Feed-Artikel, {total_co} Firmen-Treffer → public/index.html")

# ─────────────────────────────────────────────────────────────────────────────
TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="MedTech Daily">
<meta name="theme-color" content="#0B1C3A">
<title>MedTech Daily</title>
<style>
  :root{--navy:#0B1C3A;--navy-mid:#132847;--cyan:#00C2CB;--cyan-dim:rgba(0,194,203,.15);
    --white:#F7F9FC;--muted:#8A9BB0;--border:rgba(138,155,176,.18);--card-bg:#0F2240;--green:#2ECC8F}
  *{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:var(--navy);
    color:var(--white);min-height:100vh;display:flex;flex-direction:column;-webkit-text-size-adjust:100%;text-size-adjust:100%}
  a{color:inherit;text-decoration:none}
  header{background:var(--navy-mid);border-bottom:1px solid var(--border);padding:0 max(22px,env(safe-area-inset-right)) 0 max(22px,env(safe-area-inset-left));height:58px;display:flex;
    align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
  .logo{display:flex;align-items:center;gap:10px}
  .logo-icon{width:30px;height:30px;background:var(--cyan);border-radius:8px;display:flex;align-items:center;justify-content:center}
  .logo-icon svg{width:17px;height:17px}
  .logo-text{font-size:15px;font-weight:700;letter-spacing:-.3px}.logo-text span{color:var(--cyan)}
  .live-badge{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;letter-spacing:.08em;color:var(--cyan);text-transform:uppercase}
  .pulse-dot{width:7px;height:7px;border-radius:50%;background:var(--cyan);animation:pulse 2s ease-in-out infinite}
  @keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.7)}}
  .app-body{display:flex;flex:1}
  nav{width:212px;flex-shrink:0;background:var(--navy-mid);border-right:1px solid var(--border);padding:18px 0;
    position:sticky;top:58px;height:calc(100vh - 58px);overflow-y:auto}
  .nav-label{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);padding:0 18px 8px}
  .nav-item{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 18px;cursor:pointer;
    border-left:3px solid transparent;transition:all .15s;font-size:13.5px;color:var(--muted);user-select:none}
  .nav-item .l{display:flex;align-items:center;gap:10px}
  .nav-item:hover{background:rgba(0,194,203,.06);color:var(--white)}
  .nav-item.active{background:var(--cyan-dim);color:var(--cyan);border-left-color:var(--cyan);font-weight:600}
  .nav-count{font-size:11px;background:rgba(138,155,176,.15);color:var(--muted);padding:1px 7px;border-radius:10px;min-width:22px;text-align:center}
  .nav-item.active .nav-count{background:rgba(0,194,203,.25);color:var(--cyan)}
  .nav-div{height:1px;background:var(--border);margin:12px 18px}
  main{flex:1;width:100%;max-width:1120px;margin:0 auto;padding:24px;
    padding-bottom:calc(24px + env(safe-area-inset-bottom));
    padding-left:max(24px,env(safe-area-inset-left));padding-right:max(24px,env(safe-area-inset-right))}
  .mode-switch{display:inline-flex;background:var(--navy-mid);border:1px solid var(--border);border-radius:10px;padding:4px;margin-bottom:22px;gap:4px}
  .mode-btn{border:none;background:transparent;color:var(--muted);font-size:14px;font-weight:600;padding:9px 18px;border-radius:7px;cursor:pointer;display:flex;align-items:center;gap:7px;transition:all .15s}
  .mode-btn.active{background:var(--cyan);color:var(--navy)}
  .cat-bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px}
  .chip{display:inline-flex;align-items:center;gap:7px;background:var(--card-bg);border:1px solid var(--border);
    color:var(--muted);font-size:14px;font-weight:600;padding:11px 16px;border-radius:22px;cursor:pointer;transition:all .15s;user-select:none}
  .chip:hover{border-color:rgba(0,194,203,.4);color:var(--white)}
  .chip.active{background:var(--cyan-dim);border-color:var(--cyan);color:var(--cyan)}
  .chip .cc{font-size:11px;font-weight:700;background:rgba(138,155,176,.16);color:var(--muted);padding:1px 7px;border-radius:11px;min-width:20px;text-align:center}
  .chip.active .cc{background:rgba(0,194,203,.25);color:var(--cyan)}
  .briefing{background:linear-gradient(135deg,#132847,#0F2240);border:1px solid var(--border);border-radius:14px;padding:20px 22px;margin-bottom:26px}
  .brief-head{display:flex;align-items:center;gap:9px;margin-bottom:4px}
  .brief-title{font-size:17px;font-weight:700;letter-spacing:-.3px}
  .brief-sub{font-size:12px;color:var(--muted);margin-bottom:16px}
  .brief-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
  .brief-item{display:block;padding:12px 14px;background:rgba(0,194,203,.05);border:1px solid var(--border);border-radius:10px;transition:border-color .15s}
  .brief-item:hover{border-color:rgba(0,194,203,.4)}
  .brief-item .src{font-size:9.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--cyan)}
  .brief-item .t{font-size:13px;font-weight:600;line-height:1.35;margin-top:5px}
  .sec-head{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:16px;gap:14px}
  .sec-title{font-size:20px;font-weight:700;letter-spacing:-.4px}
  .sec-sub{font-size:13px;color:var(--muted);margin-top:3px}
  .meta-bar{font-size:12px;color:var(--muted);margin-bottom:16px;display:flex;gap:14px;flex-wrap:wrap}
  .meta-bar b{color:var(--cyan);font-weight:600}
  .grid{display:grid;grid-template-columns:1fr;gap:13px}
  .card{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:17px 19px;transition:border-color .2s,transform .15s;display:block}
  .card:hover{border-color:rgba(0,194,203,.35);transform:translateY(-1px)}
  .card-meta{display:flex;align-items:center;gap:8px;margin-bottom:9px;flex-wrap:wrap}
  .src-tag{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 8px;border-radius:4px;background:var(--cyan-dim);color:var(--cyan)}
  .new-tag{font-size:9.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:3px 7px;border-radius:4px;background:rgba(46,204,143,.18);color:var(--green)}
  .time{font-size:11px;color:var(--muted);margin-left:auto}
  .card-title{font-size:15px;font-weight:600;line-height:1.4;margin-bottom:7px}
  .card:hover .card-title{color:var(--cyan)}
  .card-body{font-size:13.5px;line-height:1.6;color:var(--muted)}
  .card-foot{display:flex;align-items:center;gap:8px;margin-top:11px;padding-top:11px;border-top:1px solid var(--border);font-size:11.5px;color:var(--muted)}
  .tags{display:flex;gap:6px;flex-wrap:wrap}
  .cat-tag{background:rgba(138,155,176,.1);padding:2px 7px;border-radius:4px;font-size:10.5px}
  .read{margin-left:auto;color:var(--cyan);font-weight:600;font-size:11.5px}
  .empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px 20px;text-align:center;color:var(--muted)}
  .empty .i{font-size:40px;margin-bottom:12px}.empty .t{font-size:15px;font-weight:600;color:var(--white);margin-bottom:5px}.empty .d{font-size:13px;max-width:340px;line-height:1.55}
  .co-search{width:100%;background:var(--navy-mid);border:1px solid var(--border);border-radius:9px;color:var(--white);font-size:14px;padding:11px 14px;margin-bottom:18px}
  .co-search::placeholder{color:var(--muted)}
  .co-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:11px}
  .co-card{background:var(--card-bg);border:1px solid var(--border);border-radius:11px;padding:14px 15px;cursor:pointer;transition:border-color .15s,transform .15s;position:relative}
  .co-card:hover{border-color:rgba(0,194,203,.4);transform:translateY(-1px)}
  .co-rank{position:absolute;top:11px;right:13px;font-size:11px;font-weight:700;color:var(--muted)}
  .co-name{font-size:14px;font-weight:700;letter-spacing:-.2px;padding-right:26px}
  .co-meta{font-size:11.5px;color:var(--muted);margin-top:3px}
  .co-badge{display:inline-flex;align-items:center;gap:5px;margin-top:10px;font-size:11px;font-weight:700;padding:3px 9px;border-radius:20px}
  .co-badge.has{background:rgba(46,204,143,.16);color:var(--green)}
  .co-badge.none{background:rgba(138,155,176,.12);color:var(--muted)}
  .back-link{display:inline-flex;align-items:center;gap:6px;color:var(--cyan);font-size:13px;font-weight:600;cursor:pointer;margin-bottom:14px}
  ::-webkit-scrollbar{width:5px}::-webkit-scrollbar-thumb{background:var(--border);border-radius:10px}
  /* Querformat (iPad Pro): zwei Karten-Spalten nutzen die Breite */
  @media(min-width:1000px){.grid{grid-template-columns:1fr 1fr}}
  /* Touch-Geräte: keinen klebrigen Hover-Zustand nach dem Tippen, klares Tipp-Feedback */
  @media(hover:none){
    .card:hover,.co-card:hover,.brief-item:hover,.chip:hover,.mode-btn:hover{transform:none}
    .card:active,.co-card:active,.brief-item:active{border-color:rgba(0,194,203,.5)}
    .chip:active{background:var(--cyan-dim);border-color:var(--cyan)}
    .mode-btn:active{opacity:.6}
  }
  @media(max-width:680px){
    main{padding:16px;padding-bottom:calc(16px + env(safe-area-inset-bottom))}
    .brief-grid{grid-template-columns:1fr}
  }
</style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-icon"><svg viewBox="0 0 24 24" fill="none" stroke="#0B1C3A" stroke-width="2.5" stroke-linecap="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg></div>
    <div class="logo-text">Med<span>Tech</span> Daily</div>
  </div>
  <div class="live-badge"><div class="pulse-dot"></div><span id="builtAt"></span></div>
</header>
<div class="app-body">
  <main>
    <div class="mode-switch" id="modeSwitch">
      <button class="mode-btn active" id="mbTopic" onclick="setMode('topic')">🗂 Themen</button>
      <button class="mode-btn" id="mbCompany" onclick="setMode('company')">🏢 Unternehmen</button>
    </div>
    <div id="topicView">
      <div class="cat-bar" id="catBar"></div>
      <div class="briefing" id="briefing"></div>
      <div class="sec-head">
        <div><div class="sec-title" id="secTitle">🔭 Gesamtübersicht</div>
        <div class="sec-sub" id="secSub">Alle aktuellen Entwicklungen aus echten MedTech-Fachportalen</div></div>
      </div>
      <div class="meta-bar" id="metaBar"></div>
      <div id="container"></div>
    </div>
    <div id="companyView" style="display:none"></div>
  </main>
</div>
<script>
  const DATA = __DATA__;
  const STATUS = __STATUS__;
  const COMPANIES = __COMPANIES__;
  const BUILT = "__BUILT__";
  const SOURCES_OK = __SOURCES__, SOURCES_TOTAL = __TOTAL__;

  const CATS = {
    overview:{label:"🔭 Gesamtübersicht",sub:"Alle aktuellen Entwicklungen aus echten MedTech-Fachportalen",kw:null},
    imaging:{label:"🩻 Bildgebung & KI",sub:"Radiologie, MRT, CT und KI-gestützte Bildanalyse",kw:["imaging","radiolog","mri","ct scan"," ct ","x-ray","ultrasound","scan","ai diagnos","deep learning","algorithm","artificial intelligence"]},
    implants:{label:"🦾 Implantate & Robotik",sub:"Implantate, Chirurgieroboter, Neuroprothesen",kw:["implant","pacemaker","robot","prosthe","neuro","cochlear","stimulat","exoskelet","brain"]},
    diagnostics:{label:"🧬 Diagnostik & Lab",sub:"IVD, Point-of-Care, Biomarker, Laborautomation",kw:["diagnos","ivd","assay","biomarker","blood test","lab ","glucose","sensor","point-of-care","liquid biopsy","screening"]},
    digital:{label:"📱 Digital Health",sub:"Wearables, Apps, Telemedizin, vernetzte Geräte",kw:["digital health","wearable","app","telehealth","telemedicine","remote monitor","software","smartphone","connected","dtx","platform"]},
    regulation:{label:"📋 Regulierung & MDR",sub:"FDA, EU MDR, Zulassungen, Rückrufe",kw:["fda","mdr","regulat","approval","clearance","510(k)","510k","recall","ce mark","warning letter","de novo","compliance","eudamed"]},
    startups:{label:"🚀 Startups & Deals",sub:"Finanzierung, Übernahmen, Investitionen",kw:["funding","raise","series ","million","billion","acquisition","acquire","ipo","invest","startup","venture","deal","merger"]},
    surgery:{label:"🔬 Chirurgie & OR",sub:"Minimalinvasiv, navigationsgestützt, smarter OP",kw:["surg","operat","minimally invasive","laparoscop","catheter","ablation","endoscop"]},
    research:{label:"📰 Forschung & Studien",sub:"Klinische Studien, Publikationen, Durchbrüche",kw:["study","trial","research","clinical","data show","results","university","scientist","published","breakthrough"]},
    global:{label:"🌍 International",sub:"Globale Märkte und internationale Entwicklungen",kw:["china","europe","eu ","asia","japan","india","uk ","germany","global","international","market"]},
  };

  let mode = "topic", cur = "overview", coQuery = "";

  const bd = new Date(BUILT);
  document.getElementById("builtAt").textContent = "Stand " + bd.toLocaleString("de-DE",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"});

  function filt(key){const c=CATS[key];if(!c.kw)return DATA;
    return DATA.filter(i=>{const h=(i.title+" "+i.summary).toLowerCase();return c.kw.some(k=>h.includes(k));});}
  function relT(ts){if(!ts)return"";const m=Math.round((Date.now()-ts)/6e4);if(m<60)return"vor "+m+" Min";
    const h=Math.round(m/60);if(h<24)return"vor "+h+" Std";return"vor "+Math.round(h/24)+" Tg";}
  function mCats(i){const h=(i.title+" "+(i.summary||"")).toLowerCase();const t=[];
    for(const[k,c]of Object.entries(CATS)){if(k==="overview"||!c.kw)continue;if(c.kw.some(w=>h.includes(w)))t.push(c.label);if(t.length>=2)break;}return t;}

  function cardHTML(i){
    const isNew=i.date&&(Date.now()-i.date)<864e5;const tags=mCats(i);
    return `<a class="card" href="${i.link}" target="_blank" rel="noopener">
      <div class="card-meta"><span class="src-tag">${i.source}</span>${isNew?'<span class="new-tag">● Neu</span>':''}<span class="time">${relT(i.date)}</span></div>
      <div class="card-title">${i.title}</div>${i.summary?`<div class="card-body">${i.summary}</div>`:''}
      <div class="card-foot"><div class="tags">${tags.map(t=>`<span class="cat-tag">${t}</span>`).join('')}</div><span class="read">Artikel lesen →</span></div></a>`;
  }

  function setMode(m){
    mode=m;
    document.getElementById("mbTopic").classList.toggle("active",m==="topic");
    document.getElementById("mbCompany").classList.toggle("active",m==="company");
    document.getElementById("topicView").style.display = m==="topic"?"block":"none";
    document.getElementById("companyView").style.display = m==="company"?"block":"none";
    if(m==="topic") renderTopic(); else renderCompanyDir();
  }

  /* THEMEN */
  function renderCatBar(){
    const order=["overview","imaging","implants","diagnostics","digital","regulation","startups","surgery","research","global"];
    const chip=k=>{const c=CATS[k];const n=filt(k).length;
      return `<div class="chip ${k===cur?'active':''}" onclick="sel('${k}')">${c.label}<span class="cc">${n}</span></div>`;};
    document.getElementById("catBar").innerHTML=order.map(chip).join("");
  }
  function sel(k){cur=k;const c=CATS[k];document.getElementById("secTitle").textContent=c.label;
    document.getElementById("secSub").textContent=c.sub;renderCatBar();renderTopic();}
  function briefing(){
    const top=DATA.slice(0,6);
    const items=top.map(i=>`<a class="brief-item" href="${i.link}" target="_blank" rel="noopener">
      <div class="src">${i.source}</div><div class="t">${i.title}</div></a>`).join("");
    document.getElementById("briefing").innerHTML=
      `<div class="brief-head"><span style="font-size:18px">📋</span><span class="brief-title">Heutiges Briefing</span></div>
       <div class="brief-sub">Die ${top.length} aktuellsten Schlagzeilen quer durch alle Quellen</div>
       <div class="brief-grid">${items}</div>`;
  }
  function renderTopic(){
    briefing(); renderCatBar();
    const items=filt(cur);
    document.getElementById("metaBar").innerHTML=
      `<span><b>${items.length}</b> Artikel</span><span>Quellen: <b>${SOURCES_OK}/${SOURCES_TOTAL}</b> aktiv</span><span>Gesamt heute: <b>${DATA.length}</b></span>`;
    const c=document.getElementById("container");
    if(!items.length){c.innerHTML=`<div class="empty"><div class="i">🔍</div><div class="t">Aktuell keine Artikel hier</div><div class="d">Schau in „Gesamtübersicht" oder morgen wieder rein.</div></div>`;return;}
    c.innerHTML=`<div class="grid">${items.map(cardHTML).join("")}</div>`;
  }

  /* UNTERNEHMEN (News je Firma aus Google News, im Build eingesammelt) */
  function setCoQuery(v){coQuery=v.toLowerCase();renderCompanyDir(true);}
  function renderCompanyDir(keepFocus){
    const v=document.getElementById("companyView");
    const rows=COMPANIES.map((co,idx)=>({co,idx,n:(co.news||[]).length}))
      .filter(x=>{if(!coQuery)return true;const h=(x.co.n+" "+x.co.s+" "+x.co.c).toLowerCase();return h.includes(coQuery);});
    const withNews=COMPANIES.filter(co=>(co.news||[]).length>0).length;
    const cards=rows.map(x=>{const has=x.n>0;
      return `<div class="co-card" onclick="selCompany(${x.idx})">
        <div class="co-rank">#${x.idx+1}</div>
        <div class="co-name">${x.co.n}</div>
        <div class="co-meta">${x.co.f} ${x.co.c} · ${x.co.s}</div>
        <div class="co-badge ${has?'has':'none'}">${has?('● '+x.n+' News'):'keine News'}</div>
      </div>`;}).join("");
    v.innerHTML=
      `<div class="sec-head"><div>
        <div class="sec-title">🏢 Größte MedTech-Unternehmen Europas</div>
        <div class="sec-sub">Top 50 nach ungefährem Umsatz · News je Firma via Google-News-Suche · <b style="color:var(--cyan)">${withNews}/50</b> mit Treffern</div>
       </div></div>
       <input class="co-search" id="coSearch" placeholder="Unternehmen, Land oder Bereich suchen…" oninput="setCoQuery(this.value)" value="${coQuery?coQuery:''}">
       <div class="co-grid">${cards||'<div class="empty"><div class="i">🔍</div><div class="t">Keine Treffer</div></div>'}</div>`;
    if(keepFocus){const s=document.getElementById("coSearch");s.focus();s.setSelectionRange(s.value.length,s.value.length);}
  }
  function selCompany(idx){
    const co=COMPANIES[idx];const items=co.news||[];
    const v=document.getElementById("companyView");
    v.innerHTML=
      `<div class="back-link" onclick="renderCompanyDir()">← Alle Unternehmen</div>
       <div class="sec-head"><div>
         <div class="sec-title">${co.n}</div>
         <div class="sec-sub">${co.f} ${co.c} · ${co.s} · #${idx+1} der Top 50</div>
       </div></div>
       <div class="meta-bar"><span><b>${items.length}</b> aktuelle Meldungen · Quelle: Google News</span></div>`+
      (items.length
        ? `<div class="grid">${items.map(cardHTML).join("")}</div>`
        : `<div class="empty"><div class="i">📭</div><div class="t">Keine aktuellen Meldungen zu ${co.n}</div><div class="d">Die Google-News-Suche hat für diese Firma gerade nichts Aktuelles gefunden. Schau morgen wieder rein.</div></div>`);
  }

  if(!DATA.length && !COMPANIES.some(c=>(c.news||[]).length)){
    document.getElementById("topicView").innerHTML=`<div class="empty"><div class="i">📡</div><div class="t">Heute noch keine Daten</div><div class="d">Der nächtliche Build hat nichts geladen. Starte die Action manuell neu oder warte auf den nächsten Lauf.</div></div>`;
    document.getElementById("modeSwitch").style.display="none";
  }else{setMode("topic");}
</script>
</body>
</html>"""

if __name__ == "__main__":
    main()
