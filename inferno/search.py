from sklearn.metrics.pairwise import cosine_similarity
from embeddings import (
    embedding_model,
    product_texts,
    product_embeddings,
    shop_texts,
    shop_embeddings,
)

def search_products(user_query, top_k=5):
    """
    Semantic search for products.
    """
    query_vec = embedding_model.encode([user_query])
    sims = cosine_similarity(query_vec, product_embeddings)[0]
    top_indices = sims.argsort()[-top_k:][::-1]
    return [product_texts[i] for i in top_indices]


def search_shops(user_query, top_k=4):
    """
    Semantic search for shops.
    """
    query_vec = embedding_model.encode([user_query])
    sims = cosine_similarity(query_vec, shop_embeddings)[0]
    top_indices = sims.argsort()[-top_k:][::-1]
    return [shop_texts[i] for i in top_indices]


def search_all(user_query, top_k=5):
    """
    Combined search — finds both products and shops relevant to the query.
    Returns a dict with separate lists.
    """
    return {
        "products": search_products(user_query, top_k),
        "shops": search_shops(user_query, top_k),
    }
