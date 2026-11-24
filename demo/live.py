"""
CyberOptix demo video - LIVE screen recording with narration.

Every website step is recorded as real video: Playwright drives the running site in Edge
(visible cursor, typing, scrolling, clicks, live AI replies) while Chrome's screencast API
streams frames. Each clip is narrated with a neural voice (edge-tts), framed in the reference
layout (chapter header, step pills, chapter timeline, caption) and joined into one MP4.

    .venv\\Scripts\\python.exe demo\\live.py                 # everything -> demo/out/CyberOptix_Demo_Live.mp4
    .venv\\Scripts\\python.exe demo\\live.py --only s22,s23  # re-record some segments, then rebuild
    .venv\\Scripts\\python.exe demo\\live.py --compose       # rebuild the MP4 from existing clips

Needs: dev server on :8000 (Gradio on :7860 starts with /en/chat/), ffmpeg, demo/.demo_credentials.
"""
import base64
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
WORK = OUT / "live"
for d in (OUT, WORK, WORK / "tts", WORK / "clips", WORK / "frames", WORK / "chrome", WORK / "seg"):
    d.mkdir(parents=True, exist_ok=True)

BASE, GRADIO = "http://127.0.0.1:8000", "http://127.0.0.1:7860"
VIEW = {"width": 1440, "height": 810}             # recorded at 1920x1080 (scale 1.3334)
FPS = 30
VOICE = "en-US-AndrewMultilingualNeural"
CREDS = json.loads((ROOT / ".demo_credentials").read_text())
SHOP, PRODUCT = "shop45hfg5e5ba", "334ef4d3aa"   # Citicom - ASUS ROG Strix G17
AI_GAP = 55                                       # free AI: 1 reply / 45 s per IP
CHAPTERS = ["Sign in", "Browse", "Search & filter", "Myanmar / English", "Cart",
            "Wishlist", "Checkout", "Receipt", "AI Picks", "AI chatbot"]
GRADIO_URL = "127.0.0.1:7860  ·  Veras AI Studio (Gradio, embedded at /en/chat/)"

# --------------------------------------------------------------------------- #
# In-page helpers injected into every page: a visible cursor with click ripple
# (headless browsers draw none) and a teal spotlight box with an orange label.
# --------------------------------------------------------------------------- #
INJECT = r"""
(() => {
  if (window.__cxDemo) return; window.__cxDemo = true;
  const css = `
   #__cur{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;transform:translate(-3px,-2px);transition:none}
   #__cur svg{filter:drop-shadow(0 2px 3px rgba(0,0,0,.55))}
   .__rip{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:3px solid #f97316;z-index:2147483646;pointer-events:none;animation:__rip .6s ease-out forwards}
   @keyframes __rip{from{transform:scale(.3);opacity:1}to{transform:scale(1.4);opacity:0}}
   #__spot{position:fixed;z-index:2147483645;pointer-events:none;border:3px solid #14b8a6;border-radius:12px;box-shadow:0 0 0 9999px rgba(2,6,23,.28),0 0 22px rgba(20,184,166,.75);transition:opacity .25s;opacity:0}
   #__lab{position:fixed;z-index:2147483646;pointer-events:none;background:#c2410c;color:#fff;font:600 17px Inter,system-ui,sans-serif;padding:7px 16px;border-radius:999px;box-shadow:0 8px 20px rgba(194,65,12,.4);white-space:nowrap;transition:opacity .25s;opacity:0}`;
  const add = () => {
    if (document.getElementById('__cur')) return;
    const st = document.createElement('style'); st.textContent = css; document.documentElement.appendChild(st);
    const c = document.createElement('div'); c.id = '__cur';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l15 9-7 1.5L8.5 20z" fill="#fff" stroke="#0f172a" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    const s = document.createElement('div'); s.id = '__spot';
    const l = document.createElement('div'); l.id = '__lab';
    document.documentElement.append(s, l, c);
    const p = window.__cxPos || [720, 500]; c.style.left = p[0] + 'px'; c.style.top = p[1] + 'px';
  };
  document.addEventListener('DOMContentLoaded', add); if (document.readyState !== 'loading') add();
  addEventListener('mousemove', e => { window.__cxPos = [e.clientX, e.clientY]; const c = document.getElementById('__cur'); if (c) { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; } }, true);
  addEventListener('mousedown', e => { const r = document.createElement('div'); r.className = '__rip'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; document.documentElement.appendChild(r); setTimeout(() => r.remove(), 700); }, true);
  let target = null, label = '';
  window.__cxSpot = (sel, text) => {
    add();
    target = sel ? (typeof sel === 'string' ? document.querySelector(sel) : sel) : null; label = text || '';
    const s = document.getElementById('__spot'), l = document.getElementById('__lab');
    if (!target) { s.style.opacity = 0; l.style.opacity = 0; return false; }
    l.textContent = label; return true;
  };
  const loop = () => {
    const s = document.getElementById('__spot'), l = document.getElementById('__lab');
    if (s && target && target.isConnected) {
      const r = target.getBoundingClientRect(), pad = 6;
      Object.assign(s.style, { left: (r.left - pad) + 'px', top: (r.top - pad) + 'px', width: (r.width + pad * 2) + 'px', height: (r.height + pad * 2) + 'px', opacity: 1 });
      if (label) {
        const below = r.bottom + 60 < innerHeight;
        Object.assign(l.style, { left: Math.max(12, Math.min(r.left, innerWidth - l.offsetWidth - 12)) + 'px', top: (below ? r.bottom + pad + 12 : r.top - pad - 46) + 'px', opacity: 1 });
      } else l.style.opacity = 0;
    } else if (s) { s.style.opacity = 0; if (l) l.style.opacity = 0; }
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
})();
"""


class Rec:
    """Screencast recorder for one page + human-like input helpers."""

    def __init__(self, ctx, page):
        self.page, self.ctx = page, ctx
        self.cdp = ctx.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._on_frame)
        self.frames, self.dir, self.on = [], None, False
        self.pos = [720, 500]

    def _on_frame(self, ev):
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        except Exception:
            pass
        if self.on:
            path = self.dir / f"{len(self.frames):05d}.jpg"
            path.write_bytes(base64.b64decode(ev["data"]))
            self.frames.append((time.time(), path))

    def start(self, name):
        self.dir = WORK / "frames" / name
        if self.dir.exists():
            for f in self.dir.glob("*.jpg"):
                f.unlink()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.frames, self.on, self.t0 = [], True, time.time()
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "maxWidth": 1920,
                                               "maxHeight": 1080, "everyNthFrame": 1})
        # force a first frame
        self.page.mouse.move(self.pos[0] + 1, self.pos[1])
        self.page.mouse.move(*self.pos)

    def elapsed(self):
        return time.time() - self.t0

    def stop(self, name, min_dur=0.0):
        while self.elapsed() < min_dur:
            self.page.mouse.move(self.pos[0] + (1 if int(self.elapsed() * 2) % 2 else 0), self.pos[1])
            self.page.wait_for_timeout(250)
        self.page.wait_for_timeout(300)
        t_end = time.time()
        self.cdp.send("Page.stopScreencast")
        self.on = False
        return encode_frames(name, self.frames, self.t0, t_end)

    # --- input helpers --------------------------------------------------------
    def wait(self, ms):
        self.page.wait_for_timeout(ms)

    def move(self, x, y, steps=None):
        d = ((x - self.pos[0]) ** 2 + (y - self.pos[1]) ** 2) ** .5
        self.page.mouse.move(x, y, steps=steps or max(8, int(d / 22)))
        self.pos = [x, y]

    def center(self, loc):
        loc.scroll_into_view_if_needed(timeout=10000)
        b = loc.bounding_box()
        # keep targets out from under the fixed 68px navbar / off the bottom edge
        if b["y"] < 84 or b["y"] + b["height"] > VIEW["height"] - 8:
            loc.evaluate("e => e.scrollIntoView({block: 'center', behavior: 'smooth'})")
            self.wait(650)
            b = loc.bounding_box()
        return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2

    def hover(self, loc, pause=350):
        x, y = self.center(loc)
        self.move(x, y)
        self.wait(pause)

    def click(self, loc, pause=300):
        self.hover(loc, pause)
        self.page.mouse.down()
        self.wait(90)
        self.page.mouse.up()
        self.wait(250)

    def type(self, loc, text, delay=55, clear=False):
        self.click(loc)
        if clear:
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Backspace")
        self.page.keyboard.type(text, delay=delay)

    def scroll(self, dy, steps=12, pause=500):
        for _ in range(steps):
            self.page.mouse.wheel(0, dy / steps)
            self.wait(28)
        self.wait(pause)

    def _eval(self, js, arg=None):
        """page.evaluate that survives an in-flight navigation."""
        for _ in range(3):
            try:
                return self.page.evaluate(js, arg)
            except Exception as exc:
                if "context was destroyed" not in str(exc) and "navigation" not in str(exc):
                    raise
                self.page.wait_for_load_state("networkidle")
                self.wait(300)
        return None

    def spot(self, selector, label="", pause=0):
        ok = self._eval("([s, l]) => window.__cxSpot && window.__cxSpot(s, l)", [selector, label])
        if not ok:
            print(f"   ! spot target not found: {selector}")
        if pause:
            self.wait(pause)

    def spot_js(self, expr, label="", pause=0):
        """Spotlight the element returned by a JS expression."""
        self._eval(f"() => window.__cxSpot(({expr}), {json.dumps(label)})")
        if pause:
            self.wait(pause)

    def unspot(self):
        self._eval("() => window.__cxSpot && window.__cxSpot(null)")


def encode_frames(name, frames, t0, t_end):
    """Variable-rate screencast frames -> constant 30 fps silent clip. Returns duration."""
    clip = WORK / "clips" / f"{name}.mp4"
    if not frames:
        raise RuntimeError(f"no frames recorded for {name}")
    lst = WORK / "frames" / f"{name}.txt"
    lines = []
    for i, (t, path) in enumerate(frames):
        nxt = frames[i + 1][0] if i + 1 < len(frames) else t_end
        lines.append(f"file '{path.as_posix()}'\nduration {max(nxt - t, 0.001):.4f}")
    lines.append(f"file '{frames[-1][1].as_posix()}'")
    lst.write_text("\n".join(lines))
    lead = max(0.0, frames[0][0] - t0)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-vf", f"tpad=start_duration={lead:.3f}:start_mode=clone,fps={FPS},scale=1920:1080:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(clip)], check=True)
    return probe(clip)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def tts(text):
    key = hashlib.md5(f"{VOICE}|{text}".encode()).hexdigest()[:12]
    path = WORK / "tts" / f"{key}.mp3"
    if path.exists() and probe(path) <= 0.3:   # discard a corrupt cached file
        path.unlink()
    if not path.exists():
        exe = ROOT.parent / ".venv" / "Scripts" / "edge-tts.exe"
        for attempt in range(10):
            res = subprocess.run([str(exe), "--voice", VOICE, "--rate=+4%", "--text", text, "--write-media", str(path)],
                                 capture_output=True, text=True)
            if res.returncode == 0 and path.exists() and path.stat().st_size > 1000 and probe(path) > 0.3:
                break
            path.unlink(missing_ok=True)
            print(f"   tts retry {attempt + 1}: {res.stderr.strip()[-200:]}")
            time.sleep(4 + 3 * attempt)
        else:
            raise RuntimeError(f"edge-tts failed for: {text[:60]}")
    return path, probe(path)


# --------------------------------------------------------------------------- #
# Storyboard
# --------------------------------------------------------------------------- #
def seg(id, title, ci, pills, pill, narration, caption, note=None, url=None, action=None,
        max_speed=1.0, sfx=None, page="site"):
    return dict(id=id, kind="live", title=title, chapterIndex=ci, pills=pills, pill=pill,
                narration=narration, caption=caption, note=note, url=url, action=action,
                max_speed=max_speed, sfx=sfx, page=page)


def title(id, scene, narration):
    return dict(id=id, kind="title", scene=scene, narration=narration)


SIGN = ["Google", "Email", "Signed in"]
BROW = ["Catalog", "Details", "Specs"]
FILT = ["Brand", "Price", "Search"]
LANG = ["Switch", "Myanmar", "Back"]
CART = ["Add", "Cart"]
WISH = ["Save", "Wishlist"]
CHEK = ["Address", "Payment"]
RCPT = ["Invoice", "Orders"]
PICK = ["Use & budget", "Ranking"]
VERA = ["Chat", "Gradio", "Text", "Image", "Voice"]

STORY = [
    title("t1", {"headline": "Choosing a laptop is <em>hard</em>.",
                 "caption": "Hundreds of models, confusing specs, and shops all over Myanmar."},
          "Buying a laptop in Myanmar usually means visiting several shops and comparing confusing specifications."),
    title("t2", {"logo": True, "tagline": "AI-powered laptop shopping for Myanmar",
                 "caption": "CyberOptix brings the shops, the specs and an AI shopping assistant into one website."},
          "So I built CyberOptix, an AI-powered laptop shopping website."),
    title("t3", {"headline": "Everything in <em>one place</em>", "features": [
        {"icon": "🔐", "title": "Sign in", "text": "Google OAuth 2.0 or email & password"},
        {"icon": "💻", "title": "Browse", "text": "193 products from 4 partner shops"},
        {"icon": "🔎", "title": "Search & filter", "text": "Category, brand, price and keyword"},
        {"icon": "🌐", "title": "Myanmar / English", "text": "Full bilingual interface"},
        {"icon": "🛒", "title": "Cart & wishlist", "text": "Save, compare and buy later"},
        {"icon": "🧾", "title": "Checkout & receipt", "text": "Myanmar addresses, invoice & PDF"},
        {"icon": "✨", "title": "AI Picks", "text": "Laptops ranked for your use and budget", "ai": True},
        {"icon": "🤖", "title": "Veras AI chatbot", "text": "Gradio app · text, image and voice", "ai": True}],
        "caption": "Every screen in this video is the real website, recorded live."},
          "It covers the whole shopping journey: sign-in, browsing and filters, a Myanmar and English interface, "
          "cart, wishlist, checkout and receipts. And it has two A.I. features: A.I. Picks, and Veras, a chatbot "
          "that understands text, images and voice."),
    seg("s0", "It all starts at CyberOptix", -1, [], None,
        "This is the home page, running live. You can search straight away, or even spin the 3D laptop.",
        "The home page: search, quick AI shortcuts, and an interactive 3D laptop.", action="home"),

    seg("s1", "Sign in", 0, SIGN, "Google",
        "Customers can sign in with Google. I implemented the Google OAuth 2.0 flow myself. For this recording, I'll use an email account.",
        "Customers can sign in with Google, through CyberOptix's own Google OAuth 2.0 flow.",
        note="Google sign-in needs the project's Google OAuth client ID; this recording signs in with a demo email account.",
        action="signin_google"),
    seg("s2", "Sign in", 0, SIGN, "Email", "I enter my email and password, and log in.",
        "Or sign in with an email and password.", action="signin_email"),
    seg("s3", "Sign in", 0, SIGN, "Signed in",
        "And I'm signed in. The account menu now shows my profile and personal picks.",
        "Signed in - the account menu shows the profile, personal picks and sign out.", action="signed_in"),

    seg("s4", "Browse laptops", 1, BROW, "Catalog",
        "The catalog lists 193 products from four partner shops, priced in US dollars and Myanmar kyat.",
        "The catalog: every product with its shop, specs and prices in USD and MMK.", action="catalog"),
    seg("s5", "Browse laptops", 1, BROW, "Details",
        "Each product page has a photo gallery, the price with any discount, and a full description.",
        "A product page: photo gallery, price and discount, description.", action="detail"),
    seg("s6", "Browse laptops", 1, BROW, "Specs",
        "The Additional Info tab lists every specification, which makes comparing models easy.",
        "Additional Info lists the full specifications.", action="specs"),

    seg("s7", "Search and filter", 2, FILT, "Brand",
        "The side menu filters by category and brand. Here are only the Asus products.",
        "Filter by category or brand from the side menu.", action="filter_brand"),
    seg("s8", "Search and filter", 2, FILT, "Price",
        "The price filter keeps everything within a budget, here one thousand dollars.",
        "The price filter narrows the list to a budget.", action="filter_price"),
    seg("s9", "Search and filter", 2, FILT, "Search",
        "And search finds a specific model by name, like MacBook.",
        "Search finds a model by name.", action="search"),

    seg("s10", "Myanmar and English", 3, LANG, "Myanmar",
        "One click switches the entire website to Myanmar. Every page, button and message is translated, not just the menu.",
        "One click switches the whole site to Myanmar.", action="lang_my"),
    seg("s11", "Myanmar and English", 3, LANG, "Back",
        "Product pages follow the language too. And one more click switches back to English.",
        "Product pages follow the chosen language; switch back any time.", action="lang_back"),

    seg("s12", "Shopping cart", 4, CART, "Add",
        "On a product page, Add to Cart puts the laptop straight into the cart.",
        "Add to Cart from the product page.", action="cart_add"),
    seg("s13", "Shopping cart", 4, CART, "Cart",
        "The cart groups items by shop. When I change the quantity, the totals update instantly.",
        "The cart groups items by shop; totals update instantly.", action="cart_page"),

    seg("s14", "Wishlist", 5, WISH, "Save", "The heart icon saves laptops for later.",
        "The heart saves a laptop to the wishlist.", action="wish_save"),
    seg("s15", "Wishlist", 5, WISH, "Wishlist",
        "From the wishlist, I can move a laptop to the cart, or remove it.",
        "Move saved laptops to the cart, or remove them.", action="wish_page"),

    seg("s16", "Checkout", 6, CHEK, "Address",
        "At checkout I add my mobile number and a Myanmar delivery address. The shipping fee is calculated automatically.",
        "Mobile number and Myanmar delivery address; shipping is added automatically.", action="checkout_address",
        max_speed=2.2),
    seg("s17", "Checkout", 6, CHEK, "Payment",
        "I'll pay with Cash on Delivery, and confirm the order.",
        "Pay with Cash on Delivery and confirm.",
        note="PayPal, Stripe and KBZPay buttons need payment-provider accounts, so this demo uses Cash on Delivery.",
        action="checkout_pay"),

    seg("s18", "Order confirmation", 7, RCPT, "Invoice",
        "An invoice is generated right away, with the order number, delivery address and payment method. It can be printed or downloaded as a PDF.",
        "An invoice is generated instantly - print it or download a PDF.", action="invoice"),
    seg("s19", "Order confirmation", 7, RCPT, "Orders", "And every order is saved in My Orders.",
        "Every order is kept in My Orders.", action="orders"),

    seg("s20", "AI Picks", 8, PICK, "Use & budget",
        "A.I. Picks asks just two things: what the laptop is for, and the budget.",
        "Pick what the laptop is for and set a budget.", action="picks_set"),
    seg("s21", "AI Picks", 8, PICK, "Ranking",
        "It scores every laptop on processor, memory, purpose and value for money, and ranks the best matches first.",
        "Every laptop is scored on CPU, RAM, purpose and value - best matches first.",
        note="Content-based ranking computed from the live product catalogue.", action="picks_results"),

    seg("s22", "Veras AI chatbot", 9, VERA, "Chat",
        "Veras is an A.I. shopping assistant on every page. I ask in plain language, and it recommends real products from our database.",
        "Veras answers in plain language and shows real products from the database.",
        note="Text AI: free gpt-oss-20b model via Pollinations. Product cards always come from the CyberOptix database.",
        action="ai_widget", max_speed=3.0),
    seg("s23", "Veras AI chatbot", 9, VERA, "Gradio",
        "The Veras A.I. Studio is a Gradio app, built into the website. It offers three ways to ask.",
        "The Veras AI Studio is a Gradio app embedded in the website.", action="gradio_open"),
    seg("s24", "Veras AI chatbot", 9, VERA, "Text",
        "First, text. It explains specifications, like Core i5 versus Core i7, and links laptops that match.",
        "Text: it explains specs and links matching laptops.", url=GRADIO_URL, action="g_text",
        max_speed=3.0, page="gradio"),
    seg("s25", "Veras AI chatbot", 9, VERA, "Image",
        "Second, image search. Instead of typing a model name, I upload a photo. Veras recognises an ASUS gaming laptop, and finds the closest products in the catalogue.",
        "Image search: upload a photo instead of typing a model name.",
        note="Image search: CLIP model running locally compares the photo with every product image.",
        url=GRADIO_URL, action="g_image", max_speed=3.0, page="gradio"),
    seg("s26", "Veras AI chatbot", 9, VERA, "Voice",
        "Third, voice. Here is a spoken question.",
        "Voice: record or upload a spoken question.", url=GRADIO_URL, action="g_voice_upload",
        sfx=str(ROOT / "assets" / "voice_question.wav"), page="gradio"),
    seg("s27", "Veras AI chatbot", 9, VERA, "Voice",
        "Whisper turns the speech into text, and the A.I. answers with a recommendation.",
        "Whisper transcribes the question; the AI answers.",
        note="Speech-to-text: Whisper (faster-whisper) running locally - no paid API.",
        url=GRADIO_URL, action="g_voice_answer", max_speed=3.0, page="gradio"),

    title("t4", {"headline": "Your next laptop, <em>picked by AI</em>.", "logo": True,
                 "tagline": "Django · Bilingual · Gradio AI chatbot",
                 "caption": "CyberOptix - a complete laptop e-commerce website with AI built in."},
          "That's CyberOptix: a complete laptop store, with A.I. built in. Thanks for watching."),
]


# --------------------------------------------------------------------------- #
# Actions (each runs while recording; r = Rec for the current page)
# --------------------------------------------------------------------------- #
_last_ai = [0.0]
AI_ACTIONS = {"ai_widget", "g_text", "g_image", "g_voice_answer"}


def ai_gap():
    gap = time.time() - _last_ai[0]
    if gap < AI_GAP:
        print(f"   waiting {AI_GAP - gap:.0f}s for the free AI rate limit (not recorded)")
        time.sleep(AI_GAP - gap)


def gradio_wait(g, timeout=240):
    """Wait until Gradio is idle AND the last bot message has stopped changing for 3 s."""
    g.wait_for_timeout(2000)
    t0, last, stable = time.time(), None, 0
    while time.time() - t0 < timeout:
        busy = g.locator(r"text=/processing \|/").count() + g.locator(".progress-text, .eta-bar, .generating").count()
        bots = g.locator("[data-testid='bot']")
        txt = bots.last.inner_text() if bots.count() else ""
        stable = stable + 1 if (txt and txt == last and not busy) else 0
        last = txt
        if stable >= 6:                     # 6 x 0.5 s unchanged
            break
        g.wait_for_timeout(500)
    g.wait_for_timeout(600)
    _last_ai[0] = time.time()


def gradio_upload(r, hint, path):
    g = r.page
    loc = g.get_by_text(hint).locator("visible=true").first
    r.hover(loc)
    with g.expect_file_chooser() as fc:
        loc.click()
    fc.value.set_files(str(path))


def run_action(name, r, state):
    p = r.page
    url = lambda u: f"{BASE}{u}"
    if name == "home":
        r.move(900, 420); r.wait(2600)
        lap = p.locator("#hx-laptop")
        x, y = r.center(lap)
        r.move(x - 120, y)
        p.mouse.down(); r.move(x + 200, y + 10, steps=40); p.mouse.up()
        r.wait(900)
        r.hover(p.locator(".hx-search input"), 600)
    elif name == "signin_google":
        r.hover(p.locator("#userMenu"), 700)
        r.click(p.locator(".cx-nav .dropdown-menu a[href*='sign-in']"))
        p.wait_for_load_state("networkidle"); r.wait(500)
        g = p.locator("a[href*='google/login']").first
        r.spot("a[href*='google/login']", "Continue with Google")
        r.hover(g, 1500)
    elif name == "signin_email":
        r.unspot()
        form = p.locator("form:has(input[name=email])").first
        r.type(form.locator("input[name=email]"), CREDS["email"], delay=40)
        r.type(form.locator("input[name=password]"), CREDS["password"], delay=40)
        r.click(form.locator("button[type=submit]"))
        p.wait_for_load_state("networkidle"); r.wait(800)
    elif name == "signed_in":
        r.spot("#userMenu", "Signed in")
        r.hover(p.locator("#userMenu"), 1800)
        r.unspot()
    elif name == "catalog":
        r.click(p.locator(".cx-nav nav > a[href$='/products/']").first)
        p.wait_for_load_state("networkidle"); r.wait(600)
        r.scroll(520, steps=14, pause=700)
        r.spot(".cx-product", "193 products · 4 shops")
        r.hover(p.locator(".cx-product").first, 1200)
    elif name == "detail":
        r.unspot()
        p.goto(url(f"/en/shop/{SHOP}/product/{PRODUCT}/")); p.wait_for_load_state("networkidle"); r.wait(500)
        r.spot(".pd-gallery", "Photo gallery")
        opts = p.locator(".pd-gallery .option img")
        for i in (1, 2, 0):
            if opts.count() > i:
                r.click(opts.nth(i), 200); r.wait(450)
    elif name == "specs":
        r.unspot()
        r.click(p.locator(".tab-btn[data-target='#additional-info']"))
        r.scroll(380, pause=500)
        r.spot("#additional-info", "Full specifications")
        r.wait(800)
    elif name == "filter_brand":
        r.unspot(); p.evaluate("window.scrollTo(0,0)"); r.wait(300)
        r.click(p.locator("#menu-toggle")); r.wait(500)
        r.spot("#sidebar", "Categories & brands", 900)
        r.click(p.locator("#sidebar a[href*='brand=Asus']"))
        p.wait_for_load_state("networkidle"); r.wait(500)
        r.spot("h1", "Brand: Asus", 300)
        r.scroll(420, pause=600)
    elif name == "filter_price":
        r.unspot()
        p.goto(url("/en/products/")); p.wait_for_load_state("networkidle"); r.wait(300)
        box = p.locator(".current-price-input")
        r.spot(".pl-toolbar .filter-group:has(.current-price-input)", "Max price")
        r.type(box, "1000", delay=120, clear=True)
        r.click(p.locator("#price-filter-btn")); r.wait(1300)
        r.unspot()
        r.scroll(480, pause=700)
    elif name == "search":
        p.goto(url("/en/")); p.wait_for_load_state("networkidle"); r.wait(300)
        r.type(p.locator(".hx-search input"), "macbook", delay=110)
        r.wait(250); p.keyboard.press("Enter")
        p.wait_for_load_state("networkidle"); r.wait(500)
        r.spot("h1", "Search: macbook", 600)
        r.scroll(380, pause=500)
    elif name == "lang_my":
        r.unspot()
        p.goto(url("/en/products/")); p.wait_for_load_state("networkidle"); r.wait(300)
        r.spot(".language-switcher-container", "English / Myanmar", 500)
        r.click(p.locator(".language-switcher-container label.switch"))
        p.wait_for_url("**/my/**"); p.wait_for_load_state("networkidle"); r.wait(500)
        r.unspot()
        r.scroll(450, pause=700)
        r.scroll(-450, steps=8, pause=300)
    elif name == "lang_back":
        p.goto(url(f"/my/shop/{SHOP}/product/{PRODUCT}/")); p.wait_for_load_state("networkidle"); r.wait(400)
        r.spot(".tab-navigation", "Product pages too", 1400)
        r.unspot()
        r.click(p.locator(".language-switcher-container label.switch"))
        p.wait_for_url("**/en/**"); p.wait_for_load_state("networkidle"); r.wait(600)
    elif name == "cart_add":
        btn = p.locator("#add-to-cart-btn")
        btn.scroll_into_view_if_needed(); p.evaluate("window.scrollBy(0,140)"); r.wait(300)
        r.spot("#add-to-cart-btn", "Add to Cart", 500)
        r.click(btn); r.wait(1200)
        r.unspot()
        r.spot(".cx-nav .icon-cart:has(.shop-cart-count)", "Cart updated", 900)
    elif name == "cart_page":
        r.unspot()
        r.click(p.locator(".cx-nav a[href$='/shop-cart/']").first)
        p.wait_for_load_state("networkidle"); r.wait(500)
        qty = p.locator("input[type=number]").first
        r.spot("input[type=number]", "Quantity", 400)
        r.type(qty, "2", delay=150, clear=True)
        p.keyboard.press("Tab"); r.wait(1300)
        r.spot(".global-cart-summary", "Totals update instantly", 1000)
    elif name == "wish_save":
        r.unspot()
        p.goto(url("/en/products/")); p.wait_for_load_state("networkidle")
        r.scroll(520, steps=12, pause=400)
        hearts = p.locator(".add-to-wishlist")
        r.spot(".add-to-wishlist", "Save for later", 300)
        r.click(hearts.nth(0)); r.wait(700)
        r.click(hearts.nth(1)); r.wait(700)
        r.unspot()
    elif name == "wish_page":
        p.evaluate("window.scrollTo({top:0,behavior:'smooth'})"); r.wait(600)
        r.click(p.locator(".cx-nav a[href$='/wishlist/']").first)
        p.wait_for_load_state("networkidle"); r.wait(500)
        r.spot(".wishlist-items", "Add to cart or remove", 400)
        add = p.get_by_text("Add to cart").first
        r.hover(add, 900)
        r.hover(p.locator(".delete-wishlist-product").first, 900)
    elif name == "checkout_address":
        r.unspot()
        r.click(p.locator(".cx-nav a[href$='/shop-cart/']").first)
        p.wait_for_load_state("networkidle"); r.wait(300)
        r.click(p.locator("a.shop-checkout-btn").first)
        p.wait_for_load_state("networkidle"); r.wait(600)
        r.type(p.locator("[data-field=mobile]"), "09 781 234 567", delay=45, clear=True)
        p.wait_for_function("document.querySelectorAll('#state-select option').length > 1", timeout=20000)
        r.hover(p.locator("#state-select"), 300)
        yg = p.locator("#state-select option", has_text="Yangon").first.inner_text().strip()
        p.locator("#state-select").select_option(label=yg); r.wait(700)
        p.wait_for_function("document.querySelectorAll('#city-select option').length > 1", timeout=20000)
        r.hover(p.locator("#city-select"), 300)
        cities = [o.strip() for o in p.locator("#city-select option").all_inner_texts()]
        city = next((c for c in cities if c.lower().startswith("yangon")), None)
        p.locator("#city-select").select_option(label=city) if city else p.locator("#city-select").select_option(index=1)
        r.wait(800)
        if p.locator("#township-select option").count() > 1:
            p.locator("#township-select").select_option(index=1); r.wait(400)
        r.type(p.locator("#street-address"), "No. 12, Pyay Road", delay=40, clear=True)
        r.type(p.locator("#landmark"), "Hledan Center", delay=40, clear=True)
        p.keyboard.press("Tab"); r.wait(700)
        r.spot("#state-select", "Myanmar address", 900)
    elif name == "checkout_pay":
        r.unspot()
        cod = p.locator("#cod-payment >> xpath=ancestor::*[self::label or contains(@class,'option')][1]")
        cod.scroll_into_view_if_needed(); p.evaluate("window.scrollBy(0,180)"); r.wait(400)
        r.spot_js("document.getElementById('cod-payment').closest('label, [class*=option]')", "Cash on Delivery")
        r.click(cod); r.wait(700)
        btn = p.locator("button:has-text('Confirm Cash on Delivery')").first
        r.unspot()
        r.hover(btn, 600)
        r.click(btn)
        p.wait_for_load_state("networkidle")
        p.evaluate("window.scrollTo(0, 0)"); r.wait(900)
    elif name == "invoice":
        p.evaluate("window.scrollTo(0, 0)")
        r.spot_js("[...document.querySelectorAll('h1,h2,h3')].find(e => /invoice/i.test(e.innerText))", "Invoice generated", 1400)
        r.unspot()
        r.scroll(520, steps=16, pause=600)
        pdf = p.locator("button:has-text('Download PDF')").first
        pdf.scroll_into_view_if_needed(); r.wait(300)
        r.spot_js("[...document.querySelectorAll('button')].find(b => b.innerText.includes('Download PDF'))", "Print or download PDF")
        r.hover(pdf, 1300)
    elif name == "orders":
        r.unspot()
        p.goto(url("/en/orders/")); p.wait_for_load_state("networkidle"); r.wait(500)
        r.spot("table tbody tr, .order-card", "Order history", 1200)
    elif name == "picks_set":
        r.unspot()
        r.click(p.locator(".cx-nav a.cx-ai-link").first)
        p.wait_for_load_state("networkidle"); r.wait(500)
        r.spot(".rx-bar", "Use and budget", 400)
        rng = p.locator("#budget_max")
        b = rng.bounding_box()
        frac = (1500 - 300) / (3000 - 300)
        r.move(b["x"] + b["width"] * ((1200 - 300) / 2700), b["y"] + b["height"] / 2)
        p.mouse.down(); r.move(b["x"] + b["width"] * frac, b["y"] + b["height"] / 2, steps=25); p.mouse.up()
        r.wait(600)
    elif name == "picks_results":
        r.unspot()
        r.click(p.locator("label.rx-pill:has(input[value=gaming])"))
        p.wait_for_load_state("networkidle"); r.wait(1500)
        r.spot(".cx-product", "Ranked by fit", 600)
        r.scroll(300, pause=900)
    elif name == "ai_widget":
        r.unspot()
        p.goto(url("/en/")); p.wait_for_load_state("networkidle")
        p.evaluate("try{sessionStorage.clear()}catch(e){}"); r.wait(800)
        r.click(p.locator("#veras-fab")); r.wait(500)
        r.type(p.locator("#veras-input"), "I need a laptop for programming and gaming under $1500. What do you suggest?", delay=28)
        p.keyboard.press("Enter")
        p.wait_for_selector(".veras-cards", timeout=120000)
        _last_ai[0] = time.time()
        r.wait(1200)
        r.spot("#veras-panel", "Real products from the database", 1500)
    elif name == "gradio_open":
        r.unspot()
        p.goto(url("/en/chat/")); p.wait_for_load_state("networkidle"); r.wait(500)
        r.click(p.locator(".veras-tabs [data-tab='studio']")); r.wait(3500)
        r.spot(".veras-studio", "Built with Gradio", 1200)
    elif name == "g_text":
        r.type(p.locator("textarea").first, "What is the difference between Intel Core i5 and i7 for programming?", delay=26)
        r.click(p.get_by_role("button", name="Send"))
        gradio_wait(p)
        r.wait(600)
    elif name == "g_image":
        r.click(p.get_by_role("tab", name="📷 Image")); r.wait(400)
        gradio_upload(r, "Click to Upload", ROOT / "assets" / "laptop_photo.jpg"); r.wait(900)
        r.type(p.get_by_placeholder("Ask about this image..."), "Find laptops like this one", delay=40)
        r.click(p.get_by_role("button", name="Analyze image"))
        gradio_wait(p, 300)
        r.wait(800)
    elif name == "g_voice_upload":
        r.click(p.get_by_role("tab", name="🎙️ Voice")); r.wait(400)
        r.click(p.get_by_role("button", name="Upload file").locator("visible=true").first); r.wait(400)
        gradio_upload(r, "Drop Audio Here", ROOT / "assets" / "voice_question.wav"); r.wait(800)
        play = p.locator("button[aria-label*='Play'], .play-pause-button").locator("visible=true").first
        if play.count():
            r.click(play)
        r.wait(1000)
    elif name == "g_voice_answer":
        r.click(p.get_by_role("button", name="Transcribe & ask"))
        gradio_wait(p, 240)
        tb = p.get_by_label("Transcribed text (Whisper)")
        tb.scroll_into_view_if_needed(); r.wait(400)
        r.spot_js("(() => { const l = [...document.querySelectorAll('label, span')].find(e => e.innerText.trim().startsWith('Transcribed text')); return l && (l.closest('.block, label') || l); })()", "What Whisper heard")
        r.wait(1600)
    else:
        raise ValueError(name)


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #
def chrome_png(page, item):
    path = WORK / "chrome" / f"{item['id']}.png"
    page.evaluate("c => window.renderChrome(c)", {
        "title": item["title"], "chapterIndex": item["chapterIndex"], "pills": item["pills"],
        "pill": item["pill"], "url": item.get("url_label", ""), "note": item.get("note"),
        "caption": item["caption"]})
    page.screenshot(path=str(path))
    return path


def title_clip(page, item, dur):
    """Render an animated headline card with composer.renderAt -> clip."""
    fdir = WORK / "frames" / item["id"]
    fdir.mkdir(parents=True, exist_ok=True)
    for f in fdir.glob("*.jpg"):
        f.unlink()
    scene = {"type": "headline", "dur": dur, **item["scene"]}
    page.evaluate("s => { window.SCENES = [s]; }", scene)
    n = int(dur * FPS)
    for i in range(n):
        page.evaluate("t => window.renderAt(t)", i / FPS)
        page.screenshot(path=str(fdir / f"{i:05d}.jpg"), type="jpeg", quality=92)
    clip = WORK / "clips" / f"{item['id']}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(fdir / "%05d.jpg"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(clip)], check=True)
    return clip


def build_segment(item, chrome, clip_dur):
    """Frame + speed-fit the live clip, add narration (+ optional sound) -> seg/<id>.mp4"""
    nar, nar_dur = tts(item["narration"])
    sfx = item.get("sfx")
    sfx_dur = probe(sfx) if sfx else 0
    speech_end = 0.3 + nar_dur + (0.35 + sfx_dur if sfx else 0)
    target = speech_end + 0.7
    factor = 1.0
    if clip_dur > target + 0.4 and item.get("max_speed", 1) > 1:
        factor = min(clip_dur / target, item["max_speed"])
    vid_dur = clip_dur / factor
    dur = max(vid_dur, target)
    out = WORK / "seg" / f"{item['id']}.mp4"
    R = {"x": 70, "y": 152, "w": 1408, "h": 792}
    inputs = ["-loop", "1", "-framerate", str(FPS), "-i", str(chrome), "-i", str(WORK / "clips" / f"{item['id']}.mp4"), "-i", str(nar)]
    fc = (f"[1:v]setpts=PTS/{factor:.4f},scale={R['w']}:{R['h']}:flags=lanczos,"
          f"tpad=stop_mode=clone:stop_duration={max(0, dur - vid_dur) + 0.1:.3f}[v];"
          f"[0:v][v]overlay={R['x']}:{R['y']}:shortest=0,trim=0:{dur:.3f},setpts=PTS-STARTPTS,"
          f"fade=t=in:st=0:d=0.25,fade=t=out:st={dur - 0.25:.3f}:d=0.25,format=yuv420p[vout];"
          f"[2:a]adelay=300|300[a0]")
    amix = "[a0]"
    if sfx:
        inputs += ["-i", sfx]
        d = int((0.3 + nar_dur + 0.35) * 1000)
        fc += f";[3:a]aformat=channel_layouts=stereo,adelay={d}|{d}[a1]"
        amix = "[a0][a1]"
    fc += f";{amix}amix=inputs={2 if sfx else 1}:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo,apad,atrim=0:{dur:.3f}[aout]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
                    "-t", f"{dur:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-c:a", "aac", "-b:a", "160k", str(out)], check=True)
    return out, dur, factor


def build_title_segment(page, item):
    nar, nar_dur = tts(item["narration"])
    base = 8.0 if item["scene"].get("features") else 4.0
    dur = max(base, nar_dur + 1.1)
    clip = title_clip(page, item, dur)
    out = WORK / "seg" / f"{item['id']}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-i", str(nar), "-filter_complex",
                    f"[1:a]adelay=350|350,aformat=sample_rates=48000:channel_layouts=stereo,apad,atrim=0:{dur:.3f}[a]",
                    "-map", "0:v", "-map", "[a]", "-t", f"{dur:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium",
                    "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", str(out)], check=True)
    return out, dur


def compose(browser):
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.add_init_script(f"window.SCENES = []; window.CHAPTERS = {json.dumps(CHAPTERS)};")
    page.goto((ROOT / "composer.html").as_uri())
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
    meta = json.loads((WORK / "clips.json").read_text()) if (WORK / "clips.json").exists() else {}
    segs, total = [], 0.0
    for item in STORY:
        if item["kind"] == "title":
            out, dur = build_title_segment(page, item)
        else:
            m = meta[item["id"]]
            item = {**item, "url_label": item.get("url") or m.get("url", "")}
            out, dur, factor = build_segment(item, chrome_png(page, item), m["dur"])
            if factor > 1.01:
                print(f"   {item['id']}: sped up x{factor:.2f}")
        segs.append(out)
        total += dur
        print(f" ▶ {item['id']:4s} {dur:5.1f}s   total {total:6.1f}s")
    lst = WORK / "segments.txt"
    lst.write_text("\n".join(f"file '{s.as_posix()}'" for s in segs))
    final = OUT / "CyberOptix_Demo_Live.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    print(f"\nvideo: {final}  ({total // 60:.0f}:{total % 60:04.1f})")
    page.close()


# --------------------------------------------------------------------------- #
def record(browser, only=None):
    ctx = browser.new_context(viewport=VIEW, device_scale_factor=1920 / 1440, locale="en-US", color_scheme="dark")
    ctx.add_init_script("try{localStorage.setItem('cx-theme','dark')}catch(e){}")
    ctx.add_init_script(INJECT)
    site = ctx.new_page()
    site.set_default_timeout(30000)
    rec = {"site": Rec(ctx, site)}
    meta_path = WORK / "clips.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    state = {}

    site.goto(f"{BASE}/en/"); site.wait_for_load_state("networkidle")
    lives = [s for s in STORY if s["kind"] == "live"]
    # when re-recording a subset, replay the earlier steps silently so state (login, cart) is right
    for item in lives:
        if item["page"] == "gradio" and "gradio" not in rec:
            g = ctx.new_page()
            g.set_default_timeout(60000)
            g.goto(GRADIO); g.wait_for_selector("textarea", timeout=90000); g.wait_for_timeout(1200)
            rec["gradio"] = Rec(ctx, g)
        r = rec[item["page"]]
        do_record = not only or item["id"] in only
        if not do_record and item["action"] in AI_ACTIONS | {"g_voice_upload"}:
            continue                       # don't spend AI calls on steps we aren't recording
        if item["action"] in AI_ACTIONS:
            ai_gap()                       # waits happen before recording starts
        print(f" ● {item['id']:4s} {item['action']}")
        if do_record:
            r.start(item["id"])
        run_action(item["action"], r, state)
        if do_record:
            _, nar_dur = tts(item["narration"])
            sfx_dur = probe(item["sfx"]) if item.get("sfx") else 0
            min_dur = 0.3 + nar_dur + (0.35 + sfx_dur if item.get("sfx") else 0) + 0.6
            dur = r.stop(item["id"], min_dur=min_dur if item["max_speed"] <= 1 else 0)
            page_url = r.page.url.replace("http://", "") if item["page"] == "site" else ""
            meta[item["id"]] = {"dur": dur, "url": page_url}
            meta_path.write_text(json.dumps(meta, indent=1))
            print(f"   recorded {dur:.1f}s")
    ctx.close()


def reset_demo_state():
    """Fresh wishlist for the demo account (cart is per browser session)."""
    code = ("from userauths.models import User; from flame.models import Wishlist; "
            f"u=User.objects.get(email='{CREDS['email']}'); print('wishlist cleared', Wishlist.objects.filter(user=u).delete()[0])")
    subprocess.run([str(ROOT.parent / ".venv" / "Scripts" / "python.exe"), "manage.py", "shell", "-c", code],
                   cwd=ROOT.parent / "inferno", check=False)


def main():
    args = sys.argv[1:]
    only = None
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))
    for item in STORY:                      # synthesize all narration up front
        tts(item["narration"])
    print("narration ready")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        if "--compose" not in args:
            reset_demo_state()
            # the site must be signed out at the start
            record(browser, only)
        if "--record-only" not in args:
            compose(browser)
        browser.close()


if __name__ == "__main__":
    main()
