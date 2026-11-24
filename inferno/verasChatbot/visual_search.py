"""
Image search for Veras: find catalogue products that look like an uploaded photo.

Uses OpenAI's CLIP model (ViT-B-32, via open_clip) running locally on the CPU - free, no
API key. Every product image is embedded once and cached in
inferno/.cache/veras_clip_index.npz; the cache is rebuilt automatically when products change.
CLIP also scores the photo against a few text labels (brand / device type) so Veras can
say what it thinks the photo shows.
"""
import logging
import os
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

MODEL_NAME, PRETRAINED = "ViT-B-32", "laion2b_s34b_b79k"
CACHE = os.path.join(settings.BASE_DIR, ".cache", "veras_clip_index.npz")
_lock = threading.Lock()
_state = {}

LABELS = {
    "brand": ["an Apple MacBook laptop", "an ASUS laptop", "a Dell laptop", "an HP laptop",
              "a Lenovo laptop", "an Acer laptop", "an MSI laptop"],
    "type": ["a gaming laptop with RGB lighting", "a thin and light ultrabook", "a business laptop",
             "a desktop PC tower", "a computer monitor", "a keyboard or mouse accessory",
             "a 2-in-1 convertible laptop"],
}
BRAND_NAMES = ["Apple", "ASUS", "Dell", "HP", "Lenovo", "Acer", "MSI"]


def available() -> bool:
    try:
        import open_clip  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def _model():
    if "model" not in _state:
        import open_clip
        import torch
        torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
        model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
        model.eval()
        _state.update(model=model, preprocess=preprocess, tokenizer=open_clip.get_tokenizer(MODEL_NAME))
    return _state["model"], _state["preprocess"], _state["tokenizer"]


def _embed_images(pil_images):
    import torch
    model, preprocess, _ = _model()
    with torch.no_grad():
        batch = torch.stack([preprocess(im.convert("RGB")) for im in pil_images])
        feats = model.encode_image(batch)
        feats /= feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy()


def _embed_texts(texts):
    import torch
    model, _, tokenizer = _model()
    with torch.no_grad():
        feats = model.encode_text(tokenizer(texts))
        feats /= feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy()


def _signature(products):
    return f"{len(products)}:{max((p.id for p in products), default=0)}:" \
           f"{max((p.updated.timestamp() if p.updated else 0 for p in products), default=0):.0f}"


def _index():
    """(product_ids, embeddings) for every product image, cached on disk."""
    import numpy as np
    from PIL import Image
    from flame.models import Product

    products = list(Product.objects.filter(status=True).only("id", "image", "updated"))
    sig = _signature(products)
    if _state.get("sig") == sig:
        return _state["ids"], _state["emb"]
    with _lock:
        if _state.get("sig") == sig:
            return _state["ids"], _state["emb"]
        if os.path.exists(CACHE):
            data = np.load(CACHE, allow_pickle=False)
            if str(data["sig"]) == sig:
                _state.update(sig=sig, ids=data["ids"].tolist(), emb=data["emb"])
                return _state["ids"], _state["emb"]
        ids, images = [], []
        for p in products:
            try:
                images.append(Image.open(p.image.path))
                ids.append(p.id)
            except Exception:
                continue
        embs = [_embed_images(images[i:i + 32]) for i in range(0, len(images), 32)]
        emb = np.concatenate(embs) if embs else np.zeros((0, 512), dtype="float32")
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        np.savez(CACHE, sig=sig, ids=np.array(ids), emb=emb)
        _state.update(sig=sig, ids=ids, emb=emb)
        logger.info("Veras image index built for %d products", len(ids))
        return ids, emb


def describe(pil_image):
    """Best brand and device-type label for the photo, e.g. ('ASUS', 'a gaming laptop ...')."""
    import numpy as np
    q = _embed_images([pil_image])[0]
    out = {}
    for key, labels in LABELS.items():
        sims = _embed_texts(labels) @ q
        i = int(np.argmax(sims))
        out[key] = (labels[i], float(sims[i]))
    brand = BRAND_NAMES[LABELS["brand"].index(out["brand"][0])]
    return brand, out["type"][0]


def search(pil_image, limit=4):
    """Return [(product, similarity 0-100), ...] most visually similar to the photo."""
    import numpy as np
    from flame.models import Product

    ids, emb = _index()
    if not len(ids):
        return []
    q = _embed_images([pil_image])[0]
    sims = emb @ q
    order = np.argsort(-sims)[:limit * 3]
    by_id = Product.objects.in_bulk([ids[i] for i in order])
    results, seen_titles = [], set()
    for i in order:
        p = by_id.get(ids[i])
        if not p or p.title in seen_titles:
            continue
        seen_titles.add(p.title)
        results.append((p, int(round(float(sims[i]) * 100))))
        if len(results) == limit:
            break
    return results
