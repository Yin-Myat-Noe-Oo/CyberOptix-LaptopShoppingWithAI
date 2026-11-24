"""
Render the CyberOptix demo video from the captured screens.

    .venv\\Scripts\\python.exe demo\\render.py            # full video -> demo/out/CyberOptix_Demo.mp4
    .venv\\Scripts\\python.exe demo\\render.py --preview  # a few stills -> demo/out/preview_*.png

The storyboard (STORY) mirrors the reference video's structure: headline scenes, then
numbered chapters whose steps show a real screenshot with a highlight box, an orange
callout, step pills, a chapter timeline and a caption line.
"""
import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
FPS = 24
SHOTS = json.loads((ROOT / "shots" / "shots.json").read_text())

CHAPTERS = ["Sign in", "Browse", "Search & filter", "Myanmar / English", "Cart",
            "Wishlist", "Checkout", "Receipt", "AI Picks", "AI chatbot"]

GRADIO_URL = "127.0.0.1:7860  ·  Veras AI Studio (Gradio, embedded at /en/chat/)"


def step(shot, pill, dur, callout, caption, click=False, note=None, url=None, zoom=None):
    s = SHOTS[shot]
    return {"shot": shot, "pill": pill, "dur": dur, "callout": callout, "caption": caption,
            "click": click, "note": note, "image": s["image"], "hl": s["hl"],
            "url": url or s["url"], "imgH": s["imgH"], "zoom": zoom}


STORY = [
    {"type": "headline", "dur": 6, "headline": "Choosing a laptop is <em>hard</em>.",
     "caption": "Hundreds of models, confusing specs, and shops all over Myanmar."},
    {"type": "headline", "dur": 6, "logo": True, "tagline": "AI-powered laptop shopping for Myanmar",
     "caption": "CyberOptix brings the shops, the specs and an AI shopping assistant into one website."},
    {"type": "headline", "dur": 12, "headline": "Everything in <em>one place</em>",
     "features": [
         {"icon": "🔐", "title": "Sign in", "text": "Google OAuth 2.0 or email & password"},
         {"icon": "💻", "title": "Browse", "text": "193 products from 4 partner shops"},
         {"icon": "🔎", "title": "Search & filter", "text": "Category, brand, price and keyword"},
         {"icon": "🌐", "title": "Myanmar / English", "text": "Full bilingual interface"},
         {"icon": "🛒", "title": "Cart & wishlist", "text": "Save, compare and buy later"},
         {"icon": "🧾", "title": "Checkout & receipt", "text": "Myanmar addresses, invoice & PDF"},
         {"icon": "✨", "title": "AI Picks", "text": "Laptops ranked for your use and budget", "ai": True},
         {"icon": "🤖", "title": "Veras AI chatbot", "text": "Gradio app · text, image and voice", "ai": True},
     ], "caption": "Here is what the project does - every screen in this video is the real, running website."},
    {"type": "headline", "dur": 6, "headline": "It all starts at <em>CyberOptix</em>",
     "image": SHOTS["home_hero"]["image"], "url_bar": "127.0.0.1:8000/en/",
     "caption": "The home page: a search bar, quick AI shortcuts, and an interactive 3D laptop you can rotate."},

    {"type": "chapter", "title": "Sign in", "pills": ["Google", "Email", "Signed in"], "steps": [
        step("auth_signin", "Google", 7, "Continue with Google",
             "Customers can sign in with Google - CyberOptix implements its own Google OAuth 2.0 flow.",
             click=True, note="Google sign-in needs the project's Google OAuth client ID. This recording signs in with a demo email account."),
        step("auth_filled", "Email", 5, "Or use email & password",
             "Or sign in with an email and password. New accounts verify their email first."),
        step("auth_menu", "Signed in", 5, "Signed in",
             "Signed in - the account menu now offers the profile, personal picks and sign out."),
    ]},
    {"type": "chapter", "title": "Browse laptops", "pills": ["Catalog", "Details", "Specs"], "steps": [
        step("browse_grid", "Catalog", 6, "193 products · 4 shops",
             "The catalog shows every laptop with its shop, specs, and prices in US dollars and Kyat."),
        step("browse_detail", "Details", 7, "Photo gallery",
             "A product page has a photo gallery, the price with any discount, and the description."),
        step("browse_specs", "Specs", 6, "Full specifications",
             "Additional Info lists the full specifications, so customers can compare models side by side."),
    ]},
    {"type": "chapter", "title": "Search and filter", "pills": ["Category", "Brand", "Price", "Search"], "steps": [
        step("filter_sidebar", "Category", 5.5, "Categories & brands",
             "The side menu filters by category - laptop, desktop, accessories - and by brand."),
        step("filter_brand", "Brand", 5, "Brand: Asus",
             "Choosing a brand shows only that brand's products."),
        step("filter_price", "Price", 5.5, "Up to $1,000",
             "The price filter narrows the list to a budget."),
        step("filter_search", "Search", 5, "Search: \"macbook\"",
             "And search finds a specific model by name."),
    ]},
    {"type": "chapter", "title": "Myanmar and English", "pills": ["Switch", "Myanmar", "Products"], "steps": [
        step("lang_en", "Switch", 4.5, "One-click language switch",
             "One click switches the whole site between English and Myanmar.", click=True),
        step("lang_my_home", "Myanmar", 5, "Full Myanmar interface",
             "Every page, button and message is translated - not just the menu."),
        step("lang_my_detail", "Products", 4.5, "Product pages too",
             "Product pages, checkout and the AI assistant follow the chosen language."),
    ]},
    {"type": "chapter", "title": "Shopping cart", "pills": ["Add", "Cart", "Quantity"], "steps": [
        step("cart_detail", "Add", 6, "Add to Cart",
             "On the product page, Add to Cart puts the laptop in the cart without leaving the page.", click=True),
        step("cart_page", "Cart", 6, "Change quantity",
             "The cart groups items by shop, with the unit price, quantity and subtotal."),
        step("cart_qty", "Quantity", 6, "Totals update instantly",
             "Changing a quantity or removing an item updates the totals straight away."),
    ]},
    {"type": "chapter", "title": "Wishlist", "pills": ["Save", "Wishlist"], "steps": [
        step("wish_heart", "Save", 5.5, "Save for later", "The heart saves a laptop to the wishlist.", click=True),
        step("wish_page", "Wishlist", 6.5, "Add to cart or remove",
             "Saved laptops wait here - one click moves them to the cart, or removes them."),
    ]},
    {"type": "chapter", "title": "Checkout", "pills": ["Details", "Address", "Payment", "Confirm"], "steps": [
        step("checkout_billing", "Details", 6, "Name & mobile",
             "Checkout starts with the customer's name and mobile number."),
        step("checkout_address", "Address", 6, "Myanmar address & shipping",
             "The delivery address uses Myanmar states and cities, and the shipping fee is added automatically."),
        step("checkout_payment", "Payment", 6, "Cash on Delivery",
             "Here the customer pays with Cash on Delivery.",
             note="PayPal, Stripe and KBZPay buttons are also on this page; they need payment-provider accounts, so this demo uses Cash on Delivery."),
        step("checkout_confirm", "Confirm", 5.5, "Confirm order", "Confirm - and the order is placed.", click=True),
    ]},
    {"type": "chapter", "title": "Order confirmation", "pills": ["Invoice", "PDF", "Orders"], "steps": [
        step("receipt_top", "Invoice", 6.5, "Invoice generated",
             "The customer gets an invoice right away: order number, delivery address and payment method."),
        step("receipt_total", "PDF", 5.5, "Print or download PDF",
             "The invoice can be printed or downloaded as a PDF.", click=True),
        step("receipt_orders", "Orders", 6, "Order history",
             "Every order is kept in My Orders, with its status and tracking."),
    ]},
    {"type": "chapter", "title": "AI Picks", "pills": ["Use & budget", "Ranking"], "steps": [
        step("picks_form", "Use & budget", 7, "Pick a use and a budget",
             "AI Picks asks two things: what the laptop is for, and the budget."),
        step("picks_results", "Ranking", 9, "Ranked by fit",
             "Every laptop is scored on CPU tier, RAM, purpose keywords and value for money - the best matches come first.",
             note="Content-based ranking computed from the live product catalogue."),
    ]},
    {"type": "chapter", "title": "Veras AI chatbot", "pills": ["Chat", "Gradio", "Text", "Image", "Voice"], "steps": [
        step("ai_widget", "Chat", 8, "Ask in plain language",
             "Veras, the AI assistant, is on every page. Ask in English or Burmese and it recommends real products.",
             note="Text AI: free gpt-oss-20b model via Pollinations. Product cards always come from the CyberOptix database."),
        step("ai_studio_embed", "Gradio", 6.5, "Built with Gradio",
             "The Veras AI Studio is a Gradio app embedded in the site, with three ways to ask."),
        step("ai_studio_text", "Text", 8, "Text: explains specs",
             "Text: it explains specifications - like Core i5 versus i7 - and links matching laptops.",
             url=GRADIO_URL),
        step("ai_studio_image_upload", "Image", 5, "Upload a laptop photo",
             "Image search: upload a photo instead of typing a model name.", url=GRADIO_URL),
        step("ai_studio_image", "Image", 8, "Finds look-alike products",
             "Veras recognises a gaming laptop, most likely ASUS, and finds the closest products in the catalogue.",
             url=GRADIO_URL, note="Image search: CLIP model running locally compares the photo with every product image."),
        step("ai_studio_voice_upload", "Voice", 5, "Speak a question",
             "Voice: record or upload a spoken question.", url=GRADIO_URL),
        step("ai_studio_voice", "Voice", 8.5, "Transcribed, then answered",
             "Whisper turns the speech into text, and the AI answers with a recommendation.",
             url=GRADIO_URL, note="Speech-to-text: Whisper (faster-whisper) running locally - no paid API."),
    ]},
    {"type": "headline", "dur": 7.5, "headline": "Your next laptop, <em>picked by AI</em>.", "logo": True,
     "tagline": "Django · Bilingual · Gradio AI chatbot",
     "caption": "CyberOptix - a complete laptop e-commerce website with AI built in. Thank you for watching."},
]


def build_scenes():
    scenes = []
    for item in STORY:
        if item["type"] != "chapter":
            scenes.append(item)
            continue
        at, steps = 0.0, []
        for st in item["steps"]:
            steps.append({**st, "at": at})
            at += st["dur"]
        scenes.append({"type": "chapter", "title": item["title"], "pills": item["pills"],
                       "chapterIndex": len([x for x in scenes if x["type"] == "chapter"]),
                       "dur": at, "steps": steps})
    return scenes


def main():
    preview = "--preview" in sys.argv
    scenes = build_scenes()
    total = sum(s["dur"] for s in scenes)
    print(f"{len(scenes)} scenes, {total:.1f}s ({int(total // 60)}:{int(total % 60):02d})")
    (OUT / "scenes.json").write_text(json.dumps(scenes, indent=1))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.add_init_script(f"window.SCENES = {json.dumps(scenes)}; window.CHAPTERS = {json.dumps(CHAPTERS)};")
        page.goto((ROOT / "composer.html").as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        # preload every image once so frames never show a blank screenshot
        page.evaluate("""Promise.all([...new Set(window.SCENES.flatMap(s => s.image ? [s.image] : (s.steps||[]).map(x => x.image)))]
                       .map(src => new Promise(r => { const i = new Image(); i.onload = i.onerror = r; i.src = src; })))""")

        def frame(t):
            page.evaluate("t => window.renderAt(t)", t)
            page.evaluate("Promise.all([...document.images].map(i => i.complete ? 1 : i.decode().catch(() => 1)))")
            return page.screenshot(type="png")

        if preview:
            acc = 0
            for k, s in enumerate(scenes):
                if s["type"] == "chapter":
                    for st in s["steps"]:
                        (OUT / f"preview_{k:02d}_{st['shot']}.png").write_bytes(frame(acc + st["at"] + st["dur"] * .7))
                else:
                    (OUT / f"preview_{k:02d}_headline.png").write_bytes(frame(acc + s["dur"] * .6))
                acc += s["dur"]
            print("previews written to", OUT)
            return

        n = int(total * FPS)
        out = OUT / "CyberOptix_Demo.mp4"
        ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                               "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
        for i in range(n):
            ff.stdin.write(frame(i / FPS))
            if i % (FPS * 10) == 0:
                print(f"  {i / FPS:6.1f}s / {total:.0f}s", flush=True)
        ff.stdin.close()
        ff.wait()
        print("video written to", out)
        browser.close()


if __name__ == "__main__":
    main()
