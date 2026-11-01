#!/usr/bin/env python3
"""Build landing/whats-new.html (English) and landing/<lang>/whats-new.html from the store changelogs.

The store notes are the one place release texts are written and approved, in every language
the listing carries (fastlane/metadata/android/<locale>/changelogs/<versionCode>.txt). This
page is generated FROM them so it can never drift from the stores: add a release to RELEASES,
run the script, commit both. Releases older than the first changelog file carry only the
English notes that shipped on the App Store at the time (kept inline below).

    python3 landing/build-whats-new.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = os.path.join(ROOT, "fastlane", "metadata", "android")
LANDING = os.path.join(ROOT, "landing")
SITE = "https://snakemeasurer.com"


def page_path(lang):
    """English at /whats-new.html, every other language at /<lang>/whats-new.html."""
    return "/whats-new.html" if lang == "en" else f"/{lang}/whats-new.html"


def home_path(lang):
    return "/" if lang == "en" else f"/{lang}/"

# version shown, release date, Android versionCode whose changelog carries the notes.
RELEASES = [
    ("1.8",   "2026-10-22", 63),
    ("1.7.6", "2026-09-18", 62),
    ("1.7.5", "2026-08-24", 61),
    ("1.7.0", "2026-07-15", 57),
    ("1.6.1", "2026-06-30", 49),
    ("1.6.0", "2026-06-19", 48),
]

# Before the changelog files existed: the App Store "What's New" of the time, English only.
LEGACY = [
    ("1.5", "2026-06-10", [
        "Growth charts — view your snake's progress and share with one tap",
        "Fullscreen chart view — tap any chart to expand",
        "Export charts as PNG, data as CSV",
        "Custom date range — filter analytics by any period",
        "Multiple animal profiles — manage your whole collection",
        "Faster, more reliable cloud sync",
    ]),
    ("1.3.1", "2026-04-19", [
        "Improved cloud sync reliability across devices",
        "Fixed rare cases where photos disappeared after edits",
        "Privacy Policy and Terms of Service links now open correctly",
        "Various stability improvements",
    ]),
]

# Landing language code → store locale folder.
LOCALES = {
    "en": "en-US", "ru": "ru-RU", "es": "es-ES", "fr": "fr-FR", "de": "de-DE", "pt": "pt-BR",
    "it": "it-IT", "uk": "uk", "nl": "nl-NL", "pl": "pl-PL", "ja": "ja-JP", "ko": "ko-KR", "ar": "ar",
}
NAMES = {
    "en": "English", "ru": "Русский", "es": "Español", "fr": "Français", "de": "Deutsch",
    "pt": "Português", "it": "Italiano", "uk": "Українська", "nl": "Nederlands", "pl": "Polski",
    "ja": "日本語", "ko": "한국어", "ar": "العربية",
}
# The page's own words, per language.
UI = {
    "en": {"title": "What's new", "sub": "Every release of Snake Measurer, newest first — what changed and why.", "home": "Home", "pricing": "Pricing", "en_only": "English notes — this release predates the translated changelogs."},
    "ru": {"title": "Что нового", "sub": "Все версии Snake Measurer, новые сверху: что изменилось и зачем.", "home": "Главная", "pricing": "Цены", "en_only": "Заметки на английском: эта версия вышла до переводов."},
    "es": {"title": "Novedades", "sub": "Todas las versiones de Snake Measurer, las más recientes primero. Las mismas notas que ves en App Store y Google Play.", "home": "Inicio", "pricing": "Precios", "en_only": "Notas en inglés: esta versión es anterior a las traducciones."},
    "fr": {"title": "Nouveautés", "sub": "Toutes les versions de Snake Measurer, les plus récentes en premier. Les mêmes notes que sur l'App Store et Google Play.", "home": "Accueil", "pricing": "Tarifs", "en_only": "Notes en anglais : cette version est antérieure aux traductions."},
    "de": {"title": "Neuigkeiten", "sub": "Alle Versionen von Snake Measurer, die neueste zuerst – was sich geändert hat und warum.", "home": "Start", "pricing": "Preise", "en_only": "Hinweise auf Englisch – diese Version erschien vor den Übersetzungen."},
    "pt": {"title": "Novidades", "sub": "Todas as versões do Snake Measurer, as mais recentes primeiro. As mesmas notas que você vê na App Store e no Google Play.", "home": "Início", "pricing": "Preços", "en_only": "Notas em inglês: esta versão é anterior às traduções."},
    "it": {"title": "Novità", "sub": "Tutte le versioni di Snake Measurer, le più recenti per prime. Le stesse note che vedi su App Store e Google Play.", "home": "Home", "pricing": "Prezzi", "en_only": "Note in inglese: questa versione precede le traduzioni."},
    "uk": {"title": "Що нового", "sub": "Усі версії Snake Measurer, нові згори. Ті самі нотатки, що в App Store та Google Play.", "home": "Головна", "pricing": "Ціни", "en_only": "Нотатки англійською: ця версія вийшла до перекладів."},
    "nl": {"title": "Wat is nieuw", "sub": "Elke versie van Snake Measurer, de nieuwste eerst. Dezelfde notities als in de App Store en Google Play.", "home": "Home", "pricing": "Prijzen", "en_only": "Engelse notities: deze versie verscheen vóór de vertalingen."},
    "pl": {"title": "Co nowego", "sub": "Wszystkie wersje Snake Measurer, najnowsze na górze. Te same notatki, które widzisz w App Store i Google Play.", "home": "Start", "pricing": "Cennik", "en_only": "Notatki po angielsku: ta wersja wyszła przed tłumaczeniami."},
    "ja": {"title": "新機能", "sub": "Snake Measurer のすべてのバージョンを新しい順に。何が変わったのか、なぜなのか。", "home": "ホーム", "pricing": "料金", "en_only": "英語のみ：このバージョンは翻訳開始前にリリースされました。"},
    "ko": {"title": "새로운 기능", "sub": "Snake Measurer의 모든 버전, 최신순입니다. App Store와 Google Play에 실린 것과 같은 내용입니다.", "home": "홈", "pricing": "가격", "en_only": "영어 노트: 이 버전은 번역이 시작되기 전에 출시되었습니다."},
    "ar": {"title": "ما الجديد", "sub": "كل إصدارات Snake Measurer، الأحدث أولاً. نفس الملاحظات التي تراها في App Store وGoogle Play.", "home": "الرئيسية", "pricing": "الأسعار", "en_only": "ملاحظات بالإنجليزية: صدر هذا الإصدار قبل الترجمات."},
}


STORIES = os.path.join(ROOT, "landing", "whats-new-stories")


def story_html(code, lang):
    """The site's longer, human text for a release (whats-new-stories/<code>.<lang>.md), as HTML;
    None when that language has none — the page then shows the store notes."""
    path = os.path.join(STORIES, f"{code}.{lang}.md")
    if not os.path.exists(path):
        return None
    paras = [p.strip() for p in open(path, encoding="utf-8").read().split("\n\n") if p.strip()]
    out = []
    for p in paras:
        img = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", p)
        if img:
            alt = img.group(1).replace("&", "&amp;").replace('"', "&quot;")
            out.append(f'<figure class="shot"><img src="{img.group(2)}" alt="{alt}" loading="lazy"></figure>')
            continue
        t = p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        out.append(f"<p>{t}</p>")
    return "".join(out)


# Words for the release posts: back to the list, and the call to open the app.
POST_UI = {
    "en": {"all": "All releases", "open": "Open Snake Measurer", "more": "Read more"},
    "ru": {"all": "Все версии", "open": "Открыть Snake Measurer", "more": "Читать дальше"},
    "es": {"all": "Todas las versiones", "open": "Abrir Snake Measurer", "more": "Leer más"},
    "fr": {"all": "Toutes les versions", "open": "Ouvrir Snake Measurer", "more": "Lire la suite"},
    "de": {"all": "Alle Versionen", "open": "Snake Measurer öffnen", "more": "Weiterlesen"},
    "pt": {"all": "Todas as versões", "open": "Abrir o Snake Measurer", "more": "Ler mais"},
    "it": {"all": "Tutte le versioni", "open": "Apri Snake Measurer", "more": "Continua a leggere"},
    "uk": {"all": "Усі версії", "open": "Відкрити Snake Measurer", "more": "Читати далі"},
    "nl": {"all": "Alle versies", "open": "Snake Measurer openen", "more": "Verder lezen"},
    "pl": {"all": "Wszystkie wersje", "open": "Otwórz Snake Measurer", "more": "Czytaj dalej"},
    "ja": {"all": "すべてのバージョン", "open": "Snake Measurer を開く", "more": "続きを読む"},
    "ko": {"all": "모든 버전", "open": "Snake Measurer 열기", "more": "더 읽기"},
    "ar": {"all": "كل الإصدارات", "open": "افتح Snake Measurer", "more": "اقرأ المزيد"},
}


def post_path(lang, version):
    """A release's own page: /whats-new/1.8/ in English, /<lang>/whats-new/1.8/ otherwise."""
    return f"/whats-new/{version}/" if lang == "en" else f"/{lang}/whats-new/{version}/"


def first_sentence(story):
    """The story's opening sentence, plain text — the post's title and the list's teaser."""
    m = re.search(r"<p>(.*?)</p>", story or "")
    text = re.sub(r"<[^>]+>", "", m.group(1)) if m else ""
    cut = re.search(r"(.+?[.!?。])(\s|$)", text)
    return (cut.group(1) if cut else text).strip()


def story_without_lead(story, lead):
    """The post's body: the opening sentence is already its title, so it is not said twice."""
    m = re.match(r"<p>(.*?)</p>", story)
    if not m or not lead:
        return story
    first = re.sub(r"<[^>]+>", "", m.group(1))
    rest = first[len(lead):].strip() if first.startswith(lead) else first
    head = f"<p>{rest}</p>" if rest else ""
    return head + story[m.end():]


def bullets(path):
    items = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[•\-–*]\s*", "", line)
        items.append(line)
    return items


def build():
    data = {}
    for lang, locale in LOCALES.items():
        releases = []
        for version, date, code in RELEASES:
            path = os.path.join(META, locale, "changelogs", f"{code}.txt")
            fallback = os.path.join(META, "en-US", "changelogs", f"{code}.txt")
            src = path if os.path.exists(path) else fallback
            if not os.path.exists(src):
                sys.exit(f"missing changelog {src}")
            story = story_html(code, lang)
            releases.append({"v": version, "d": date, "items": bullets(src), "en": src == fallback and lang != "en",
                             "story": story, "post": post_path(lang, version) if story else None,
                             "lead": first_sentence(story) if story else None, "code": code})
        for version, date, items in LEGACY:
            releases.append({"v": version, "d": date, "items": items, "en": lang != "en", "story": None})
        data[lang] = releases
    return data


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def releases_html(data, lang):
    ui = UI.get(lang, UI["en"])
    out = []
    for r in data[lang]:
        if r.get("story"):
            more = POST_UI.get(lang, POST_UI["en"])["more"]
            body = f'<p class="lead">{esc(r["lead"])}</p><a class="more" href="{r["post"]}">{esc(more)} \u2192</a>'
        else:
            items = "".join(f"<li>{esc(it)}</li>" for it in r["items"])
            note = f'<p class="en-only">{esc(ui["en_only"])}</p>' if r["en"] else ""
            body = f"<ul>{items}</ul>{note}"
        head = f'<a href="{r["post"]}">{esc(r["v"])}</a>' if r.get("post") else esc(r["v"])
        out.append(f'<section class="release"><div class="release-head"><h2>{head}</h2><time datetime="{r["d"]}">{r["d"]}</time></div>{body}</section>')
    return "".join(out)


def html(data, lang):
    ui = UI.get(lang, UI["en"])
    options = "\n".join(f'                <option value="{k}"{" selected" if k == lang else ""}>{v}</option>' for k, v in NAMES.items())
    hreflang = "\n".join([f'    <link rel="alternate" hreflang="x-default" href="{SITE}{page_path("en")}">'] +
                         [f'    <link rel="alternate" hreflang="{k}" href="{SITE}{page_path(k)}">' for k in NAMES])
    lite = {k: [{kk: vv for kk, vv in r.items() if kk != "story"} for r in v] for k, v in data.items()}
    payload = json.dumps({"ui": UI, "post": POST_UI, "releases": lite}, ensure_ascii=False, separators=(",", ":"))
    return f"""<!DOCTYPE html>
<!-- GENERATED by landing/build-whats-new.py from fastlane/metadata/android/*/changelogs — do not edit by hand. -->
<html lang="{lang}"{' dir="rtl"' if lang == "ar" else ""}>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(ui["title"])} — Snake Measurer</title>
    <meta name="description" content="{esc(ui["sub"])}">
    <link rel="canonical" href="{SITE}{page_path(lang)}">
{hreflang}
    <meta name="robots" content="index, follow">
    <meta name="theme-color" content="#F2F2F7" media="(prefers-color-scheme: light)">
    <meta name="theme-color" content="#141416" media="(prefers-color-scheme: dark)">
    <link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <script>(function(){{try{{var s=localStorage.getItem('landing_theme');var m=(s==='light'||s==='dark')?s:'system';var d=window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches;if(m==='dark'||(m==='system'&&d))document.documentElement.classList.add('dark');}}catch(e){{}}}})();</script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/site.css">
    <style>
        .release {{ background: var(--bg-card); border-radius: 20px; padding: 22px 26px; box-shadow: var(--card-shadow); margin: 0 0 16px; }}
        .release-head {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }}
        .release-head h2 {{ font-size: 24px; margin: 0; }}
        .release-head h2 a {{ color: var(--text); }}
        .release-head time {{ color: var(--text-sec); font-size: 14px; }}
        .release ul {{ margin: 0; padding-left: 20px; }}
        .release li {{ margin: 4px 0; }}
        .release .lead {{ margin: 0 0 8px; font-size: 17px; }}
        .release .more {{ font-weight: 600; }}
        .release .en-only {{ color: var(--text-sec); font-size: 13px; margin: 8px 0 0; }}
    </style>
</head>
<body>
    <header>
        <div class="header-inner">
            <a href="{home_path(lang)}" class="logo"><img src="/icon-192.png" alt="" width="32" height="32"><span>Snake Measurer</span></a>
            <nav class="nav-links">
                <a href="{home_path(lang)}" id="homeLink">{esc(ui["home"])}</a>
                <a href="/pricing.html" id="pricingLink">{esc(ui["pricing"])}</a>
                <select class="lang-select" id="langSelect" aria-label="Language">
{options}
                </select>
            </nav>
        </div>
    </header>
    <main>
        <h1 id="title">{esc(ui["title"])}</h1>
        <p class="subtitle" id="subtitle">{esc(ui["sub"])}</p>
        <div id="releases">{releases_html(data, lang)}</div>
    </main>
    <footer>
        <a href="{home_path(lang)}" id="homeLink2">{esc(ui["home"])}</a> · <a href="/pricing.html" id="pricingLink2">{esc(ui["pricing"])}</a> · <a href="/refund-policy.html">Refund Policy</a>
        <div style="margin-top: 12px;">© 2026 Snake Measurer · <a href="mailto:support@snakemeasurer.com">support@snakemeasurer.com</a></div>
    </footer>
    <script id="data" type="application/json">{payload}</script>
    <script>
    (function() {{
        var D = JSON.parse(document.getElementById('data').textContent);
        var sel = document.getElementById('langSelect');
        /* This page's language is in its address (/de/whats-new.html); the text is already in the
           HTML. Switching changes it in place and moves the address — no reload. */
        var PAGE_LANG = '{lang}';
        function pagePath(l) {{ return l === 'en' ? '/whats-new.html' : '/' + l + '/whats-new.html'; }}
        function homePath(l) {{ return l === 'en' ? '/' : '/' + l + '/'; }}
        function pick() {{
            var h = location.hash.replace('#', '');
            if (D.releases[h] && h !== PAGE_LANG) {{ location.replace(pagePath(h)); }}
            return PAGE_LANG;
        }}
        function esc(s) {{ return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }}
        function fmtDate(iso, lang) {{
            try {{ return new Date(iso + 'T00:00:00').toLocaleDateString(lang, {{ year: 'numeric', month: 'long', day: 'numeric' }}); }}
            catch (e) {{ return iso; }}
        }}
        function render(lang) {{
            var ui = D.ui[lang] || D.ui.en;
            document.documentElement.lang = lang;
            document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
            sel.value = lang;
            document.getElementById('title').textContent = ui.title;
            document.getElementById('subtitle').textContent = ui.sub;
            document.title = ui.title + ' \\u2014 Snake Measurer';
            ['homeLink', 'homeLink2'].forEach(function(id) {{ var a = document.getElementById(id); a.textContent = ui.home; a.href = homePath(lang); }});
            document.querySelector('.logo').href = homePath(lang);
            var canon = document.querySelector('link[rel="canonical"]');
            if (canon) canon.href = 'https://snakemeasurer.com' + pagePath(lang);
            ['pricingLink', 'pricingLink2'].forEach(function(id) {{ document.getElementById(id).textContent = ui.pricing; }});
            var out = '';
            D.releases[lang].forEach(function(r) {{
                out += '<section class="release"><div class="release-head"><h2>' + (r.post ? '<a href="' + r.post + '">' + esc(r.v) + '</a>' : esc(r.v)) + '</h2><time datetime="' + r.d + '">' + esc(fmtDate(r.d, lang)) + '</time></div>';
                if (r.post) {{
                    var more = (D.post[lang] || D.post.en).more;
                    out += '<p class="lead">' + esc(r.lead) + '</p><a class="more" href="' + r.post + '">' + esc(more) + ' \\u2192</a>';
                }} else {{
                    out += '<ul>';
                    r.items.forEach(function(it) {{ out += '<li>' + esc(it) + '</li>'; }});
                    out += '</ul>' + (r.en ? '<p class="en-only">' + esc(ui.en_only) + '</p>' : '');
                }}
                out += '</section>';
            }});
            document.getElementById('releases').innerHTML = out;
        }}
        sel.addEventListener('change', function() {{
            try {{ localStorage.setItem('landing_lang', this.value); }} catch (e) {{}}
            render(this.value);
            history.pushState({{ lang: this.value }}, '', pagePath(this.value));
        }});
        window.addEventListener('popstate', function() {{
            var m = location.pathname.match(/^\\/([a-z]{{2}})\\//);
            render(m && D.releases[m[1]] ? m[1] : 'en');
        }});
        render(pick());
    }})();
    </script>
</body>
</html>
"""


def post_html(data, lang, idx):
    r = data[lang][idx]
    ui = UI.get(lang, UI["en"])
    pu = POST_UI.get(lang, POST_UI["en"])
    title = f"Snake Measurer {r['v']}: {r['lead']}"
    langs_with = [k for k in NAMES if data[k][idx].get("post")]
    hreflang = "\n".join([f'    <link rel="alternate" hreflang="x-default" href="{SITE}{post_path("en", r["v"])}">'] +
                         [f'    <link rel="alternate" hreflang="{k}" href="{SITE}{post_path(k, r["v"])}">' for k in langs_with])
    other = " · ".join(
        f'<a href="{post_path(k, r["v"])}" hreflang="{k}" lang="{k}"{" aria-current=page" if k == lang else ""}>{NAMES[k]}</a>'
        for k in langs_with)
    # Neighbours in this language that also have a post.
    newer = next((data[lang][j] for j in range(idx - 1, -1, -1) if data[lang][j].get("post")), None)
    older = next((data[lang][j] for j in range(idx + 1, len(data[lang])) if data[lang][j].get("post")), None)
    nav = ""
    if older: nav += f'<a href="{older["post"]}">\u2190 {esc(older["v"])}</a>'
    nav += f'<a href="{page_path(lang)}">{esc(pu["all"])}</a>'
    if newer: nav += f'<a href="{newer["post"]}">{esc(newer["v"])} \u2192</a>'
    ld = json.dumps({"@context": "https://schema.org", "@type": "BlogPosting", "headline": title,
                     "datePublished": r["d"], "inLanguage": lang, "url": SITE + post_path(lang, r["v"]),
                     "publisher": {"@type": "Organization", "name": "SerpWidgets"}}, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<!-- GENERATED by landing/build-whats-new.py from landing/whats-new-stories — do not edit by hand. -->
<html lang="{lang}"{' dir="rtl"' if lang == "ar" else ""}>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(re.sub(r'<[^>]+>', '', r['story'])[:300])}">
    <link rel="canonical" href="{SITE}{post_path(lang, r['v'])}">
{hreflang}
    <meta property="og:type" content="article">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:url" content="{SITE}{post_path(lang, r['v'])}">
    <meta property="og:image" content="{SITE}/og-image.png">
    <meta name="robots" content="index, follow">
    <meta name="apple-itunes-app" content="app-id=6760619393">
    <link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <script>(function(){{try{{var s=localStorage.getItem('landing_theme');var m=(s==='light'||s==='dark')?s:'system';var d=window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches;if(m==='dark'||(m==='system'&&d))document.documentElement.classList.add('dark');}}catch(e){{}}}})();</script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/site.css">
    <script type="application/ld+json">{ld}</script>
    <style>
        .meta {{ color: var(--text-sec); font-size: 15px; margin: 0 0 10px; }}
        .story p {{ font-size: 18px; line-height: 1.65; margin: 0 0 16px; }}
        .story strong {{ color: var(--text); }}
        .story .shot {{ margin: 8px 0 24px; text-align: center; }}
        .story .shot img {{ max-width: min(100%, 520px); max-height: 640px; border-radius: 16px; box-shadow: var(--card-shadow); }}
        .cta {{ margin: 24px 0 8px; }}
        .post-nav {{ display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border); }}
        .langs {{ color: var(--text-sec); font-size: 14px; margin-top: 24px; }}
        .langs a {{ color: var(--text-sec); }}
        .langs a[aria-current] {{ color: var(--text); font-weight: 600; }}
    </style>
</head>
<body>
    <header><div class="header-inner">
        <a href="{home_path(lang)}" class="logo"><img src="/icon-192.png" alt="" width="32" height="32"><span>Snake Measurer</span></a>
        <nav class="nav-links"><a href="{page_path(lang)}">{esc(ui["title"])}</a></nav>
    </div></header>
    <main>
        <article>
            <p class="meta">Snake Measurer {esc(r["v"])} · <time datetime="{r["d"]}" id="postDate">{r["d"]}</time></p>
            <h1>{esc(r["lead"])}</h1>
            <div class="story">{story_without_lead(r["story"], r["lead"])}</div>
            <a class="btn cta" href="/app/">{esc(pu["open"])} &rarr;</a>
        </article>
        <nav class="post-nav">{nav}</nav>
        <p class="langs">{other}</p>
    </main>
    <script>
        (function () {{
            var t = document.getElementById('postDate');
            try {{ t.textContent = new Date(t.getAttribute('datetime') + 'T00:00:00').toLocaleDateString('{lang}', {{ year: 'numeric', month: 'long', day: 'numeric' }}); }} catch (e) {{}}
        }})();
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    data = build()
    for lang in NAMES:
        out = os.path.join(LANDING, page_path(lang).lstrip("/"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html(data, lang))
    posts = 0
    for lang in NAMES:
        for idx, r in enumerate(data[lang]):
            if not r.get("post"):
                continue
            out = os.path.join(LANDING, r["post"].strip("/"), "index.html")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(post_html(data, lang, idx))
            posts += 1
    print(f"wrote {len(NAMES)} list pages, {len(data['en'])} releases each, and {posts} release posts")
