"""
Content-based laptop recommender shared by the Recommendations page and the
AI shopping assistant (verasChatbot).

It works directly on the Product table, so recommendations always link to real,
purchasable products. Scoring combines:
  * spec fit   - how well CPU tier / RAM match the target for the chosen purpose
  * keywords   - purpose-specific words in title/description/specification
  * value      - how comfortably the price sits inside the user's budget
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Q
from django.utils.translation import gettext, gettext_lazy as _

# --------------------------------------------------------------------------- #
# Purpose profiles
# --------------------------------------------------------------------------- #
PURPOSES = {
    "gaming": {
        "label": _("Gaming"),
        "icon": "fa-gamepad",
        "cpu": 8, "ram": 16,
        "keywords": ["gaming", "rtx", "gtx", "geforce", "radeon", "rog", "tuf", "nitro",
                     "predator", "legion", "omen", "victus", "msi", "alienware", "144hz", "165hz"],
        "blurb": _("High-refresh displays, dedicated GPUs and strong CPUs."),
    },
    "programming": {
        "label": _("Programming"),
        "icon": "fa-code",
        "cpu": 7, "ram": 16,
        "keywords": ["macbook", "thinkpad", "xps", "zenbook", "ssd", "16gb", "32gb", "developer"],
        "blurb": _("Plenty of RAM and fast CPUs for IDEs, containers and builds."),
    },
    "design": {
        "label": _("Design & Editing"),
        "icon": "fa-palette",
        "cpu": 8, "ram": 16,
        "keywords": ["macbook", "pro", "oled", "retina", "creator", "studio", "rtx", "4k", "color"],
        "blurb": _("Colour-accurate screens and power for creative apps."),
    },
    "business": {
        "label": _("Business"),
        "icon": "fa-briefcase",
        "cpu": 7, "ram": 16,
        "keywords": ["thinkpad", "latitude", "elitebook", "probook", "vostro", "expertbook",
                     "travelmate", "business", "fingerprint", "lightweight"],
        "blurb": _("Reliable, portable machines with good battery life."),
    },
    "office": {
        "label": _("Office & Study"),
        "icon": "fa-graduation-cap",
        "cpu": 5, "ram": 8,
        "keywords": ["ideapad", "vivobook", "aspire", "inspiron", "pavilion", "student",
                     "lightweight", "air", "chromebook"],
        "blurb": _("Affordable, light laptops for documents, browsing and classes."),
    },
    "general": {
        "label": _("Everyday Use"),
        "icon": "fa-house-laptop",
        "cpu": 5, "ram": 8,
        "keywords": ["laptop", "everyday", "home"],
        "blurb": _("Balanced all-rounders for daily tasks."),
    },
}

PURPOSE_SYNONYMS = {
    "gaming": ["game", "gaming", "gamer", "games", "esports", "valorant", "pubg", "fps"],
    "programming": ["programming", "coding", "code", "developer", "software", "dev ", "python",
                    "java", "engineering", "computer science"],
    "design": ["design", "editing", "video", "photo", "photoshop", "premiere", "creative",
               "render", "3d", "blender", "graphic", "content creation"],
    "business": ["business", "work", "corporate", "professional", "meeting", "travel"],
    "office": ["office", "student", "school", "study", "university", "college", "class",
               "word", "excel", "documents", "cheap", "budget", "affordable"],
    "general": ["general", "everyday", "home", "browsing", "netflix", "movies", "casual"],
}

# Burmese keywords (matched as substrings - Myanmar script has no spaces between words)
PURPOSE_SYNONYMS_MY = {
    "gaming": ["ဂိမ်း"],
    "programming": ["ပရိုဂရမ်", "ကုဒ်", "ဆော့ဖ်ဝဲ"],
    "design": ["ဒီဇိုင်း", "ဗီဒီယို", "ဓာတ်ပုံ", "တည်းဖြတ်"],
    "business": ["လုပ်ငန်း", "စီးပွားရေး", "အလုပ်"],
    "office": ["ကျောင်း", "ရုံး", "စာသင်", "တက္ကသိုလ်", "ဈေးသက်သာ", "ဈေးပေါ"],
    "general": ["နေ့စဉ်", "အိမ်သုံး", "ရုပ်ရှင်"],
}
_MY_DIGITS = str.maketrans("၀၁၂၃၄၅၆၇၈၉", "0123456789")
_MY_WORDS = [("ဒေါ်လာ", " usd "), ("အောက်", " under "), ("ထက်နည်း", " under "), ("ဝန်းကျင်", " around "),
             ("လောက်", " around "), ("ဘတ်ဂျက်", " budget "), ("လက်ပ်တော့", " laptop "),
             ("ဒက်စ်တော့", " desktop "), ("ရမ်", " ram ")]

BRANDS = ["apple", "lenovo", "hp", "dell", "asus", "acer", "msi"]
BRAND_ALIASES = {"macbook": "apple", "mac": "apple", "thinkpad": "lenovo", "rog": "asus",
                 "zenbook": "asus", "vivobook": "asus", "omen": "hp", "pavilion": "hp",
                 "xps": "dell", "inspiron": "dell", "alienware": "dell", "nitro": "acer",
                 "predator": "acer", "legion": "lenovo", "ideapad": "lenovo"}


# --------------------------------------------------------------------------- #
# Spec parsing helpers
# --------------------------------------------------------------------------- #
def cpu_score(cpu_text: str) -> float:
    """Map a free-text CPU description to a rough 1-10 performance tier."""
    s = (cpu_text or "").lower()
    if not s:
        return 0
    patterns = [
        (r"m[34]\s*(max|pro)", 10), (r"\bm[34]\b", 9), (r"m[12]\s*(max|pro)", 9), (r"\bm[12]\b", 8),
        (r"ultra\s*9", 10), (r"ultra\s*7", 9), (r"ultra\s*5", 7),
        (r"i9|ryzen\s*9", 9), (r"i7|ryzen\s*7", 7), (r"i5|ryzen\s*5", 5), (r"i3|ryzen\s*3", 3),
        (r"celeron|pentium|athlon|atom|mediatek", 2),
    ]
    for pat, score in patterns:
        if re.search(pat, s):
            return score
    if "xeon" in s or "threadripper" in s:
        return 9
    return 4  # unknown but present


def ram_gb(ram_text: str) -> int:
    s = (ram_text or "").lower().replace(" ", "")
    m = re.search(r"(\d+)\s*tb", s)
    if m:
        return int(m.group(1)) * 1024
    m = re.search(r"(\d+)\s*g", s) or re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 0


_PLACEHOLDERS = {"", "none", "intel", "amd", "n/a", "null"}


def product_cpu_score(p, text: str = "") -> float:
    """CPU tier from the cpu field, falling back to title/description text."""
    field_val = (p.cpu or "").strip().lower()
    if field_val not in _PLACEHOLDERS:
        score = cpu_score(field_val)
        if score != 4:
            return score
    text = text or _product_text(p)
    score = cpu_score(text)
    return score if score != 4 else (4 if field_val not in ("", "none") else 0)


def product_ram_gb(p, text: str = "") -> int:
    field_val = (p.ram or "").strip().lower()
    if field_val not in _PLACEHOLDERS:
        gb = ram_gb(field_val)
        if 2 <= gb <= 256:
            return gb
    text = text or _product_text(p)
    m = re.search(r"(\d{1,3})\s*gb\s*(?:ddr\d|lpddr\d|unified|ram|memory)", text)
    return int(m.group(1)) if m else 0


# --------------------------------------------------------------------------- #
# Query parsing (used by the chatbot)
# --------------------------------------------------------------------------- #
@dataclass
class Preferences:
    purpose: str = ""
    budget_min: float = 0
    budget_max: float = 0
    brands: list = field(default_factory=list)
    min_ram: int = 0
    cpu_hint: str = ""
    category: str = ""
    keywords: list = field(default_factory=list)

    def is_empty(self):
        return not (self.purpose or self.budget_max or self.budget_min or self.brands
                    or self.min_ram or self.cpu_hint or self.category)


_NUM = r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|lakh|lakhs)?"


def _to_number(num: str, suffix: str | None) -> float:
    value = float(num.replace(",", ""))
    if suffix == "k":
        value *= 1000
    elif suffix in ("lakh", "lakhs"):
        value *= 100000
    return value


def parse_preferences(text: str) -> Preferences:
    raw = (text or "").translate(_MY_DIGITS)
    prefs = Preferences()
    for purpose, words in PURPOSE_SYNONYMS_MY.items():
        if any(w in raw for w in words):
            prefs.purpose = purpose
            break
    for my_word, en in _MY_WORDS:
        raw = raw.replace(my_word, en)
    # Burmese puts "under/around" after the amount ("1500 ဒေါ်လာအောက်"): move it in front.
    raw = re.sub(r"(\d[\d,]*)\s*(?:usd)?\s*(under|around)", r"\2 \1", raw)
    t = " " + raw.lower() + " "

    for purpose, words in PURPOSE_SYNONYMS.items():
        if prefs.purpose:
            break
        if any(re.search(r"\b" + re.escape(w.strip()) + r"\b", t) for w in words):
            prefs.purpose = purpose

    # Budget: "between 500 and 900", "500-900", "under 1000", "below $800", "around 700"
    m = re.search(r"between\s+" + _NUM + r"\s*(?:and|to|-)\s*" + _NUM, t) or \
        re.search(_NUM + r"\s*(?:-|to)\s*" + _NUM, t)
    if m:
        lo = _to_number(m.group(1), m.group(2))
        hi = _to_number(m.group(3), m.group(4))
        if hi > lo >= 50:
            prefs.budget_min, prefs.budget_max = lo, hi
    if not prefs.budget_max:
        m = re.search(r"(?:under|below|less than|max(?:imum)?|up to|upto|within|budget(?: is| of)?|<)\s*" + _NUM, t)
        if m:
            prefs.budget_max = _to_number(m.group(1), m.group(2))
    if not prefs.budget_max:
        m = re.search(r"(?:around|about|approx(?:imately)?|~)\s*" + _NUM, t)
        if m:
            v = _to_number(m.group(1), m.group(2))
            prefs.budget_min, prefs.budget_max = v * 0.8, v * 1.15
    if not prefs.budget_min:
        m = re.search(r"(?:over|above|more than|at least|min(?:imum)?)\s*" + _NUM + r"(?!\s*gb)", t)
        if m:
            prefs.budget_min = _to_number(m.group(1), m.group(2))
    if not prefs.budget_max and not prefs.budget_min:
        m = re.search(r"\$\s*(\d[\d,]*)", t)
        if m:
            prefs.budget_max = float(m.group(1).replace(",", ""))
    if prefs.budget_max and prefs.budget_max < 50:  # e.g. "under 16" is not a budget
        prefs.budget_max = 0

    for b in BRANDS:
        if re.search(r"\b" + b + r"\b", t):
            prefs.brands.append(b)
    for alias, brand in BRAND_ALIASES.items():
        if re.search(r"\b" + alias + r"\b", t) and brand not in prefs.brands:
            prefs.brands.append(brand)

    m = re.search(r"(\d+)\s*gb\s*(?:of\s*)?ram", t) or re.search(r"(\d+)\s*gb", t)
    if m:
        prefs.min_ram = int(m.group(1))

    m = re.search(r"\b(i[3579]|ryzen\s*[3579]|m[1-4](?:\s*(?:pro|max))?|core\s*ultra\s*[579])\b", t)
    if m:
        prefs.cpu_hint = m.group(1)

    if "desktop" in t or " pc " in t:
        prefs.category = "desktop"
    elif any(w in t for w in ["accessor", "mouse", "keyboard", "headset", "bag"]):
        prefs.category = "accessories"
    elif "laptop" in t or "notebook" in t:
        prefs.category = "laptop"

    return prefs


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def _product_text(p) -> str:
    parts = [p.title, p.description or "", p.specification or "", p.cpu or "", p.ram or ""]
    if p.brand_id and p.brand:
        parts.append(p.brand.title)
    if p.category_id and p.category:
        parts.append(p.category.title)
    return " ".join(parts).lower()


def base_queryset():
    from flame.models import Product
    return (Product.objects.filter(status=True)
            .select_related("brand", "category", "shop"))


def score_products(prefs: Preferences, limit: int = 6, queryset=None):
    """Return a list of (product, score 0-100, reasons[]) sorted best first."""
    qs = queryset if queryset is not None else base_queryset()

    if prefs.category:
        cat = {"laptop": "Laptop", "desktop": "Desktop", "accessories": "Accessor"}[prefs.category]
        filtered = qs.filter(category__title__icontains=cat)
        if filtered.exists():
            qs = filtered
    elif prefs.purpose:
        # Purpose-driven searches are about computers, not accessories.
        filtered = qs.exclude(category__title__icontains="Accessor")
        if filtered.exists():
            qs = filtered

    if prefs.brands:
        q = Q()
        for b in prefs.brands:
            q |= Q(brand__title__iexact=b) | Q(title__icontains=b)
        filtered = qs.filter(q)
        if filtered.exists():
            qs = filtered

    if prefs.budget_max:
        filtered = qs.filter(price__lte=Decimal(str(prefs.budget_max * 1.05)))
        if filtered.exists():
            qs = filtered
    if prefs.budget_min:
        filtered = qs.filter(price__gte=Decimal(str(prefs.budget_min * 0.95)))
        if filtered.exists():
            qs = filtered

    profile = PURPOSES.get(prefs.purpose or "general")
    target_cpu = profile["cpu"]
    target_ram = max(profile["ram"], prefs.min_ram or 0)
    if prefs.cpu_hint:
        target_cpu = max(target_cpu, cpu_score(prefs.cpu_hint))

    results = []
    for p in qs[:500]:
        text = _product_text(p)
        c, r = product_cpu_score(p, text), product_ram_gb(p, text)
        cpu_fit = min(c / target_cpu, 1.0) if target_cpu else 1.0
        ram_fit = min(r / target_ram, 1.0) if target_ram and r else (0.4 if target_ram else 1.0)
        spec_fit = 0.5 * cpu_fit + 0.5 * ram_fit

        kw_hits = [k for k in profile["keywords"] if k in text]
        kw_score = min(len(kw_hits) / 2.0, 1.0)

        price = float(p.price or 0)
        if prefs.budget_max:
            # closer to (but under) the budget = better use of money
            value = 1.0 - abs(prefs.budget_max * 0.85 - price) / max(prefs.budget_max, 1)
            value = max(0.0, min(value, 1.0))
        elif prefs.purpose in ("office", "general"):
            value = 1.0 / (1.0 + price / 1000.0)  # cheaper is better for basic use
        else:
            value = 0.5

        score = 0.6 * spec_fit + 0.25 * kw_score + 0.15 * value
        if not p.in_stock:
            score *= 0.85
        if p.featured:
            score += 0.02

        # Reasons are built with gettext at request time so they follow the site language.
        reasons = []
        if c:
            known_cpu = (p.cpu or "").strip().lower() not in _PLACEHOLDERS
            cpu_label = p.cpu if known_cpu else gettext("Capable")
            reasons.append(gettext("%(cpu)s CPU meets the target") % {"cpu": cpu_label} if cpu_fit >= 1
                           else gettext("%(cpu)s CPU") % {"cpu": cpu_label})
        if r:
            reasons.append(gettext("%(gb)s GB RAM meets the target") % {"gb": r} if ram_fit >= 1
                           else gettext("%(gb)s GB RAM") % {"gb": r})
        if kw_hits:
            reasons.append(gettext("Made for %(use)s: %(words)s") % {
                "use": str(profile["label"]).lower(), "words": ", ".join(kw_hits[:3])})
        if prefs.budget_max and price <= prefs.budget_max:
            reasons.append(gettext("Within budget ($%(price)s)") % {"price": f"{price:,.0f}"})
        results.append((p, round(min(score, 1.0) * 100), reasons))

    results.sort(key=lambda x: (x[1], -float(x[0].price or 0)), reverse=True)
    return results[:limit]


def product_to_dict(p, score=None, reasons=None, request=None):
    from django.urls import reverse
    try:
        url = reverse("flame:product-detail", args=[p.p_id])
    except Exception:
        url = "#"
    try:
        image = p.image.url if p.image else ""
    except Exception:
        image = ""
    return {
        "id": p.id,
        "pid": p.p_id,
        "title": p.title,
        "price": float(p.price or 0),
        "old_price": float(p.old_price or 0),
        "cpu": p.cpu,
        "ram": p.ram,
        "brand": p.brand.title if p.brand_id and p.brand else "",
        "shop": p.shop.title if p.shop_id and p.shop else "",
        "in_stock": p.in_stock,
        "image": image,
        "url": url,
        "score": score,
        "reasons": reasons or [],
    }
