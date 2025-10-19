from flame.data_preparation import prepare_training_data
from sentence_transformers import SentenceTransformer
import numpy as np
import os

def train_and_save_embeddings(output_dir="embeddings"):
    os.makedirs(output_dir, exist_ok=True)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    data = prepare_training_data()

    def save_embeddings(name, texts, ids):
        if not texts:
            return
        embeddings = model.encode(texts, show_progress_bar=True)
        np.save(os.path.join(output_dir, f"{name}_embeddings.npy"), embeddings)
        np.save(os.path.join(output_dir, f"{name}_ids.npy"), np.array(ids))
        print(f"✅ Saved {len(texts)} {name} embeddings")

    save_embeddings("product", data["product_texts"], data["product_ids"])
    save_embeddings("shop", data["shop_texts"], data["shop_ids"])
    save_embeddings("brand", data["brand_texts"], data["brand_ids"])
    save_embeddings("category", data["category_texts"], data["category_ids"])

if __name__ == "__main__":
    train_and_save_embeddings()
