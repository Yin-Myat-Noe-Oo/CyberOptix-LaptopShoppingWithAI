# CyberOptix – Demo Video Script (4 min 05 s)

A screen-recorded walkthrough of **CyberOptix – AI-Powered Laptop Shopping**, from sign-in to the
receipt, ending with the AI features. A finished, captioned version is rendered by
`demo/render.py` → `demo/out/CyberOptix_Demo.mp4`. Use this script to record your own narrated
version or to narrate over the rendered one.

---

## 1. Reference video – what we copied

The reference ("Vibmo", 2 min 47 s, 1080p, **no audio track**) is a calm motion-graphics walkthrough:

| Element | Reference | CyberOptix video |
|---|---|---|
| Canvas | Off-white page, lots of space | Same (`#f4f5f0`) |
| Opening | Problem headline → logo → "It all starts at …" | "Choosing a laptop is *hard*." → logo → feature grid → home page |
| Chapters | `01 Start a gathering` + step pills (active pill in teal) | `01 Sign in` … `10 Veras AI chatbot` with step pills |
| Screens | Real screenshots in rounded frames | Real CyberOptix screens in a browser frame |
| Focus | Teal highlight box + orange callout label | Same, positioned from the real button coordinates |
| Progress | Vertical chapter list on the right | Same – 10 chapters |
| Text | One caption sentence at the bottom; tiny honesty notes | Same – notes explain demo limits honestly |
| Ending | Logo, tagline, URL | Logo, "Your next laptop, *picked by AI*." |
| Pace | ~5–6 s per step, gentle push-in zoom | 4.5–9 s per step, slow push-in, soft cross-fades |

---

## 2. Feature verification (checked against the code and the running site)

| Feature | Status | Notes |
|---|---|---|
| Email / password sign-in | ✅ Works | New sign-ups must verify email first (needs Gmail SMTP in `.env`). Demo uses a verified demo account. |
| Google sign-in ("Continue with Google") | ⚠️ Needs config | Custom OAuth 2.0 flow (`userauths/services.py`). Needs `GOOGLE_OAUTH_CLIENT_ID/SECRET` in `inferno/.env` and redirect URI `http://127.0.0.1:8000/en/user/google/callback/` in Google Cloud Console. Only @gmail.com accounts are accepted. |
| Product list, detail, gallery, specs tab, reviews, related | ✅ Works | |
| Filters: category, brand (sidebar), shop chips, price "Apply", search | ✅ Works | Type a max price before **Apply** (the box starts at the lowest price). |
| Myanmar / English switch | ✅ Works | Whole UI translated (2 061 strings). Product names/specs come from the database in English. |
| Cart: add, quantity, remove, per-shop totals | ✅ Works | Add to Cart is on the product page (cards show "View"). |
| Wishlist: heart, page, add to cart, remove | ✅ Works | |
| Checkout + **Cash on Delivery** | ✅ Works | Myanmar address data loaded (`populate_myanmar_locations`). Record checkout in **English** (Myanmar mode sends the shipping fee in MMK). |
| KBZPay (demo mock) | ⚠️ Partly | Server bugs fixed; the mock success page has no link back to the shop – not shown in the video. |
| PayPal / Stripe | ⚠️ Needs accounts | PayPal sandbox + public callback URL; Stripe test keys. Shown only as buttons. |
| Invoice page, Print, Download PDF | ✅ Works | PDF is generated in the browser. |
| My Orders `/en/orders/` | ✅ Works | Avoid Profile → Order History → **View** (known 404). |
| AI Picks (recommendations) | ✅ Works | Content-based ranking: CPU tier, RAM, purpose keywords, value for budget. It does **not** learn from behaviour on this page. |
| Veras chat widget (every page) | ✅ Works | Free AI (gpt-oss-20b via Pollinations, no key). Free tier: **1 reply / 45 s** – otherwise the built-in engine answers. Product cards come from the database. |
| Veras AI Studio – **Gradio** (text / image / voice) | ✅ Works | Gradio app started by Django, embedded at `/en/chat/` → *Voice & Image Studio*. Image search = CLIP (local); voice = Whisper (local). |

---

## 3. Scene-by-scene script

Narration speed ≈ 150 words/min. Times are cumulative.

### Scene 1 – Problem · 0:00–0:06 (6 s)
- **On screen:** Headline "Choosing a laptop is *hard*."
- **Actions:** none (title card).
- **Voice-over:** "Buying a laptop in Myanmar usually means visiting several shops and comparing confusing specs."
- **Caption:** Hundreds of models, confusing specs, and shops all over Myanmar.
- **Transition:** fade to logo.

### Scene 2 – Logo · 0:06–0:12 (6 s)
- **On screen:** CyberOptix logo, tagline "AI-powered laptop shopping for Myanmar".
- **Voice-over:** "So I built CyberOptix – an AI-powered laptop shopping website."
- **Caption:** CyberOptix brings the shops, the specs and an AI shopping assistant into one website.
- **Transition:** fade.

### Scene 3 – Features · 0:12–0:24 (12 s)
- **On screen:** Eight feature cards appear one by one; the two AI cards are purple.
- **Voice-over:** "It covers the full shopping journey – sign-in, browsing, search and filters, a Myanmar and English interface, cart and wishlist, checkout with a receipt – plus two AI features: personalised AI Picks and the Veras chatbot, which understands text, images and voice."
- **Caption:** Here is what the project does – every screen in this video is the real, running website.
- **Transition:** fade.

### Scene 4 – Home page · 0:24–0:30 (6 s)
- **On screen:** `127.0.0.1:8000/en/` – hero with the rotating 3D laptop.
- **Actions:** (live) drag the 3D laptop a little to rotate it.
- **Voice-over:** "This is the home page. You can search right away, or even spin the 3D laptop."
- **Caption:** The home page: a search bar, quick AI shortcuts, and an interactive 3D laptop you can rotate.
- **Transition:** cut to chapter 01.

### Chapter 01 – Sign in · 0:30–0:47 (17 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Google | 7 s | User icon → **Sign In** (`/en/user/sign-in/`). Point at **Continue with Google**. | "Customers can sign in with their Google account – I implemented the Google OAuth 2.0 flow myself – or…" | *Continue with Google* · note: needs Google OAuth client ID; demo uses email account |
| Email | 5 s | Type email + password → **Login**. | "…with an email and password. New accounts verify their email first." | *Or use email & password* |
| Signed in | 5 s | Toast "Welcome back"; hover the user icon. | "Now I'm signed in, and the account menu shows my profile." | *Signed in* |

> To record real Google sign-in: add the OAuth credentials (section 2), restart the server, click **Continue with Google**, pick the account, and you return to the home page signed in.

### Chapter 02 – Browse laptops · 0:47–1:06 (19 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Catalog | 6 s | Navbar **Products** → scroll to the grid. | "The catalog has 193 products from four partner shops, priced in dollars and Kyat." | *193 products · 4 shops* |
| Details | 7 s | Open **ASUS ROG Strix G17** (Citicom) → click a thumbnail. | "Each product has a photo gallery, the price and discount, and a description." | *Photo gallery* |
| Specs | 6 s | Click the **Additional Info** tab. | "Additional Info lists the full specs, which makes comparing models easy." | *Full specifications* |

### Chapter 03 – Search and filter · 1:06–1:27 (21 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Category | 5.5 s | Click ☰ (top-left) → side menu. | "The side menu filters by category and brand." | *Categories & brands* |
| Brand | 5 s | Click **Asus**. | "Here are only the Asus products." | *Brand: Asus* |
| Price | 5.5 s | Products → type **1000** in Price → **Apply**. | "The price filter keeps everything under a thousand dollars." | *Up to $1,000* |
| Search | 5 s | Home search → type **macbook** → **Search**. | "And search finds a model by name." | *Search: "macbook"* |

### Chapter 04 – Myanmar and English · 1:27–1:41 (14 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Switch | 4.5 s | Click the flag toggle in the navbar. | "One click switches the site to Myanmar…" | *One-click language switch* |
| Myanmar | 5 s | Home page in Myanmar. | "…and everything is translated, not just the menu." | *Full Myanmar interface* |
| Products | 4.5 s | Open the product page in Myanmar, then toggle back to English. | "Product pages and the assistant follow the language too." | *Product pages too* |

### Chapter 05 – Shopping cart · 1:41–1:59 (18 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Add | 6 s | Product page → **Add to Cart** (button turns "Added to cart", bag count +1). | "I'll add the ROG Strix to my cart." | *Add to Cart* |
| Cart | 6 s | Click the bag icon → `/en/shop-cart/`. | "The cart groups items by shop with price, quantity and subtotal." | *Change quantity* |
| Quantity | 6 s | Change a quantity to **2** (trash icon removes an item). | "Changing the quantity updates the totals instantly." | *Totals update instantly* |

### Chapter 06 – Wishlist · 1:59–2:11 (12 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Save | 5.5 s | Products → click the ♥ on two laptops. | "The heart saves laptops for later." | *Save for later* |
| Wishlist | 6.5 s | Navbar ♥ → `/en/wishlist/` → point at **Add to cart** / trash. | "From the wishlist I can move one to the cart or remove it." | *Add to cart or remove* |

### Chapter 07 – Checkout · 2:11–2:35 (23.5 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Details | 6 s | Cart → **Checkout Citicom →** → enter mobile. | "At checkout I confirm my name and mobile number." | *Name & mobile* |
| Address | 6 s | State **Yangon** → City → Street "No. 12, Pyay Road" → Landmark "Hledan Center". | "The address uses Myanmar states and cities, and shipping is added automatically." | *Myanmar address & shipping* |
| Payment | 6 s | Keep **Cash on Delivery** selected. | "I'll pay with Cash on Delivery." | *Cash on Delivery* · note: PayPal/Stripe/KBZPay need provider accounts |
| Confirm | 5.5 s | Click **Confirm Cash on Delivery Order**. | "Confirm – and the order is placed." | *Confirm order* |

### Chapter 08 – Order confirmation · 2:35–2:53 (18 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Invoice | 6.5 s | Invoice page `/en/payment-completed/<shop>/`. | "I immediately get an invoice with the order number, address and payment method." | *Invoice generated* |
| PDF | 5.5 s | Scroll to items/total → **Download PDF** (or **Print Invoice**). | "It can be printed or saved as a PDF." | *Print or download PDF* |
| Orders | 6 s | Address bar → `/en/orders/`. | "And every order is kept in My Orders." | *Order history* |

### Chapter 09 – AI Picks · 2:53–3:09 (16 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Use & budget | 7 s | Navbar **AI Picks** → slide budget to **$1,500**. | "AI Picks asks what the laptop is for and my budget." | *Pick a use and a budget* |
| Ranking | 9 s | Click **Gaming** → results with match %. | "It scores every laptop on CPU, RAM, purpose and value for money, and shows the best matches first." | *Ranked by fit* |

### Chapter 10 – Veras AI chatbot (Gradio) · 3:09–3:58 (49 s)
| Step | Time | On screen / clicks | Voice-over | Caption · callout |
|---|---|---|---|---|
| Chat | 8 s | Click the robot button → type "I need a laptop for programming and gaming under $1500. What do you suggest?" → Enter. | "Veras is an AI assistant on every page. I ask in plain language, and it recommends real products from our database." | *Ask in plain language* |
| Gradio | 6.5 s | Open `/en/chat/` → tab **Voice & Image Studio**. | "The Veras AI Studio is built with Gradio and embedded in the site." | *Built with Gradio* |
| Text | 8 s | Text tab → "What is the difference between Intel Core i5 and i7 for programming?" → **Send**. | "It explains specs – like i5 versus i7 – and links matching laptops." | *Text: explains specs* |
| Image (upload) | 5 s | **📷 Image** tab → upload a laptop photo → "Find laptops like this one". | "I can also search with a photo instead of typing a name…" | *Upload a laptop photo* |
| Image (result) | 8 s | **Analyze image**. | "…it recognises a gaming laptop, most likely ASUS, and finds the closest products in the catalogue." | *Finds look-alike products* |
| Voice (upload) | 5 s | **🎙️ Voice** tab → record (mic) or upload a question. | "Or I can just ask with my voice." | *Speak a question* |
| Voice (result) | 8.5 s | **Transcribe & ask**. | "Whisper turns my speech into text, and the AI answers with a recommendation." | *Transcribed, then answered* |

> ⏱️ The free AI allows **one reply every 45 seconds**. When recording live, pause about a minute between AI questions (cut the waits in editing).

### Scene – Outro · 3:58–4:05 (7.5 s)
- **On screen:** "Your next laptop, *picked by AI*." + logo + "Django · Bilingual · Gradio AI chatbot".
- **Voice-over:** "That's CyberOptix – a complete laptop store with AI built in. Thanks for watching."
- **Caption:** CyberOptix – a complete laptop e-commerce website with AI built in. Thank you for watching.

**Total: 4 min 05 s** (limit 5:00).

---

## 4. Recording checklist

Before recording
- [ ] `cd CyberOptix-LaptopShoppingWithAI\inferno` and start the server: `..\.venv\Scripts\python.exe manage.py runserver`
- [ ] Open `http://127.0.0.1:8000/en/chat/` once so the Gradio studio starts (port 7860) and its first AI call warms up.
- [ ] Sign out; clear the cart and wishlist; browser zoom 100 %, window 1440×900 or larger; dark theme.
- [ ] Have ready: demo login (`demo/.demo_credentials`), `demo/assets/laptop_photo.jpg`, `demo/assets/voice_question.wav` (or speak live).
- [ ] Hide bookmarks bar, notifications, other tabs. Use a recorder at 1080p 30 fps (OBS / Xbox Game Bar).

While recording
- [ ] Move the mouse slowly; pause ~1 s on each highlighted control before clicking.
- [ ] Checkout in **English**; choose **Yangon** for the address.
- [ ] Wait ~1 minute between AI questions (free tier).
- [ ] Don't use Profile → Order History → View (404); use `/en/orders/`.

After recording
- [ ] Trim waits; keep each step 4–9 s; total under 5 min.
- [ ] Add captions/callouts as in section 3, or narrate over `demo/out/CyberOptix_Demo.mp4`.

---

## 5. Editing & transitions

- **Cross-fade 0.35–0.45 s** between steps; **hard cut** at each new chapter title (as in the reference).
- **Slow push-in** (2–3 % zoom) on every screenshot keeps still screens alive.
- **Highlight → callout → click**: show the teal box ~0.5 s after the screen appears, the orange label with it, then the cursor click ring.
- Keep the **chapter timeline** on the right so viewers always know where they are.
- Use one sentence of caption per step; keep honesty notes small and grey.
- Optional music: a quiet, royalty-free ambient track at −22 dB under the voice-over.

## 6. Rebuilding the video

```powershell
cd C:\Users\User\Downloads\cyberoptix\CyberOptix-LaptopShoppingWithAI
.venv\Scripts\python.exe demo\capture.py        # re-capture all screens (server must be running)
.venv\Scripts\python.exe demo\render.py         # -> demo\out\CyberOptix_Demo.mp4
```
