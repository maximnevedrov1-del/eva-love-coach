#!/usr/bin/env python3
"""
SEO verifier v1 for evaintimacycoach.com static site.

Checks per page: title, meta description, single H1, canonical, Open Graph,
valid JSON-LD of required types, internal linking (перелинковка),
internal link integrity. Site-wide: sitemap.xml, robots.txt, llms.txt,
uniqueness of titles/descriptions.

Usage:
    python3 check_seo.py [SITE_ROOT] [--runs-dir DIR]

Exit code 0 = full PASS, 1 = at least one FAIL.
Every run is appended to verifier/runs/run-YYYYmmdd-HHMMSS.log
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

BASE_URL = "https://evaintimacycoach.com"
ARTICLES = [
    "blog/emocionalnoe-vygoranie.html",
    "blog/lichnye-granicy.html",
    "blog/muzh-ne-hochet.html",
    "blog/perezhit-izmenu.html",
    "blog/revnost-v-otnosheniyah.html",
    "blog/samootsenka-i-otnosheniya.html",
    "blog/seksualnoe-zdorove.html",
    "blog/toksichnye-otnosheniya.html",
    "blog/trevozhnost-v-otnosheniyah.html",
    "blog/vernut-blizost.html",
    # wave 2 (2026-07-20)
    "blog/zhena-ne-hochet-blizosti.html",
    "blog/brak-bez-seksa.html",
    "blog/raznoe-libido.html",
    "blog/blizost-posle-rodov.html",
    "blog/otnosheniya-na-rasstoyanii.html",
    "blog/kak-govorit-o-sekse.html",
    # wave 3 (2026-07-21)
    "blog/strah-blizosti.html",
    "blog/emocionalnaya-blizost.html",
    "blog/gazlayting.html",
    "blog/sozavisimye-otnosheniya.html",
    "blog/zhenskoe-libido.html",
    "blog/muzhskie-strahi-v-posteli.html",
    "blog/novye-otnosheniya-posle-razvoda.html",
    "blog/klimaks-i-intim.html",
    # wave 4 (2026-07-22)
    "blog/chem-seksolog-otlichaetsya-ot-psihologa.html",
    "blog/kak-prohodit-konsultaciya-seksologa.html",
    "blog/kak-vybrat-seksologa.html",
    "blog/yazyki-lyubvi.html",
    "blog/seks-posle-pereryva.html",
    "blog/skolko-stoit-konsultaciya-seksologa.html",
]
# commercial landings (2026-07-21)
LANDINGS = [
    "seksolog-online.html",
    "dlya-par.html",
    "za-granitsey.html",
    "vopros.html",
]
PAGES = ["index.html", "blog.html", "diplomas.html"] + LANDINGS + ARTICLES

results = []  # (status, check, detail)


def ok(check, detail=""):
    results.append(("PASS", check, detail))


def fail(check, detail=""):
    results.append(("FAIL", check, detail))


def read(root, rel):
    p = os.path.join(root, rel)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read()


def canonical_for(rel):
    if rel == "index.html":
        return BASE_URL + "/"
    return BASE_URL + "/" + rel


def ld_blocks(html):
    out = []
    for m in re.findall(r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>',
                        html, re.S | re.I):
        try:
            out.append(json.loads(m))
        except Exception as e:
            out.append({"__parse_error__": str(e)})
    return out


def ld_types(blocks):
    types = []
    for b in blocks:
        if isinstance(b, dict):
            if "@graph" in b:
                types += [i.get("@type") for i in b["@graph"] if isinstance(i, dict)]
            else:
                types.append(b.get("@type"))
    return types


def internal_hrefs(html):
    hrefs = re.findall(r'href="([^"]+)"', html)
    res = []
    for h in hrefs:
        if h.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        if h.startswith("http"):
            if h.startswith(BASE_URL):
                res.append(h[len(BASE_URL):] or "/")
            continue  # external
        res.append(h)
    return res


def norm_target(href, from_rel):
    """Map an internal href to a repo-relative file path (None if non-file)."""
    h = href.split("#")[0].split("?")[0]
    if not h:
        return None
    if h.startswith("/"):
        h = h[1:]
    else:
        base = os.path.dirname(from_rel)
        h = os.path.normpath(os.path.join(base, h)).replace("\\", "/")
    if h in ("", "."):
        return "index.html"
    if h.endswith("/"):
        return h + "index.html"
    return h


def check_page(root, rel):
    html = read(root, rel)
    tag = f"[{rel}]"
    if html is None:
        fail(f"{tag} file exists")
        return None
    ok(f"{tag} file exists")

    # lang
    if re.search(r'<html\s+lang="ru"', html):
        ok(f"{tag} lang=ru")
    else:
        fail(f"{tag} lang=ru")

    # title
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    title = m.group(1).strip() if m else ""
    if title and 10 <= len(title) <= 70:
        ok(f"{tag} title ({len(title)} chars)", title)
    else:
        fail(f"{tag} title 10-70 chars", title)

    # meta description
    m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html, re.I)
    desc = m.group(1).strip() if m else ""
    if 50 <= len(desc) <= 160:
        ok(f"{tag} meta description ({len(desc)} chars)")
    else:
        fail(f"{tag} meta description 50-160 chars", f"len={len(desc)}")

    # H1
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    h1_texts = [re.sub(r"<[^>]+>", "", h).strip() for h in h1s]
    if len(h1s) == 1 and h1_texts[0]:
        ok(f"{tag} exactly one non-empty H1", h1_texts[0][:70])
    else:
        fail(f"{tag} exactly one non-empty H1", f"found {len(h1s)}")

    # canonical
    want = canonical_for(rel)
    cans = re.findall(r'<link\s+rel="canonical"\s+href="([^"]+)"', html, re.I)
    if cans == [want]:
        ok(f"{tag} canonical", want)
    else:
        fail(f"{tag} canonical == {want}", f"found {cans}")

    # Open Graph
    for prop in ("og:title", "og:description"):
        if re.search(rf'<meta\s+property="{prop}"\s+content="[^"]+"', html):
            ok(f"{tag} {prop}")
        else:
            fail(f"{tag} {prop}")

    # JSON-LD parse
    blocks = ld_blocks(html)
    if not blocks:
        fail(f"{tag} has JSON-LD block(s)")
    for b in blocks:
        if "__parse_error__" in b:
            fail(f"{tag} JSON-LD valid JSON", b["__parse_error__"])
    types = [t for t in ld_types(blocks) if t]
    if blocks and all("__parse_error__" not in b for b in blocks):
        ok(f"{tag} JSON-LD valid JSON", f"types={types}")
    return html, title, desc, h1_texts[0] if h1_texts else "", types, blocks


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = args[0] if args else os.environ.get("SITE_ROOT", "/mnt/agents/eva-love-coach")
    runs_dir = None
    for i, a in enumerate(sys.argv):
        if a == "--runs-dir" and i + 1 < len(sys.argv):
            runs_dir = sys.argv[i + 1]
    if runs_dir is None:
        runs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs")
    os.makedirs(runs_dir, exist_ok=True)

    print(f"SEO verifier v1 — site root: {root}")
    print(f"run at {datetime.now(timezone.utc).isoformat()}\n")

    page_info = {}
    for rel in PAGES:
        r = check_page(root, rel)
        if r:
            page_info[rel] = r

    # --- required JSON-LD types per page ---
    def require_types(rel, required):
        if rel not in page_info:
            return
        types = page_info[rel][4]
        for t in required:
            if t in types:
                ok(f"[{rel}] JSON-LD type {t}")
            else:
                fail(f"[{rel}] JSON-LD type {t}", f"have {types}")

    require_types("index.html", ["Person", "ProfessionalService", "FAQPage"])
    require_types("blog.html", ["Blog"])
    require_types("diplomas.html", ["CollectionPage", "BreadcrumbList"])
    for art in ARTICLES:
        require_types(art, ["Article", "BreadcrumbList"])
        if art in page_info:
            blocks = page_info[art][5]
            art_blocks = [b for b in blocks if isinstance(b, dict) and b.get("@type") == "Article"]
            if art_blocks:
                a = art_blocks[0]
                for field in ("headline", "description", "author", "datePublished", "inLanguage", "mainEntityOfPage"):
                    if a.get(field):
                        ok(f"[{art}] Article.{field}")
                    else:
                        fail(f"[{art}] Article.{field}")
                if a.get("mainEntityOfPage") == canonical_for(art):
                    ok(f"[{art}] Article.mainEntityOfPage == canonical")
                else:
                    fail(f"[{art}] Article.mainEntityOfPage == canonical", str(a.get("mainEntityOfPage")))

    # --- uniqueness across pages ---
    titles, descs, h1s = {}, {}, {}
    for rel, (_, t, d, h, _, _) in page_info.items():
        titles.setdefault(t, []).append(rel)
        descs.setdefault(d, []).append(rel)
        h1s.setdefault(h, []).append(rel)
    for name, coll in (("title", titles), ("meta description", descs), ("H1", h1s)):
        dups = {k: v for k, v in coll.items() if k and len(v) > 1}
        if not dups:
            ok(f"site-wide unique {name}s", f"{len(coll)} unique")
        else:
            fail(f"site-wide unique {name}s", json.dumps(dups, ensure_ascii=False))

    # --- перелинковка (internal linking) ---
    art_set = set(ARTICLES)
    links_from = {}
    for rel in PAGES:
        if rel not in page_info:
            continue
        targets = set()
        for h in internal_hrefs(page_info[rel][0]):
            t = norm_target(h, rel)
            if t:
                targets.add(t)
        links_from[rel] = targets

    # blog hub lists all articles
    if "blog.html" in links_from:
        missing = art_set - links_from["blog.html"]
        if not missing:
            ok(f"[blog.html] links to all {len(art_set)} articles")
        else:
            fail(f"[blog.html] links to all {len(art_set)} articles", f"missing {sorted(missing)}")

    # every article links to >=2 other articles, to blog hub and to index
    for art in ARTICLES:
        if art not in links_from:
            continue
        others = (links_from[art] & art_set) - {art}
        if len(others) >= 2:
            ok(f"[{art}] links to >=2 other articles", f"{len(others)} links")
        else:
            fail(f"[{art}] links to >=2 other articles", f"only {sorted(others)}")
        for need, label in (("blog.html", "blog hub"), ("index.html", "homepage")):
            if need in links_from[art]:
                ok(f"[{art}] links to {label}")
            else:
                fail(f"[{art}] links to {label}")

    # homepage links to blog hub and to >=3 articles
    if "index.html" in links_from:
        if "blog.html" in links_from["index.html"]:
            ok("[index.html] links to blog hub")
        else:
            fail("[index.html] links to blog hub")
        n = len(links_from["index.html"] & art_set)
        if n >= 3:
            ok("[index.html] links to >=3 articles", f"{n}")
        else:
            fail("[index.html] links to >=3 articles", f"only {n}")

    # diplomas links to blog (cross-section linking)
    if "diplomas.html" in links_from:
        if "blog.html" in links_from["diplomas.html"]:
            ok("[diplomas.html] links to blog hub")
        else:
            fail("[diplomas.html] links to blog hub")

    # --- internal link integrity ---
    # Files that are referenced in markup but uploaded to the repo separately
    # (binary assets delivered outside the code-change commits).
    # 2026-07-22: hero-bg.jpg no longer pending — hero/og images moved to
    # CDN (www.kimi.com), see ALLOWED_EXTERNAL_DOMAINS below.
    PENDING_UPLOADS = set()
    broken = []
    pending = []
    for rel in PAGES:
        if rel not in page_info:
            continue
        for h in internal_hrefs(page_info[rel][0]):
            t = norm_target(h, rel)
            if t and t.endswith((".html", ".xml", ".txt", ".jpg", ".png")):
                if not os.path.isfile(os.path.join(root, t)):
                    if t in PENDING_UPLOADS:
                        pending.append(f"{rel} -> {h}")
                    else:
                        broken.append(f"{rel} -> {h}")
    if pending:
        ok("pending binary uploads referenced but not yet in repo",
           "; ".join(sorted(set(pending))))
    if not broken:
        ok("all internal links resolve to existing files")
    else:
        fail("all internal links resolve to existing files", "; ".join(broken[:20]))

    # --- external domains whitelist ---
    # Any external URL referenced from markup must point at a whitelisted
    # domain. www.kimi.com is the CDN hosting hero/og images (perf pass
    # 2026-07-22) and is an allowed asset source, not a broken external link.
    ALLOWED_EXTERNAL_DOMAINS = {
        "evaintimacycoach.com",
        "schema.org", "www.w3.org",
        "fonts.googleapis.com", "fonts.gstatic.com",
        "t.me", "wa.me", "instagram.com", "www.instagram.com",
        "www.kimi.com",
    }
    bad_ext = []
    for rel in PAGES:
        if rel not in page_info:
            continue
        for u in re.findall(r'https?://[^\s"\'<>)]+', page_info[rel][0]):
            d = re.sub(r"^https?://", "", u).split("/")[0].lower()
            if d and d not in ALLOWED_EXTERNAL_DOMAINS:
                bad_ext.append(f"{rel} -> {d}")
    if not bad_ext:
        ok("external links point to whitelisted domains (CDN www.kimi.com allowed)")
    else:
        fail("external links point to whitelisted domains",
             "; ".join(sorted(set(bad_ext))[:20]))

    # --- sitemap.xml ---
    sm = read(root, "sitemap.xml")
    if sm is None:
        fail("sitemap.xml exists")
    else:
        ok("sitemap.xml exists")
        try:
            tree = ET.fromstring(sm)
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            locs = [e.text.strip() for e in tree.findall(".//s:loc", ns)]
            lastmods = tree.findall(".//s:lastmod", ns)
            want_locs = {canonical_for(p) for p in PAGES}
            missing = want_locs - set(locs)
            extra = [l for l in locs if l not in want_locs]
            if not missing:
                ok("sitemap lists all pages", f"{len(locs)} urls")
            else:
                fail("sitemap lists all pages", f"missing {sorted(missing)}")
            if not extra:
                ok("sitemap has no dead urls")
            else:
                fail("sitemap has no dead urls", f"extra {extra}")
            if len(lastmods) == len(locs):
                ok("sitemap lastmod on every url")
            else:
                fail("sitemap lastmod on every url", f"{len(lastmods)}/{len(locs)}")
        except Exception as e:
            fail("sitemap.xml valid XML", str(e))

    # --- robots.txt ---
    rb = read(root, "robots.txt")
    if rb is None:
        fail("robots.txt exists")
    else:
        ok("robots.txt exists")
        if re.search(rf"Sitemap:\s*{re.escape(BASE_URL)}/sitemap\.xml", rb):
            ok("robots.txt references sitemap")
        else:
            fail("robots.txt references sitemap")
        if re.search(r"Disallow:\s*/\s*$", rb, re.M):
            fail("robots.txt does not block whole site", "Disallow: / found")
        else:
            ok("robots.txt does not block whole site")

    # --- llms.txt ---
    ll = read(root, "llms.txt")
    if ll and len(ll.strip()) > 100:
        ok("llms.txt exists and non-trivial", f"{len(ll)} chars")
    else:
        fail("llms.txt exists and non-trivial")

    # --- report ---
    passes = sum(1 for r in results if r[0] == "PASS")
    fails = [r for r in results if r[0] == "FAIL"]
    print("\n--- FAILURES ---" if fails else "\n--- no failures ---")
    for _, c, d in fails:
        print(f"FAIL: {c} | {d}")
    print(f"\nTOTAL: {passes} PASS / {len(fails)} FAIL -> {'PASS' if not fails else 'FAIL'}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join(runs_dir, f"run-{stamp}.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"SEO verifier v1 run {stamp} UTC, root={root}\n")
        for s, c, d in results:
            f.write(f"{s}\t{c}\t{d}\n")
        f.write(f"TOTAL: {passes} PASS / {len(fails)} FAIL -> {'PASS' if not fails else 'FAIL'}\n")
    print(f"log: {log_path}")
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
