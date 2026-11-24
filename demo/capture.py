"""
Capture real CyberOptix screens for the demo video.

Drives the running dev server (http://127.0.0.1:8000) in headless Microsoft Edge with
Playwright, performs the demo user journey, and saves a 2x screenshot per step plus the
on-screen rectangle of the element each step highlights (demo/shots/shots.json).

Usage (from the repository root):
    .venv\\Scripts\\python.exe demo\\capture.py            # everything
    .venv\\Scripts\\python.exe demo\\capture.py ai         # only steps whose name contains "ai"
Requires: the dev server on :8000, demo/.demo_credentials (local demo account).
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / "shots"
SHOTS.mkdir(exist_ok=True)
META = SHOTS / "shots.json"
BASE = "http://127.0.0.1:8000"
GRADIO = "http://127.0.0.1:7860"
VIEW = {"width": 1440, "height": 786}           # = the browser frame inside the video
CREDS = json.loads((ROOT / ".demo_credentials").read_text())
SHOP, PRODUCT = "shop45hfg5e5ba", "334ef4d3aa"   # Citicom - ASUS ROG Strix G17
SHOP2_PRODUCT = "1h4aib31ea"                     # Citicom - MacBook Air 15"
AI_GAP = 55                                       # free AI: 1 reply / 45 s per IP, counted from the end of a reply

only = sys.argv[1] if len(sys.argv) > 1 else None
meta = json.loads(META.read_text()) if META.exists() else {}
_last_ai = [0.0]


def ai_wait():
    gap = time.time() - _last_ai[0]
    if gap < AI_GAP:
        time.sleep(AI_GAP - gap)
    _last_ai[0] = time.time()


def rect(page, selector, frame=None):
    """Bounding box (CSS px, viewport) of the first visible match."""
    try:
        loc = (frame or page).locator(selector).first
        b = loc.bounding_box(timeout=3000)
        if b:
            return [round(b["x"]), round(b["y"]), round(b["width"]), round(b["height"])]
    except Exception as exc:
        print("   ! highlight not found:", selector, exc.__class__.__name__)
    return None


def shot(page, name, url, hl=None, frame=None, full=False):
    path = SHOTS / f"{name}.png"
    box = rect(page, hl, frame) if hl else None
    if full:
        page.screenshot(path=str(path), full_page=True)
        h = page.evaluate("document.documentElement.scrollHeight")
    else:
        page.screenshot(path=str(path))
        h = VIEW["height"]
    meta[name] = {"image": f"shots/{name}.png", "url": url, "hl": box, "imgH": h}
    META.write_text(json.dumps(meta, indent=2))
    print(f" ✓ {name}  hl={box}")


def settle(page, ms=900):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


def scroll_to(page, selector, offset=110):
    page.evaluate("""([s, o]) => { const el = document.querySelector(s);
        if (el) window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - o); }""", [selector, offset])
    page.wait_for_timeout(500)


def want(name):
    return not only or any(part and part in name for part in only.split(","))


def login(page):
    page.goto(f"{BASE}/en/user/sign-in/")
    settle(page)
    form = page.locator("form:has(input[name=email])").first
    form.locator("input[name=email]").fill(CREDS["email"])
    form.locator("input[name=password]").fill(CREDS["password"])
    form.locator("button[type=submit]").click()
    settle(page)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport=VIEW, device_scale_factor=2, locale="en-US",
                                  color_scheme="dark")
        ctx.add_init_script("try{localStorage.setItem('cx-theme','dark')}catch(e){}")
        page = ctx.new_page()
        page.set_default_timeout(20000)

        # ------------------------------------------------------------ intro / home
        if want("home"):
            page.goto(f"{BASE}/en/")
            settle(page, 3500)            # let the 3D laptop open
            shot(page, "home_hero", "127.0.0.1:8000/en/", hl="#hx-laptop")

        # ---------------------------------------------------------------- sign in
        if want("auth"):
            page.goto(f"{BASE}/en/user/sign-in/")
            settle(page)
            shot(page, "auth_signin", "127.0.0.1:8000/en/user/sign-in/", hl="a[href*='google/login']")
            form = page.locator("form:has(input[name=email])").first
            form.locator("input[name=email]").fill(CREDS["email"])
            form.locator("input[name=password]").fill("•" * 10)
            shot(page, "auth_filled", "127.0.0.1:8000/en/user/sign-in/", hl="form:has(input[name=email]) button[type=submit]")
        login(page)
        if want("auth"):
            shot(page, "auth_loggedin", "127.0.0.1:8000/en/", hl="#userMenu")
            page.locator("#userMenu").hover()
            page.wait_for_timeout(600)
            shot(page, "auth_menu", "127.0.0.1:8000/en/", hl=".cx-nav .dropdown-menu")

        # ---------------------------------------------------------------- browse
        if want("browse"):
            page.goto(f"{BASE}/en/products/")
            settle(page)
            shot(page, "browse_list", "127.0.0.1:8000/en/products/", hl=".pl-toolbar")
            scroll_to(page, ".cx-grid, .product-grid, #filtered-product", 120)
            shot(page, "browse_grid", "127.0.0.1:8000/en/products/", hl=".cx-product")
            page.goto(f"{BASE}/en/shop/{SHOP}/product/{PRODUCT}/")
            settle(page, 1200)
            shot(page, "browse_detail", f"127.0.0.1:8000/en/shop/citicom/product/{PRODUCT}/", hl=".pd-gallery .option")
            page.locator(".tab-btn[data-target='#additional-info']").click()
            scroll_to(page, ".tab-navigation", 140)
            shot(page, "browse_specs", f"127.0.0.1:8000/en/shop/citicom/product/{PRODUCT}/", hl="#additional-info")

        # ---------------------------------------------------------------- filters
        if want("filter"):
            page.goto(f"{BASE}/en/")
            settle(page)
            page.locator("#menu-toggle").click()
            page.wait_for_timeout(700)
            shot(page, "filter_sidebar", "127.0.0.1:8000/en/", hl="#sidebar")
            page.goto(f"{BASE}/en/products/?brand=Asus")
            settle(page)
            shot(page, "filter_brand", "127.0.0.1:8000/en/products/?brand=Asus", hl=".pl-hero h1, section h1")
            page.goto(f"{BASE}/en/products/")
            settle(page)
            page.locator(".current-price-input").fill("1000")
            page.locator("#price-filter-btn").click()
            page.wait_for_timeout(1800)
            shot(page, "filter_price", "127.0.0.1:8000/en/products/", hl=".pl-toolbar .filter-group:has(.current-price-input), .current-price-input")
            page.goto(f"{BASE}/en/search/?q=macbook")
            settle(page)
            shot(page, "filter_search", "127.0.0.1:8000/en/search/?q=macbook", hl="h1")

        # --------------------------------------------------------------- bilingual
        if want("lang"):
            page.goto(f"{BASE}/en/products/")
            settle(page)
            shot(page, "lang_en", "127.0.0.1:8000/en/products/", hl=".language-switcher-container")
            page.locator(".language-switcher-container label.switch").click()
            settle(page, 1500)
            shot(page, "lang_my_products", "127.0.0.1:8000/my/products/", hl="h1")
            page.goto(f"{BASE}/my/")
            settle(page, 3000)
            shot(page, "lang_my_home", "127.0.0.1:8000/my/", hl=".hx-title")
            page.goto(f"{BASE}/my/shop/{SHOP}/product/{PRODUCT}/")
            settle(page)
            shot(page, "lang_my_detail", f"127.0.0.1:8000/my/shop/citicom/product/{PRODUCT}/", hl=".tab-navigation")
            page.locator(".language-switcher-container label.switch").click()
            settle(page)

        # -------------------------------------------------------------------- cart
        if want("cart"):
            # clear any old cart rows first
            page.goto(f"{BASE}/en/shop-cart/")
            settle(page)
            for _ in range(10):
                btns = page.locator(".delete-product, [class*=delete-shop-product], .delete-shop-cart-product")
                if not btns.count():
                    break
                btns.first.click()
                page.wait_for_timeout(900)
            page.goto(f"{BASE}/en/shop/{SHOP}/product/{SHOP2_PRODUCT}/")
            settle(page)
            page.locator("#add-to-cart-btn").click()
            page.wait_for_timeout(1500)
            page.goto(f"{BASE}/en/shop/{SHOP}/product/{PRODUCT}/")
            settle(page)
            page.locator("#add-to-cart-btn").scroll_into_view_if_needed()
            page.evaluate("window.scrollBy(0, 160)")
            page.wait_for_timeout(500)
            shot(page, "cart_detail", f"127.0.0.1:8000/en/shop/citicom/product/{PRODUCT}/", hl="#add-to-cart-btn")
            page.locator("#add-to-cart-btn").click()
            page.wait_for_timeout(1500)
            shot(page, "cart_added", f"127.0.0.1:8000/en/shop/citicom/product/{PRODUCT}/", hl="#add-to-cart-btn")
            page.goto(f"{BASE}/en/shop-cart/")
            settle(page)
            shot(page, "cart_page", "127.0.0.1:8000/en/shop-cart/", hl="input[type=number]")
            qty = page.locator("input[type=number]").first
            qty.fill("2")
            qty.dispatch_event("change")
            page.wait_for_timeout(1800)
            shot(page, "cart_qty", "127.0.0.1:8000/en/shop-cart/", hl=".global-cart-summary")

        # ---------------------------------------------------------------- wishlist
        if want("wish"):
            page.goto(f"{BASE}/en/products/")
            settle(page)
            scroll_to(page, ".cx-grid, #filtered-product", 120)
            hearts = page.locator(".add-to-wishlist")
            shot(page, "wish_heart", "127.0.0.1:8000/en/products/", hl=".add-to-wishlist")
            for i in range(2):
                hearts.nth(i).click()
                page.wait_for_timeout(1200)
            page.goto(f"{BASE}/en/wishlist/")
            settle(page)
            shot(page, "wish_page", "127.0.0.1:8000/en/wishlist/", hl=".wishlist-items")

        # ---------------------------------------------------------------- checkout
        if want("checkout"):
            page.goto(f"{BASE}/en/shop-cart/")
            settle(page)
            page.locator('a.shop-checkout-btn').first.click()
            settle(page, 1500)
            page.locator("[data-field=mobile]").fill("09 781 234 567")
            shot(page, "checkout_billing", f"127.0.0.1:8000/en/checkout/shop/{SHOP}/", hl="#billing-form")
            page.wait_for_function("document.querySelectorAll('#state-select option').length > 1", timeout=20000)
            page.locator("#state-select").select_option(label=page.locator("#state-select option", has_text="Yangon").first.inner_text().strip())
            page.wait_for_function("document.querySelectorAll('#city-select option').length > 1", timeout=20000)
            page.locator("#city-select").select_option(index=1)
            page.wait_for_timeout(1200)
            if page.locator("#township-select option").count() > 1:
                page.locator("#township-select").select_option(index=1)
            page.locator("#street-address").fill("No. 12, Pyay Road")
            page.locator("#landmark").fill("Hledan Center")
            page.locator("#landmark").press("Tab")
            page.wait_for_timeout(1500)
            scroll_to(page, "#state-select", 200)
            shot(page, "checkout_address", f"127.0.0.1:8000/en/checkout/shop/{SHOP}/", hl="#state-select")
            scroll_to(page, "[data-payment-type='cod']", 360)
            shot(page, "checkout_payment", f"127.0.0.1:8000/en/checkout/shop/{SHOP}/", hl="#cod-payment >> xpath=ancestor::*[self::label or contains(@class,'option')][1]")
            confirm = page.locator("button:has-text('Confirm Cash on Delivery')").first
            confirm.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            shot(page, "checkout_confirm", f"127.0.0.1:8000/en/checkout/shop/{SHOP}/", hl="button:has-text('Confirm Cash on Delivery')")
            confirm.click()
            settle(page, 1800)
            print("   after confirm:", page.url)
            shot(page, "receipt_top", page.url.replace("http://", ""), hl="h1, .invoice-title, [class*=invoice-head]")
            page.locator("button:has-text('Download PDF')").first.scroll_into_view_if_needed()
            page.evaluate("window.scrollBy(0, 250)")
            page.wait_for_timeout(500)
            shot(page, "receipt_total", page.url.replace("http://", ""), hl="button:has-text('Download PDF')")
            page.goto(f"{BASE}/en/orders/")
            settle(page)
            shot(page, "receipt_orders", "127.0.0.1:8000/en/orders/", hl="table tbody tr, .order-card")

        # ---------------------------------------------------------------- AI picks
        if want("picks"):
            page.goto(f"{BASE}/en/recommendation_page/")
            settle(page)
            shot(page, "picks_form", "127.0.0.1:8000/en/recommendation_page/", hl=".rx-bar")
            page.goto(f"{BASE}/en/recommendation_page/?purpose=gaming&budget_max=1500")
            settle(page, 1500)
            page.evaluate("window.scrollTo(0, 0)")
            scroll_to(page, ".rx-results-head", 90)
            shot(page, "picks_results", "127.0.0.1:8000/en/recommendation_page/?purpose=gaming&budget_max=1500", hl=".cx-product")

        # ------------------------------------------------------- AI chat widget
        if want("ai_widget"):
            page.goto(f"{BASE}/en/")
            settle(page, 1500)
            page.evaluate("try{sessionStorage.clear()}catch(e){}")
            page.reload()
            settle(page, 1500)
            page.locator("#veras-fab").click()
            page.wait_for_timeout(700)
            ai_wait()
            page.locator("#veras-input").fill("I need a laptop for programming and gaming under $1500. What do you suggest?")
            page.locator("#veras-input").press("Enter")
            page.wait_for_selector(".veras-cards", timeout=90000)
            page.wait_for_timeout(1500)
            shot(page, "ai_widget", "127.0.0.1:8000/en/", hl="#veras-panel")

        # ----------------------------------------------------- Gradio AI studio
        voice_only = only == "ai_voice"
        if want("ai_studio") or voice_only:
            if not voice_only:
                page.goto(f"{BASE}/en/chat/")
                settle(page, 1500)
                page.locator(".veras-tabs [data-tab='studio']").click()
                page.wait_for_timeout(6000)
                shot(page, "ai_studio_embed", "127.0.0.1:8000/en/chat/", hl=".veras-studio")

            g = ctx.new_page()
            g.set_default_timeout(30000)
            g.goto(GRADIO)
            g.wait_for_selector("textarea", timeout=60000)
            g.wait_for_timeout(1500)

            def wait_answer(_n=None, timeout=240):
                """Wait until Gradio finishes (its 'processing | 3.1s' badge disappears)."""
                g.wait_for_timeout(1500)
                t0 = time.time()
                while time.time() - t0 < timeout:
                    busy = g.locator("text=/processing \|/").count() + g.locator(".progress-text, .eta-bar").count()
                    if not busy:
                        break
                    time.sleep(1)
                g.wait_for_timeout(1500)
                _last_ai[0] = time.time()          # the free-tier window starts when a reply ends
                msgs = g.locator("[data-testid='bot']")
                return msgs.last.inner_text() if msgs.count() else ""

            def upload(path, hint="Click to Upload"):
                """Upload through the visible drop area of the active tab."""
                with g.expect_file_chooser() as fc:
                    g.get_by_text(hint).locator("visible=true").first.click()
                fc.value.set_files(str(path))

            if not voice_only:
                # A. text
                ai_wait()
                g.locator("textarea").first.fill("What is the difference between Intel Core i5 and i7 for programming?")
                g.get_by_role("button", name="Send").click()
                print("   text ->", wait_answer(1)[:120].replace("\n", " "))
                shot(g, "ai_studio_text", "127.0.0.1:8000/en/chat/  ·  Veras AI Studio (Gradio)", hl="[data-testid='bot']")

                # B. image
                g.get_by_role("tab", name="📷 Image").click()
                g.wait_for_timeout(800)
                upload(ROOT / "assets" / "laptop_photo.jpg")
                g.wait_for_timeout(2000)
                g.get_by_placeholder("Ask about this image...").fill("Find laptops like this one")
                shot(g, "ai_studio_image_upload", "127.0.0.1:8000/en/chat/  ·  Veras AI Studio (Gradio)", hl="[data-testid='image'], .image-container, .upload-container")
                ai_wait()
                g.get_by_role("button", name="Analyze image").click()
                print("   image ->", wait_answer(2, 300)[:160].replace("\n", " "))
                shot(g, "ai_studio_image", "127.0.0.1:8000/en/chat/  ·  Veras AI Studio (Gradio)", hl="[data-testid='bot'] >> nth=-1")

            # C. voice
            g.get_by_role("tab", name="🎙️ Voice").click()
            g.wait_for_timeout(800)
            g.get_by_role("button", name="Upload file").locator("visible=true").first.click()
            g.wait_for_timeout(800)
            upload(ROOT / "assets" / "voice_question.wav", "Drop Audio Here")
            g.wait_for_timeout(2500)
            shot(g, "ai_studio_voice_upload", "127.0.0.1:8000/en/chat/  ·  Veras AI Studio (Gradio)", hl="[data-testid='waveform-Audio'], .audio-container, audio")
            ai_wait()
            g.get_by_role("button", name="Transcribe & ask").click()
            print("   voice ->", wait_answer(3, 180)[:160].replace("\n", " "))
            g.get_by_label("Transcribed text (Whisper)").scroll_into_view_if_needed()
            g.wait_for_timeout(600)
            shot(g, "ai_studio_voice", "127.0.0.1:8000/en/chat/  ·  Veras AI Studio (Gradio)", hl="label:has-text('Transcribed text')")

        browser.close()


if __name__ == "__main__":
    main()
