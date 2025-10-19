from .models import Product, Shop, Brand, Category
from sentence_transformers import SentenceTransformer
import numpy as np
import os

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def prepare_training_data():
    product_texts, product_ids = [], []
    shop_texts, shop_ids = [], []
    brand_texts, brand_ids = [], []
    category_texts, category_ids = [], []

    # Products
    for p in Product.objects.select_related("shop", "brand", "category"):
        text = f"{p.title}. {p.description}. CPU: {p.cpu}, RAM: {p.ram}. "
        if p.shop:
            text += f"Sold by {p.shop.title}. "
        if p.brand:
            text += f"Brand: {p.brand.title}. "
        if p.category:
            text += f"Category: {p.category.title}. "
        product_texts.append(text)
        product_ids.append(p.id)

    # Shops
    for s in Shop.objects.all():
        shop_texts.append(f"{s.title}. {s.description}. Located at {s.address}.")
        shop_ids.append(s.id)

    # Brands
    for b in Brand.objects.all():
        brand_texts.append(b.title)
        brand_ids.append(b.id)

    # Categories
    for c in Category.objects.all():
        category_texts.append(c.title)
        category_ids.append(c.id)

    return {
        "product_texts": product_texts,
        "product_ids": product_ids,
        "shop_texts": shop_texts,
        "shop_ids": shop_ids,
        "brand_texts": brand_texts,
        "brand_ids": brand_ids,
        "category_texts": category_texts,
        "category_ids": category_ids,
    }
