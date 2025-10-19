# shop/utils.py
from .models import Product,Shop

def get_all_product_text():
    """
    Returns a list of product strings for AI retrieval
    """
    products = Product.objects.all()
    product_texts = []
    for p in products:
        product_texts.append(
            f"Name: {p.title}\nDescription: {p.description}\nPrice: ${p.price}\nCategory: {p.category or 'N/A'}\nShop: {p.shop}"
        )
    return product_texts
def get_all_shop_text():
    shops = Shop.objects.all()
    shop_texts = []
    for s in shops:
        shop_texts.append(
            f"Name: {s.title}\nDescription: {s.description}\nContact: {s.contact}\nshop Address: {s.address or 'N/A'}"
        )
    return shop_texts