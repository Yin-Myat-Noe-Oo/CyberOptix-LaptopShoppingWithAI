# embeddings.py
from sentence_transformers import SentenceTransformer
from .utils import get_all_product_text

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
product_texts = get_all_product_text()
product_embeddings = embedding_model.encode(product_texts)
