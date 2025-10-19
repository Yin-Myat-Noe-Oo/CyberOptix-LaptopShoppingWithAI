from sentence_transformers import SentenceTransformer
from flame.util import get_all_product_text, get_all_shop_text

# Load the embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# Retrieve product and shop texts from the database
product_texts = get_all_product_text()
shop_texts = get_all_shop_text()

# Generate embeddings
product_embeddings = embedding_model.encode(product_texts, show_progress_bar=True)
shop_embeddings = embedding_model.encode(shop_texts, show_progress_bar=True)
