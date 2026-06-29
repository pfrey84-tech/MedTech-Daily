#!/usr/bin/env python3
"""
MedTech Daily — Build-Skript (Zeitungs-Edition)

Läuft nachts auf GitHub Actions und schreibt eine fertige, in sich geschlossene
Seite nach public/index.html. Zur Laufzeit wird nichts nachgeladen.

Drei Datenquellen:
  • THEMEN      → 7 kuratierte MedTech-Fachfeeds (RSS)
  • UNTERNEHMEN → Google-News-Suche je Firma
  • MÄRKTE      → Börsenkurse je gelisteter Firma (yfinance, Stand letzter Schluss)
"""

import feedparser, json, re, html, os, time, urllib.parse
from datetime import datetime, timezone

FEEDS = [
    ("MedTech Dive",           "https://www.medtechdive.com/feeds/news/"),
    ("MassDevice",             "https://www.massdevice.com/feed/"),
    ("Medical Device Network", "https://www.medicaldevice-network.com/feed/"),
    ("MedCity News",           "https://medcitynews.com/feed/"),
    ("Medgadget",              "https://www.medgadget.com/feed"),
    ("MedTech Intelligence",   "https://www.medtechintelligence.com/feed/"),
    ("ScienceDaily Devices",   "https://www.sciencedaily.com/rss/health_medicine/medical_devices.xml"),
]

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

# Börsennotierte Firmen → Yahoo-Finance-Tickersymbol (private Firmen fehlen bewusst)
STOCK_TICKERS = [
    ("Siemens Healthineers","SHL.DE"), ("Philips","PHIA.AS"), ("Fresenius Medical Care","FME.DE"),
    ("Roche","ROG.SW"), ("EssilorLuxottica","EL.PA"), ("Smith & Nephew","SN.L"),
    ("Getinge","GETI-B.ST"), ("Coloplast","COLO-B.CO"), ("Sonova","SOON.SW"),
    ("Demant","DEMANT.CO"), ("Sartorius","SRT.DE"), ("Straumann","STMN.SW"),
    ("bioMérieux","BIM.PA"), ("Drägerwerk","DRW3.DE"), ("ConvaTec","CTEC.L"),
    ("Qiagen","QIA.DE"), ("Zeiss Meditec","AFX.DE"), ("Elekta","EKTA-B.ST"),
    ("Gerresheimer","GXI.DE"), ("Ambu","AMBU-B.CO"), ("LivaNova","LIVN"),
    ("DiaSorin","DIA.MI"), ("Tecan","TECN.SW"), ("Amplifon","AMP.MI"),
    ("Arjo","ARJO-B.ST"), ("Ypsomed","YPSN.SW"), ("Stratec","SBS.DE"),
    ("Sectra","SECT-B.ST"), ("Stevanato","STVN"), ("Guerbet","GBT.PA"),
    ("Vitrolife","VITR.ST"), ("Eckert & Ziegler","EUZ.DE"),
]

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
TAG_RE = re.compile(r"<[^>]+>")

def clean(text, limit=240):
    if not text: return ""
    text = html.unescape(TAG_RE.sub("", text))
    text = re.sub(r"\s+", " ", text).strip()
    return (text[: limit - 1] + "…") if len(text) > limit else text

def to_ms(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try: return int(time.mktime(t) * 1000)
            except Exception: pass
    return 0

def collect_feeds():
    items, status = [], []
    for name, url in FEEDS:
        try:
            d = feedparser.parse(url); n = 0
            for e in (d.entries or []):
                title = (e.get("title") or "").strip(); link = (e.get("link") or "").strip()
                if not title or not link: continue
                items.append({"title": title, "link": link,
                              "summary": clean(e.get("summary") or e.get("description") or ""),
                              "date": to_ms(e), "source": name}); n += 1
            status.append({"name": name, "ok": n > 0, "count": n}); print(f"  Feed {name}: {n}")
        except Exception as ex:
            status.append({"name": name, "ok": False, "count": 0}); print(f"  Feed {name}: FEHLER {ex}")
    seen, unique = set(), []
    for it in items:
        k = it["title"].lower()
        if k not in seen: seen.add(k); unique.append(it)
    unique.sort(key=lambda x: x["date"], reverse=True)
    return unique, status

def fetch_company_news(co, top=8):
    query = co.get("q") or '"%s"' % co["n"]
    url = GOOGLE_NEWS.format(q=urllib.parse.quote(query)); out = []
    try:
        d = feedparser.parse(url)
        for e in (d.entries or []):
            title = (e.get("title") or "").strip(); link = (e.get("link") or "").strip()
            if not title or not link: continue
            src = ""; s = e.get("source")
            if s and getattr(s, "get", None): src = (s.get("title") or "").strip()
            if not src and " - " in title: title, src = title.rsplit(" - ", 1)
            out.append({"title": title.strip(), "link": link, "summary": "",
                        "date": to_ms(e), "source": src or "Google News"})
    except Exception as ex:
        print(f"  Firma {co['n']}: FEHLER {ex}"); return []
    seen, uniq = set(), []
    for it in out:
        k = it["title"].lower()
        if k not in seen: seen.add(k); uniq.append(it)
    uniq.sort(key=lambda x: x["date"], reverse=True)
    return uniq[:top]

def collect_companies():
    result = []
    for co in COMPANIES:
        news = fetch_company_news(co)
        item = {k: co[k] for k in ("n", "f", "c", "s")}; item["news"] = news
        result.append(item); print(f"  Firma {co['n']}: {len(news)}"); time.sleep(0.25)
    return result

def _g(fi, *keys):
    for k in keys:
        try:
            v = fi[k]
            if v is not None: return v
        except Exception: pass
        v = getattr(fi, k, None)
        if v is not None: return v
    return None

def collect_stocks():
    out = []
    try:
        import yfinance as yf
    except Exception as ex:
        print(f"  yfinance nicht verfügbar: {ex}"); return out
    for name, sym in STOCK_TICKERS:
        try:
            fi = yf.Ticker(sym).fast_info
            price = _g(fi, "last_price", "lastPrice")
            prev  = _g(fi, "previous_close", "previousClose")
            cur   = _g(fi, "currency") or ""
            if price is None: 
                print(f"  Kurs {sym}: kein Preis"); continue
            price = float(price)
            chg = ((price - float(prev)) / float(prev) * 100) if prev else 0.0
            out.append({"name": name, "sym": sym, "price": round(price, 2),
                        "cur": cur, "chg": round(chg, 2)})
            print(f"  Kurs {name}: {price} {cur} ({chg:+.2f}%)")
        except Exception as ex:
            print(f"  Kurs {sym}: FEHLER {ex}")
        time.sleep(0.1)
    return out

def build_html(items, status, companies, stocks):
    built = datetime.now(timezone.utc).isoformat()
    tpl = TEMPLATE
    tpl = tpl.replace("__DATA__", json.dumps(items, ensure_ascii=False))
    tpl = tpl.replace("__STATUS__", json.dumps(status, ensure_ascii=False))
    tpl = tpl.replace("__COMPANIES__", json.dumps(companies, ensure_ascii=False))
    tpl = tpl.replace("__STOCKS__", json.dumps(stocks, ensure_ascii=False))
    tpl = tpl.replace("__BUILT__", built)
    tpl = tpl.replace("__SOURCES__", str(sum(1 for s in status if s["ok"])))
    tpl = tpl.replace("__TOTAL__", str(len(FEEDS)))
    return tpl

def main():
    print("Sammle Themen-Feeds…");   items, status = collect_feeds()
    print("Sammle Unternehmens-News…"); companies = collect_companies()
    print("Sammle Börsenkurse…");     stocks = collect_stocks()
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(build_html(items, status, companies, stocks))
    print(f"Fertig: {len(items)} Artikel, {sum(len(c['news']) for c in companies)} Firmen-Treffer, {len(stocks)} Kurse")

# ─────────────────────────────────────────────────────────────────────────────
TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="theme-color" content="#f6f4ef">
<title>MedTech Daily</title>
<style>
  :root{--paper:#f6f4ef;--panel:#fffdf8;--ink:#191714;--soft:#5d564d;--rule:#d3cdc1;--rule2:#a89f90;
    --up:#0a7d3c;--down:#a01020}
  *{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{font-family:Georgia,'Iowan Old Style','Times New Roman',serif;background:var(--paper);color:var(--ink);
    -webkit-text-size-adjust:100%;text-size-adjust:100%;min-height:100vh;
    padding-bottom:calc(46px + env(safe-area-inset-bottom))}
  a{color:inherit;text-decoration:none}
  .kicker,.tab,.sec,.mh-top,.meta-bar,.co-meta,.co-badge,.brief-kicker,.ticker-label,.tk{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif}

  /* MASTHEAD */
  .masthead{background:var(--panel);border-bottom:3px double var(--ink);text-align:center;
    padding:calc(12px + env(safe-area-inset-top)) 20px 14px}
  .mh-top{display:flex;justify-content:space-between;align-items:center;font-size:11px;letter-spacing:.1em;
    text-transform:uppercase;color:var(--soft);border-bottom:1px solid var(--rule);padding-bottom:8px;margin-bottom:12px}
  .mh-title{font-size:clamp(32px,7vw,54px);font-weight:800;letter-spacing:-1px;line-height:.95}
  .mh-sub{font-style:italic;color:var(--soft);font-size:14px;margin-top:8px}

  /* NAVBAR (sticky) */
  .navbar{position:sticky;top:0;z-index:50;background:var(--panel);border-bottom:1px solid var(--rule2)}
  .tabs{display:flex;justify-content:center;border-bottom:1px solid var(--rule)}
  .tab{padding:11px 20px;font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
    color:var(--soft);cursor:pointer;border-bottom:2px solid transparent}
  .tab.active{color:var(--ink);border-bottom-color:var(--ink)}
  .sections{display:flex;gap:2px;overflow-x:auto;white-space:nowrap;padding:7px 12px;scrollbar-width:none}
  .sections::-webkit-scrollbar{display:none}
  .sec{flex:0 0 auto;padding:7px 12px;font-size:12px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;
    color:var(--soft);cursor:pointer}
  .sec.active{color:var(--ink);box-shadow:inset 0 -2px 0 var(--ink)}
  .sec .cc{color:var(--soft);font-weight:700;margin-left:6px;font-size:11px}
  .sec.active .cc{color:var(--ink)}

  main{max-width:1100px;margin:0 auto;padding:22px max(20px,env(safe-area-inset-left)) 30px max(20px,env(safe-area-inset-right))}

  /* BRIEFING / Aufmacher */
  .briefing{border-top:2px solid var(--ink);padding:14px 0 6px;margin-bottom:22px}
  .brief-kicker{font-size:11px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--down);margin-bottom:12px}
  .brief-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:0 26px}
  .brief-item{display:block;padding:11px 0;border-bottom:1px solid var(--rule)}
  .brief-item .src{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--soft)}
  .brief-item .t{font-size:16px;font-weight:700;line-height:1.28;margin-top:4px}
  .brief-item:hover .t{text-decoration:underline}

  .sec-head{margin:6px 0 14px;border-bottom:2px solid var(--ink);padding-bottom:6px}
  .sec-title{font-size:23px;font-weight:800;letter-spacing:-.3px}
  .sec-sub{font-size:13px;color:var(--soft);font-style:italic;margin-top:2px}
  .meta-bar{font-size:11px;color:var(--soft);letter-spacing:.04em;text-transform:uppercase;margin-bottom:16px;display:flex;gap:16px;flex-wrap:wrap}
  .meta-bar b{color:var(--ink)}

  /* ARTIKEL */
  .grid{display:grid;grid-template-columns:1fr;gap:0}
  .card{display:block;padding:16px 0;border-bottom:1px solid var(--rule)}
  .kicker{font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--soft);margin-bottom:6px;display:flex;align-items:center;gap:8px}
  .kicker .new{color:var(--down)}
  .kicker .when{margin-left:auto;font-weight:600;letter-spacing:0}
  .card-title{font-size:19px;font-weight:700;line-height:1.3;margin-bottom:6px}
  .card:hover .card-title{text-decoration:underline}
  .card-body{font-size:15px;line-height:1.55;color:#33302b}
  .card-foot{display:flex;align-items:center;gap:8px;margin-top:9px}
  .cat-tag{font-family:-apple-system,system-ui,sans-serif;font-size:10px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--soft);border:1px solid var(--rule2);padding:1px 7px;border-radius:2px}
  .read{margin-left:auto;font-family:-apple-system,system-ui,sans-serif;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}

  /* UNTERNEHMEN */
  .co-search{width:100%;background:var(--panel);border:1px solid var(--rule2);color:var(--ink);font-size:15px;
    font-family:Georgia,serif;padding:11px 14px;margin-bottom:18px}
  .co-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
  .co-card{background:var(--panel);border:1px solid var(--rule2);padding:13px 15px;cursor:pointer;position:relative}
  .co-card:hover{border-color:var(--ink)}
  .co-rank{position:absolute;top:12px;right:13px;font-size:11px;font-weight:700;color:var(--soft);font-family:-apple-system,system-ui,sans-serif}
  .co-name{font-size:16px;font-weight:700;padding-right:28px}
  .co-meta{font-size:11.5px;color:var(--soft);margin-top:3px}
  .co-badge{display:inline-block;margin-top:11px;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
  .co-badge.has{color:var(--ink)} .co-badge.none{color:var(--soft)}
  .back-link{display:inline-block;font-family:-apple-system,system-ui,sans-serif;font-size:12px;font-weight:700;
    text-transform:uppercase;letter-spacing:.05em;cursor:pointer;margin-bottom:14px}

  .empty{text-align:center;padding:46px 20px;color:var(--soft)}
  .empty .t{font-size:17px;font-weight:700;color:var(--ink);margin-bottom:6px}
  .empty .d{font-size:14px;line-height:1.55;max-width:360px;margin:0 auto}

  /* TICKER (fest unten) */
  .ticker{position:fixed;left:0;right:0;bottom:0;z-index:60;height:calc(40px + env(safe-area-inset-bottom));
    background:#141210;border-top:2px solid var(--ink);display:flex;align-items:stretch;overflow:hidden;
    padding-bottom:env(safe-area-inset-bottom)}
  .ticker-label{flex:0 0 auto;background:#000;color:#fff;font-size:11px;font-weight:800;letter-spacing:.12em;
    text-transform:uppercase;display:flex;align-items:center;padding:0 14px}
  .ticker-wrap{flex:1;overflow:hidden;display:flex;align-items:center}
  .ticker-track{display:inline-flex;white-space:nowrap;animation:scroll 80s linear infinite}
  .tk{display:inline-flex;align-items:center;gap:7px;padding:0 18px;font-size:12.5px;border-right:1px solid #333}
  .tk .nm{color:#bdb6a8;text-transform:uppercase;font-size:10.5px;letter-spacing:.05em}
  .tk .pr{color:#f4f1ea;font-weight:600}
  .tk .up{color:#54d68a;font-weight:600}.tk .down{color:#ff6f6f;font-weight:600}
  @keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-50%)}}

  @media(min-width:1000px){.grid{grid-template-columns:1fr 1fr;column-gap:30px}}
  @media(hover:none){.brief-item:hover .t,.card:hover .card-title{text-decoration:none}.co-card:active{border-color:var(--ink)}}
</style>
</head>
<body>
<header class="masthead">
  <div class="mh-top"><span id="mhDate"></span><span>Medizintechnik · Tägliche Ausgabe</span></div>
  <div class="mh-title">MedTech Daily</div>
  <div class="mh-sub">Nachrichten aus der Medizintechnik — nach Themen und Unternehmen</div>
</header>
<div class="navbar">
  <div class="tabs" id="modeSwitch">
    <div class="tab active" id="mbTopic" onclick="setMode('topic')">Themen</div>
    <div class="tab" id="mbCompany" onclick="setMode('company')">Unternehmen</div>
  </div>
  <div class="sections" id="catBar"></div>
</div>
<main>
  <div id="topicView">
    <div class="briefing" id="briefing"></div>
    <div class="sec-head"><div class="sec-title" id="secTitle">Gesamtübersicht</div>
      <div class="sec-sub" id="secSub">Alle aktuellen Entwicklungen aus MedTech-Fachportalen</div></div>
    <div class="meta-bar" id="metaBar"></div>
    <div id="container"></div>
  </div>
  <div id="companyView" style="display:none"></div>
</main>
<div class="ticker" id="ticker"></div>
<script>
  const DATA = __DATA__;
  const STATUS = __STATUS__;
  const COMPANIES = __COMPANIES__;
  const STOCKS = __STOCKS__;
  const BUILT = "__BUILT__";
  const SOURCES_OK = __SOURCES__, SOURCES_TOTAL = __TOTAL__;

  const CATS = {
    overview:{label:"Gesamtübersicht",sub:"Alle aktuellen Entwicklungen aus MedTech-Fachportalen",kw:null},
    imaging:{label:"Bildgebung & KI",sub:"Radiologie, MRT, CT und KI-gestützte Bildanalyse",kw:["imaging","radiolog","mri","ct scan"," ct ","x-ray","ultrasound","scan","ai diagnos","deep learning","algorithm","artificial intelligence"]},
    implants:{label:"Implantate & Robotik",sub:"Implantate, Chirurgieroboter, Neuroprothesen",kw:["implant","pacemaker","robot","prosthe","neuro","cochlear","stimulat","exoskelet","brain"]},
    diagnostics:{label:"Diagnostik & Lab",sub:"IVD, Point-of-Care, Biomarker, Laborautomation",kw:["diagnos","ivd","assay","biomarker","blood test","lab ","glucose","sensor","point-of-care","liquid biopsy","screening"]},
    digital:{label:"Digital Health",sub:"Wearables, Apps, Telemedizin, vernetzte Geräte",kw:["digital health","wearable","app","telehealth","telemedicine","remote monitor","software","smartphone","connected","dtx","platform"]},
    regulation:{label:"Regulierung & MDR",sub:"FDA, EU MDR, Zulassungen, Rückrufe",kw:["fda","mdr","regulat","approval","clearance","510(k)","510k","recall","ce mark","warning letter","de novo","compliance","eudamed"]},
    startups:{label:"Startups & Deals",sub:"Finanzierung, Übernahmen, Investitionen",kw:["funding","raise","series ","million","billion","acquisition","acquire","ipo","invest","startup","venture","deal","merger"]},
    collab:{label:"Kooperationen",sub:"Partnerschaften, Allianzen, Joint Ventures, Lizenzen, Hyperscaler",
      kw:["partnership","partner with","partners with","partnered","collaborat","alliance","joint venture","teams up","team up","co-develop","strategic partnership","licensing","license agreement","distribution agreement","memorandum","mou"],
      pair:["hyperscaler","amazon web services","aws","azure","microsoft","google cloud","nvidia","oracle","openai","gcp"],
      req:["health","medtech","medical","healthcare","clinical","hospital","patient","diagnos","imaging","device","therap","life science","biotech","pharma","surg","radiolog"]},
    people:{label:"Personen & Ernennungen",sub:"Führungswechsel, Ernennungen, Personalien",kw:["appoint","names ","ceo","cfo","coo","chief executive","chief financial","executive","hire","hires","joins","steps down","stepping down","resign","retire","board of directors","chairman","chair ","president","promot","leadership","succession"]},
    surgery:{label:"Chirurgie & OR",sub:"Minimalinvasiv, navigationsgestützt, smarter OP",kw:["surg","operat","minimally invasive","laparoscop","catheter","ablation","endoscop"]},
    research:{label:"Forschung & Studien",sub:"Klinische Studien, Publikationen, Durchbrüche",kw:["study","trial","research","clinical","data show","results","university","scientist","published","breakthrough"]},
    global:{label:"International",sub:"Globale Märkte und internationale Entwicklungen",kw:["china","europe","eu ","asia","japan","india","uk ","germany","global","international","market"]},
  };
  const CSYM={EUR:"€",USD:"$",GBP:"£"};

  let mode="topic", cur="overview", coQuery="";
  const bd=new Date(BUILT);
  document.getElementById("mhDate").textContent =
    bd.toLocaleDateString("de-DE",{weekday:"long",day:"numeric",month:"long",year:"numeric"}) +
    " · Stand " + bd.toLocaleTimeString("de-DE",{hour:"2-digit",minute:"2-digit"});

  function hasWord(h,w){return new RegExp("(^|[^a-z0-9])"+w+"([^a-z0-9]|$)").test(h);}
  function catMatch(c,h){
    if(c.kw && c.kw.some(k=>h.includes(k)))return true;
    if(c.pair && c.req)return c.pair.some(p=>hasWord(h,p)) && c.req.some(r=>h.includes(r));
    return false;}
  function filt(key){const c=CATS[key];if(!c.kw && !c.pair)return DATA;
    return DATA.filter(i=>catMatch(c,(i.title+" "+i.summary).toLowerCase()));}
  function relT(ts){if(!ts)return"";const m=Math.round((Date.now()-ts)/6e4);if(m<60)return"vor "+m+" Min";
    const h=Math.round(m/60);if(h<24)return"vor "+h+" Std";return"vor "+Math.round(h/24)+" Tg";}
  function mCats(i){const h=(i.title+" "+(i.summary||"")).toLowerCase();const t=[];
    for(const[k,c]of Object.entries(CATS)){if(k==="overview"||(!c.kw&&!c.pair))continue;if(catMatch(c,h))t.push(c.label);if(t.length>=2)break;}return t;}
  function cardHTML(i){const isNew=i.date&&(Date.now()-i.date)<864e5;const tags=mCats(i);
    return `<a class="card" href="${i.link}" target="_blank" rel="noopener">
      <div class="kicker"><span>${i.source}</span>${isNew?'<span class="new">Neu</span>':''}<span class="when">${relT(i.date)}</span></div>
      <div class="card-title">${i.title}</div>${i.summary?`<div class="card-body">${i.summary}</div>`:''}
      <div class="card-foot">${tags.map(t=>`<span class="cat-tag">${t}</span>`).join('')}<span class="read">Weiterlesen →</span></div></a>`;}

  function setMode(m){mode=m;
    document.getElementById("mbTopic").classList.toggle("active",m==="topic");
    document.getElementById("mbCompany").classList.toggle("active",m==="company");
    document.getElementById("topicView").style.display=m==="topic"?"block":"none";
    document.getElementById("companyView").style.display=m==="company"?"block":"none";
    document.getElementById("catBar").style.display=m==="topic"?"flex":"none";
    if(m==="topic")renderTopic();else renderCompanyDir();}

  function renderCatBar(){
    const order=["overview","imaging","implants","diagnostics","digital","regulation","startups","collab","people","surgery","research","global"];
    const sec=k=>{const c=CATS[k];const n=filt(k).length;
      return `<div class="sec ${k===cur?'active':''}" onclick="sel('${k}')">${c.label}<span class="cc">${n}</span></div>`;};
    document.getElementById("catBar").innerHTML=order.map(sec).join("");}
  function sel(k){cur=k;const c=CATS[k];document.getElementById("secTitle").textContent=c.label;
    document.getElementById("secSub").textContent=c.sub;renderCatBar();renderTopic();}
  function briefing(){const top=DATA.slice(0,6);
    const items=top.map(i=>`<a class="brief-item" href="${i.link}" target="_blank" rel="noopener">
      <div class="src">${i.source} · ${relT(i.date)}</div><div class="t">${i.title}</div></a>`).join("");
    document.getElementById("briefing").innerHTML=
      `<div class="brief-kicker">Das Wichtigste heute</div><div class="brief-grid">${items}</div>`;}
  function renderTopic(){briefing();renderCatBar();
    const items=filt(cur);
    document.getElementById("metaBar").innerHTML=
      `<span><b>${items.length}</b> Artikel</span><span>Quellen <b>${SOURCES_OK}/${SOURCES_TOTAL}</b></span><span>Heute gesamt <b>${DATA.length}</b></span>`;
    const c=document.getElementById("container");
    if(!items.length){c.innerHTML=`<div class="empty"><div class="t">Keine Artikel in dieser Rubrik</div><div class="d">Schauen Sie in „Gesamtübersicht" oder morgen wieder rein.</div></div>`;return;}
    c.innerHTML=`<div class="grid">${items.map(cardHTML).join("")}</div>`;}

  function setCoQuery(v){coQuery=v.toLowerCase();renderCompanyDir(true);}
  function renderCompanyDir(keepFocus){
    const v=document.getElementById("companyView");
    const rows=COMPANIES.map((co,idx)=>({co,idx,n:(co.news||[]).length}))
      .filter(x=>{if(!coQuery)return true;const h=(x.co.n+" "+x.co.s+" "+x.co.c).toLowerCase();return h.includes(coQuery);});
    const withNews=COMPANIES.filter(co=>(co.news||[]).length>0).length;
    const cards=rows.map(x=>{const has=x.n>0;
      return `<div class="co-card" onclick="selCompany(${x.idx})"><div class="co-rank">#${x.idx+1}</div>
        <div class="co-name">${x.co.n}</div><div class="co-meta">${x.co.f} ${x.co.c} · ${x.co.s}</div>
        <div class="co-badge ${has?'has':'none'}">${has?(x.n+' Meldungen'):'keine Meldungen'}</div></div>`;}).join("");
    v.innerHTML=
      `<div class="sec-head"><div class="sec-title">Größte MedTech-Unternehmen Europas</div>
        <div class="sec-sub">Top 50 nach ungefährem Umsatz · News je Firma via Google · ${withNews}/50 mit Treffern</div></div>
       <input class="co-search" id="coSearch" placeholder="Unternehmen, Land oder Bereich suchen…" oninput="setCoQuery(this.value)" value="${coQuery?coQuery:''}">
       <div class="co-grid">${cards||'<div class="empty"><div class="t">Keine Treffer</div></div>'}</div>`;
    if(keepFocus){const s=document.getElementById("coSearch");s.focus();s.setSelectionRange(s.value.length,s.value.length);}}
  function selCompany(idx){const co=COMPANIES[idx];const items=co.news||[];
    const v=document.getElementById("companyView");
    v.innerHTML=`<div class="back-link" onclick="renderCompanyDir()">← Alle Unternehmen</div>
       <div class="sec-head"><div class="sec-title">${co.n}</div>
         <div class="sec-sub">${co.f} ${co.c} · ${co.s} · #${idx+1} der Top 50</div></div>
       <div class="meta-bar"><span><b>${items.length}</b> aktuelle Meldungen · Quelle Google News</span></div>`+
      (items.length?`<div class="grid">${items.map(cardHTML).join("")}</div>`
        :`<div class="empty"><div class="t">Keine aktuellen Meldungen zu ${co.n}</div><div class="d">Die Suche hat gerade nichts Aktuelles gefunden. Schauen Sie morgen wieder rein.</div></div>`);}

  function fmtPrice(s){if(s.cur==="GBp")return s.price.toFixed(0)+" p";
    const sym=CSYM[s.cur];return sym?sym+s.price.toFixed(2):s.price.toFixed(2)+" "+(s.cur||"");}
  function renderTicker(){const el=document.getElementById("ticker");
    if(!STOCKS||!STOCKS.length){el.style.display="none";document.body.style.paddingBottom="0";return;}
    const tk=s=>{const up=s.chg>=0;return `<span class="tk"><span class="nm">${s.name}</span><span class="pr">${fmtPrice(s)}</span><span class="${up?'up':'down'}">${up?'▲':'▼'}${Math.abs(s.chg).toFixed(2)}%</span></span>`;};
    const items=STOCKS.map(tk).join("");
    el.innerHTML=`<div class="ticker-label">Märkte</div><div class="ticker-wrap"><div class="ticker-track">${items}${items}</div></div>`;}

  if(!DATA.length && !COMPANIES.some(c=>(c.news||[]).length)){
    document.getElementById("topicView").innerHTML=`<div class="empty"><div class="t">Heute noch keine Daten</div><div class="d">Der nächtliche Build hat nichts geladen. Starten Sie die Action neu oder warten Sie auf den nächsten Lauf.</div></div>`;
    document.querySelector(".navbar").style.display="none";
  }else{setMode("topic");}
  renderTicker();
</script>
</body>
</html>"""

if __name__ == "__main__":
    main()
