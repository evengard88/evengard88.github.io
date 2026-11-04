#!/usr/bin/env python3
"""
One page per language for the landing: English at /, the rest at /ru/, /de/, … — the layout
search engines expect (Google indexes a URL in ONE language; text swapped in by a script on a
single URL is never seen in the other twelve).

Source of truth stays landing/index.html — the English page with every translation in its
script (the `L` table). This script:
  - writes landing/<lang>/index.html with the text, title, description and social tags already
    in that language (no script needed to read it), relative links made absolute;
  - rewrites the hreflang block and the footer language links on every page, the root included;
  - writes landing/sitemap.xml with each page and its language alternates.

Run after editing index.html:   python3 landing/build-lang-pages.py
Needs node (to read the translation table exactly as the browser does).
"""
import datetime
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://snakemeasurer.com"
SRC = os.path.join(HERE, "index.html")

OG_LOCALE = {
    "en": "en_US", "ru": "ru_RU", "es": "es_ES", "fr": "fr_FR", "de": "de_DE", "pt": "pt_BR",
    "it": "it_IT", "uk": "uk_UA", "nl": "nl_NL", "pl": "pl_PL", "ja": "ja_JP", "ko": "ko_KR", "ar": "ar_AR",
}
POLICY_SUFFIX = {"en": ""}  # others: "-<lang>", as the page's own script does


def page_url(code):
    return SITE + ("/" if code == "en" else f"/{code}/")


def path_url(code):
    return "/" if code == "en" else f"/{code}/"


def read_table(src):
    start = src.index("var L = {")
    end = src.index("/* Privacy/terms file suffixes", start)
    js = src[start:end].strip().rstrip(";") + ";\nprocess.stdout.write(JSON.stringify(L));"
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def languages(src):
    sel = src[src.index('id="langSelect"'):]
    sel = sel[:sel.index("</select>")]
    return re.findall(r'<option value="([a-z]{2})">([^<]+)</option>', sel)


def hreflang_block(langs):
    lines = ["    <!-- hreflang — one address per language (build-lang-pages.py) -->",
             f'    <link rel="alternate" hreflang="x-default" href="{page_url("en")}">']
    lines += [f'    <link rel="alternate" hreflang="{c}" href="{page_url(c)}">' for c, _ in langs]
    return "\n".join(lines) + "\n"


def replace_hreflang(page, langs):
    pat = re.compile(r'    <!-- hreflang[^\n]*-->\n(?:    <link rel="alternate" hreflang="[^"]+" href="[^"]+">\n)+')
    if not pat.search(page):
        sys.exit("hreflang block not found")
    return pat.sub(lambda m: hreflang_block(langs), page, count=1)


def lang_links(langs, current):
    parts = []
    for c, name in langs:
        cur = ' aria-current="page"' if c == current else ""
        parts.append(f'<a href="{path_url(c)}" hreflang="{c}" lang="{c}"{cur}>{html.escape(name)}</a>')
    return "".join(parts)


def replace_lang_links(page, langs, current):
    pat = re.compile(r'(<nav class="footer-langs" aria-label="Language">).*?(</nav>)', re.S)
    if not pat.search(page):
        sys.exit("footer-langs slot not found")
    return pat.sub(lambda m: m.group(1) + "<!--LANG_LINKS-->" + lang_links(langs, current) + m.group(2), page, count=1)


def set_attr_content(page, selector_re, value):
    """Set content="…" of the single tag matched by selector_re (a regex for the tag's start)."""
    pat = re.compile(r'(<meta ' + selector_re + r' content=")[^"]*(")')
    if not pat.search(page):
        sys.exit(f"meta not found: {selector_re}")
    return pat.sub(lambda m: m.group(1) + html.escape(value, quote=True) + m.group(2), page, count=1)


def localise(src, L, code, langs):
    s = L.get(code, {})
    en = L["en"]

    def t(key):
        return s.get(key) or en.get(key)

    page = src
    page = page.replace('<html lang="en">', f'<html lang="{code}"' + (' dir="rtl"' if code == "ar" else "") + ">", 1)

    title = f"{t('app_name')} — {t('hero_title')}"
    page = re.sub(r"<title>[^<]*</title>", lambda m: f"<title>{html.escape(title)}</title>", page, count=1)
    page = set_attr_content(page, r'name="description"', t("hero_sub"))
    if s.get("meta_keywords"):
        page = set_attr_content(page, r'name="keywords"', s["meta_keywords"])
    page = set_attr_content(page, r'property="og:title"', title)
    page = set_attr_content(page, r'property="og:description"', t("hero_sub"))
    page = set_attr_content(page, r'name="twitter:title"', title)
    page = set_attr_content(page, r'name="twitter:description"', t("hero_sub"))
    page = set_attr_content(page, r'property="og:url"', page_url(code))
    page = page.replace(f'<link rel="canonical" href="{page_url("en")}">', f'<link rel="canonical" href="{page_url(code)}">', 1)
    page = set_attr_content(page, r'property="og:locale"', OG_LOCALE[code])
    page = page.replace(f'<meta property="og:locale:alternate" content="{OG_LOCALE[code]}">',
                        f'<meta property="og:locale:alternate" content="{OG_LOCALE["en"]}">', 1)

    # Visible text: what the page's script would put there, already in the HTML.
    def text_sub(m):
        key = m.group(3)
        val = t(key)
        return m.group(1) + (html.escape(val, quote=False) if val else m.group(4)) + m.group(5)
    page = re.sub(r'(<(\w+)\b[^>]*\bdata-t="([^"]+)"[^>]*>)(.*?)(</\2>)', text_sub, page, flags=re.S)

    def aria_sub(m):
        val = t(m.group(2))
        return m.group(1) + (html.escape(val, quote=True) if val else m.group(3)) + m.group(4)
    page = re.sub(r'(<[^>]*\bdata-t-aria="([^"]+)"[^>]*\baria-label=")([^"]*)(")', aria_sub, page)

    # Structured data: strings that are an English translation replaced by this language's.
    def ld_sub(m):
        block = m.group(0)
        for key, en_val in en.items():
            if not isinstance(en_val, str) or len(en_val) < 12 or not t(key) or t(key) == en_val:
                continue
            block = block.replace(json.dumps(en_val, ensure_ascii=False)[1:-1], json.dumps(t(key), ensure_ascii=False)[1:-1])
        if '"inLanguage"' not in block:
            block = block.replace('"@context"', f'"inLanguage": "{code}",\n        "@context"', 1)
        return block
    page = re.sub(r'<script type="application/ld\+json">.*?</script>', ld_sub, page, flags=re.S)

    # Store badges and policy links, as the script would set them.
    apple = "en" if code in ("uk", "ar") else code
    page = re.sub(r'src="badges/app-store-en\.svg"', f'src="/badges/app-store-{apple}.svg"', page)
    page = re.sub(r'src="badges/google-play-en\.png"', f'src="/badges/google-play-{code}.png"', page)
    suffix = POLICY_SUFFIX.get(code, f"-{code}")
    page = page.replace('<a href="#" id="privacyLink"', f'<a href="/app/privacy-policy{suffix}.html" id="privacyLink"', 1)
    page = page.replace('<a href="#" id="termsLink"', f'<a href="/app/terms{suffix}.html" id="termsLink"', 1)

    # "What's new" has its own page per language (build-whats-new.py).
    page = page.replace('href="/whats-new.html"', f'href="/{code}/whats-new.html"')

    # The page's script: this page's language, not a guess.
    if "var PAGE_LANG = 'en'; /*PAGE_LANG*/" not in page:
        sys.exit("PAGE_LANG marker not found")
    page = page.replace("var PAGE_LANG = 'en'; /*PAGE_LANG*/", f"var PAGE_LANG = '{code}'; /*PAGE_LANG*/", 1)

    # Relative addresses would resolve under /<lang>/: make them absolute.
    page = re.sub(r'\b(src|href)="(?!https?:|/|#|mailto:|tel:|data:)([^"]+)"', r'\1="/\2"', page)

    page = replace_lang_links(page, langs, code)
    return page


def main():
    src = open(SRC, encoding="utf-8").read()
    L = read_table(src)
    langs = languages(src)
    codes = [c for c, _ in langs]
    missing = [c for c in codes if c not in L]
    if missing:
        sys.exit(f"no translations for {missing}")

    root = replace_lang_links(replace_hreflang(src, langs), langs, "en")
    root = root.replace('<a href="#" id="privacyLink"', '<a href="/app/privacy-policy.html" id="privacyLink"', 1)
    root = root.replace('<a href="#" id="termsLink"', '<a href="/app/terms.html" id="termsLink"', 1)
    if root != src:
        open(SRC, "w", encoding="utf-8").write(root)

    for code in codes:
        if code == "en":
            continue
        out_dir = os.path.join(HERE, code)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(localise(root, L, code, langs))

    today = datetime.date.today().isoformat()
    alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{page_url(c)}"/>' for c in codes)
    alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{page_url("en")}"/>'
    urls = []
    for c in codes:
        urls.append(f"  <url>\n    <loc>{page_url(c)}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>{'1.0' if c == 'en' else '0.9'}</priority>{alts}\n  </url>")
    wn_alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{SITE}{"/whats-new.html" if c == "en" else f"/{c}/whats-new.html"}"/>' for c in codes)
    wn_alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE}/whats-new.html"/>'
    for c in codes:
        loc = SITE + ("/whats-new.html" if c == "en" else f"/{c}/whats-new.html")
        urls.append(f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>0.6</priority>{wn_alts}\n  </url>")
    # Release posts (build-whats-new.py): one URL per language that has the text, linked as alternates.
    import glob
    posts = {}
    for f in glob.glob(os.path.join(HERE, "whats-new", "*", "index.html")) + glob.glob(os.path.join(HERE, "*", "whats-new", "*", "index.html")):
        rel = os.path.relpath(os.path.dirname(f), HERE).split(os.sep)
        lang, ver = ("en", rel[1]) if rel[0] == "whats-new" else (rel[0], rel[2])
        posts.setdefault(ver, {})[lang] = SITE + "/" + "/".join(rel) + "/"
    for ver, by_lang in sorted(posts.items()):
        p_alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{c}" href="{u}"/>' for c, u in sorted(by_lang.items()))
        if "en" in by_lang:
            p_alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{by_lang["en"]}"/>'
        for c, u in sorted(by_lang.items()):
            urls.append(f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>0.5</priority>{p_alts}\n  </url>")
    for path, prio in [("/pricing.html", "0.7"), ("/app/", "0.8"),
                       ("/app/privacy-policy.html", "0.3"), ("/app/terms.html", "0.3"), ("/refund-policy.html", "0.3")]:
        urls.append(f"  <url>\n    <loc>{SITE}{path}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>{prio}</priority>\n  </url>")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
               + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(HERE, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap)
    print(f"pages: {len(codes) - 1} languages + root; sitemap: {len(urls)} urls")


if __name__ == "__main__":
    main()
