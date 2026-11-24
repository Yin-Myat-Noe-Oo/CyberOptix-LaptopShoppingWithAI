"""
Veras - CyberOptix AI shopping assistant.

Pipeline for every message:
  1. Parse shopping preferences (purpose, budget, brand, RAM, CPU - English or
     Burmese) and rank real products with flame.recommender, or look products up
     by name.
  2. Merge preferences with earlier turns, so follow-ups like "cheaper?" or
     "what about Dell?" keep the context.
  3. The reply is written by the Veras AI (OpenAI, see verasChatbot/ai.py),
     grounded on the ranked products and in the site language. If the AI is
     not configured or fails, a translated template reply is used.
     Product cards always come from the database, never from the model.
"""
import logging
import re

from django.db.models import Q
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from flame.recommender import (
    PURPOSES, Preferences, parse_preferences, product_to_dict, score_products,
)

from . import ai

logger = logging.getLogger(__name__)


def suggestions():
    return [
        _("Gaming laptop under $1500"),
        _("Laptop for a student under $700"),
        _("Best for programming with 16GB RAM"),
        _("Show me Apple MacBooks"),
        _("What payment methods do you accept?"),
    ]


def follow_ups(has_budget=True):
    items = [_("Show me cheaper options"), _("Something more powerful")]
    if not has_budget:
        items.insert(0, _("My budget is $1000"))
    return items


# (pattern, answer). Lazy translations resolve in the request's language.
FAQ = [
    (r"\b(hi|hello|hey|mingalar|mingalaba|good (morning|afternoon|evening))\b|မင်္ဂလာ",
     gettext_lazy("Hi! I'm **Veras**, the CyberOptix AI shopping assistant. Tell me what you'll use your "
     "laptop for and your budget, and I'll pick the best matches from our shops.")),
    (r"\b(thank|thanks|thx|cheers)\b|ကျေးဇူး",
     gettext_lazy("You're welcome! Anything else I can help you find?")),
    (r"\b(pay|payment|kbz|paypal|stripe|card|cash on delivery|cod)\b|ငွေပေးချေ",
     gettext_lazy("We accept **PayPal**, **Stripe** (credit/debit cards), **KBZPay**, and **Cash on Delivery**. "
     "You choose the method at checkout.")),
    (r"\b(return|refund|exchange|warranty)\b|ပြန်အမ်း|လဲလှယ်",
     gettext_lazy("Returns and exchanges must be requested **within 7 days of delivery**. Approved refunds are "
     "processed in **3-5 business days** to your original payment method (return shipping fees "
     "are not refunded). See the Return Policy page for details.")),
    (r"\b(ship|shipping|deliver|delivery)\b|ပို့ဆောင်",
     gettext_lazy("We deliver across Myanmar. Shipping fees are calculated at checkout from your state, city "
     "and township, and you can also choose in-shop pickup.")),
    (r"\b(contact|phone|email|support|call)\b|ဆက်သွယ်",
     gettext_lazy("You can reach CyberOptix support at **+959 00090999** or **cyberoptix@gmail.com**.")),
    (r"\b(track|order status|my order|where is my order)\b|အော်ဒါ",
     gettext_lazy("Sign in and open **Profile -> Orders** to track an order, see its status, or request a "
     "cancellation/return.")),
    (r"\b(who are you|what can you do|help)\b|ကူညီ",
     gettext_lazy("I can recommend laptops by purpose (gaming, programming, design, business, study), budget, "
     "brand, RAM or CPU, compare options, and answer questions about payment, shipping and returns.")),
]

FOLLOW_UP_CHEAPER = re.compile(r"\b(cheaper|less expensive|lower price|budget option)\b|ပိုသက်သာ|ဈေးပိုပေါ")
FOLLOW_UP_BETTER = re.compile(r"\b(better|more powerful|faster|higher end|premium)\b|ပိုကောင်း|ပိုအားကောင်း")


def _merge(previous: dict | None, current: Preferences) -> Preferences:
    """Carry context from earlier turns into short follow-up questions."""
    if not previous:
        return current
    known = {"purpose", "budget_min", "budget_max", "min_ram", "cpu_hint", "category"}
    merged = Preferences(**{k: v for k, v in previous.items() if k in known and v is not None})
    merged.brands = list(previous.get("brands") or [])
    for field in known:
        val = getattr(current, field)
        if val:
            setattr(merged, field, val)
    if current.brands:
        merged.brands = current.brands
    return merged


def _shops_reply():
    from flame.models import Shop
    shops = list(Shop.objects.all()[:10])
    if not shops:
        return _("We don't have any partner shops listed yet.")
    lines = [f"- **{s.title}** - {s.address}" for s in shops]
    return _("Here are our partner shops:") + "\n" + "\n".join(lines)


STOPWORDS = {"show", "me", "the", "a", "an", "laptop", "laptops", "want", "need", "any", "some",
             "for", "with", "and", "or", "of", "do", "you", "have", "find", "get", "buy", "looking",
             "please", "can", "i", "is", "are", "what", "which", "best", "good", "new", "price",
             "pc", "computer", "notebook", "recommend", "something", "one", "about", "how"}


def _keyword_search(text: str, limit=6):
    """Rank products by how many query words appear in their title."""
    from flame.models import Product
    words = [w.rstrip("s") if len(w) > 4 else w
             for w in re.findall(r"[a-z0-9]+", text.lower())
             if w not in STOPWORDS and len(w) > 1 and not w.isdigit()]
    if not words:
        return []
    q = Q()
    for w in words:
        q |= Q(title__icontains=w)
    candidates = Product.objects.filter(status=True).filter(q).select_related("brand", "shop", "category")[:200]
    scored = []
    for p in candidates:
        title = p.title.lower()
        hits = sum(1 for w in words if w in title)
        scored.append((hits, p.in_stock, -float(p.price or 0), p))
    if not scored:
        return []
    best = max(s[0] for s in scored)
    need = best if len(words) > 1 else 1  # every word must match a specific product name
    scored = [s for s in scored if s[0] >= need]
    scored.sort(key=lambda s: (s[0], s[1], s[2]), reverse=True)
    return [s[3] for s in scored[:limit]]


def _describe(prefs: Preferences) -> str:
    bits = []
    if prefs.purpose:
        bits.append(_(PURPOSES[prefs.purpose]["label"]))
    if prefs.brands:
        bits.append("/".join(b.title() if b != "hp" else "HP" for b in prefs.brands))
    if prefs.min_ram:
        bits.append(f"{prefs.min_ram}GB+ RAM")
    if prefs.cpu_hint:
        bits.append(prefs.cpu_hint.upper())
    if prefs.budget_min and prefs.budget_max:
        bits.append(f"${prefs.budget_min:,.0f}-${prefs.budget_max:,.0f}")
    elif prefs.budget_max:
        bits.append(_("under $%(amount)s") % {"amount": f"{prefs.budget_max:,.0f}"})
    elif prefs.budget_min:
        bits.append(_("over $%(amount)s") % {"amount": f"{prefs.budget_min:,.0f}"})
    return ", ".join(bits)


def _template_reply(prefs: Preferences, products: list) -> str:
    if not products:
        return _("I couldn't find a product matching that yet. Try widening your budget or "
                 "telling me the main use (gaming, study, programming, design, business).")
    desc = _describe(prefs)
    top = products[0]
    head = (_("Here are my top picks for %(desc)s.") % {"desc": desc}) if desc else _("Here are my top picks.")
    best = " " + _("**%(title)s** ($%(price)s) is the strongest match.") % {
        "title": top["title"], "price": f"{top['price']:,.0f}"}
    tip = ""
    if not prefs.budget_max:
        tip = " " + _("Tell me your budget and I'll narrow it down.")
    elif not prefs.purpose:
        tip = " " + _("What will you mainly use it for? I can fine-tune the ranking.")
    return head + best + tip


def respond(message: str, history: list | None = None, context: dict | None = None,
            lang: str = "en") -> dict:
    history = history or []
    text = (message or "").strip()
    if not text:
        return {"reply": _("Please type a message."), "products": [], "suggestions": suggestions(),
                "context": context or {}}
    lower = text.lower()
    prefs = parse_preferences(text)
    is_follow_up = bool(FOLLOW_UP_CHEAPER.search(lower) or FOLLOW_UP_BETTER.search(lower))

    # Store/policy intents (only when the message isn't a product search).
    if prefs.is_empty() and not is_follow_up:
        if re.search(r"\b(shop|shops|store|stores|branch)\b|ဆိုင်", lower) and not re.search(r"laptop|desktop|လက်ပ်တော့", lower):
            return {"reply": _shops_reply(), "products": [], "suggestions": suggestions()[:3],
                    "context": context or {}}
        for pattern, answer in FAQ:
            if re.search(pattern, lower):
                reply = ai.chat_reply(text, history, [], lang) or str(answer)
                return {"reply": reply, "products": [], "suggestions": suggestions()[:4],
                        "context": context or {}}

    raw = prefs
    fresh_request = re.match(r"^(show|i want|i need|i'm looking|im looking|looking for|find|recommend|suggest)", lower)
    refinement = re.match(r"^(what about|how about|and |also|with |under|below|cheaper|more|less|only|"
                          r"maybe|instead|but|any |around|my budget|budget)", lower)
    if context and (is_follow_up or refinement or
                    (not fresh_request and not raw.purpose and not raw.is_empty())):
        prefs = _merge(context, prefs)

    # Product-name lookups ("rog strix", "thinkpad", "Apple MacBooks") answered from titles first.
    if not raw.purpose and not raw.budget_max and not raw.budget_min and not is_follow_up \
            and not refinement:
        found = _keyword_search(text, limit=4)
        if found:
            products = [product_to_dict(p) for p in found]
            reply = ai.chat_reply(text, history, products, lang) or (
                _("Here's what I found for \"%(q)s\". Tell me your budget or main use and I can rank "
                  "them for you.") % {"q": text})
            new_context = {"brands": prefs.brands, "category": prefs.category,
                           "_last_prices": [p["price"] for p in products]}
            return {"reply": reply, "products": products,
                    "suggestions": follow_ups() + [_("Gaming laptop under $1500")],
                    "context": new_context}

    previous_prices = (context or {}).get("_last_prices") or []
    if FOLLOW_UP_CHEAPER.search(lower) and previous_prices:
        prefs.budget_max = min(previous_prices) * 0.95
        prefs.budget_min = 0
    elif FOLLOW_UP_BETTER.search(lower) and previous_prices:
        prefs.budget_min = max(previous_prices) * 1.06  # strictly above the last picks
        prefs.budget_max = 0

    if prefs.is_empty():
        # General question (tech help, comparisons...): the AI answers on its own.
        reply = ai.chat_reply(text, history, [], lang) or _(
            "I'm Veras, your laptop shopping assistant. Tell me what you'll use it for "
            "and your budget - e.g. \"gaming laptop under $1200\" - and I'll recommend "
            "the best matches.")
        return {"reply": reply, "products": [], "suggestions": suggestions(),
                "context": context or {}}

    ranked = score_products(prefs, limit=4)
    products = [product_to_dict(p, s, r) for p, s, r in ranked]
    reply = ai.chat_reply(text, history, products, lang) or _template_reply(prefs, products)

    new_context = {
        "purpose": prefs.purpose, "budget_min": prefs.budget_min, "budget_max": prefs.budget_max,
        "brands": prefs.brands, "min_ram": prefs.min_ram, "cpu_hint": prefs.cpu_hint,
        "category": prefs.category, "keywords": [],
        "_last_prices": [p["price"] for p in products],
    }
    return {"reply": reply, "products": products, "suggestions": follow_ups(bool(prefs.budget_max)),
            "context": new_context}
