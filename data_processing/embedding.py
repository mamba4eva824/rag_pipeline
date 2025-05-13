#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Confluence Data Embedding

This script processes the cleaned Confluence data chunks, tokenizes the text,
and creates embeddings using SentenceTransformers. The embeddings are then saved
for use in a RAG system.
"""

import json
import os
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Tuple
import torch
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

# Configure paths
DATA_DIR = "exports"
CHUNKS_FILE = os.path.join(DATA_DIR, "founders_confluence_chunks.json")
EMBEDDINGS_FILE = os.path.join(DATA_DIR, f"founders_confluence_embeddings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.npy")
METADATA_FILE = os.path.join(DATA_DIR, f"founders_confluence_embedding_metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

# Configure embedding model
MODEL_NAME = "all-MiniLM-L6-v2"  # Smaller, faster model suitable for RAG
# MODEL_NAME = "all-mpnet-base-v2"  # Alternative: Better quality but slower

def load_chunks() -> List[Dict[str, Any]]:
    """Load the cleaned chunks from the JSON file"""
    try:
        with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        print(f"Loaded {len(chunks)} chunks from {CHUNKS_FILE}")
        return chunks
    except Exception as e:
        print(f"Error loading chunks: {e}")
        return []

def create_embeddings(chunks: List[Dict[str, Any]], model_name: str = MODEL_NAME) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """Create embeddings for each chunk using the specified SentenceTransformers model"""
    print(f"Loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)
    
    # Extract text content from chunks
    texts = [chunk["content"] for chunk in chunks]
    
    # Get device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    model = model.to(device)
    
    # Create embeddings with progress bar
    print("Creating embeddings...")
    embeddings = []
    batch_size = 16
    
    for i in tqdm(range(0, len(texts), batch_size)):
        batch_texts = texts[i:i+batch_size]
        batch_embeddings = model.encode(batch_texts)
        embeddings.extend(batch_embeddings)
    
    # Convert to numpy array
    embeddings_array = np.array(embeddings)
    
    # Create metadata for each embedding
    metadata = []
    for i, chunk in enumerate(chunks):
        metadata.append({
            "chunk_id": chunk["chunk_id"],
            "embedding_index": i,
            "page_id": chunk["page_id"],
            "title": chunk["title"],
            "url": chunk["url"],
            "chunk_index": chunk["chunk_index"],
            "total_chunks": chunk["total_chunks"],
            "content": chunk["content"]  # Add the text content to metadata
        })
    
    print(f"Created {len(embeddings)} embeddings of dimension {embeddings_array.shape[1]}")
    return embeddings_array, metadata

def save_embeddings(embeddings: np.ndarray, metadata: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Save embeddings and metadata to disk"""
    # Save embeddings as numpy array
    np.save(EMBEDDINGS_FILE, embeddings)
    
    # Save metadata as JSON
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"Embeddings saved to: {EMBEDDINGS_FILE}")
    print(f"Metadata saved to: {METADATA_FILE}")
    
    return EMBEDDINGS_FILE, METADATA_FILE

def main():
    """Main execution flow"""
    print("=== Confluence Data Embedding ===")
    
    # Create output directory if it doesn't exist
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Load the chunks
    chunks = load_chunks()
    if not chunks:
        print("No chunks to process. Exiting.")
        return
    
    # Create embeddings
    embeddings, metadata = create_embeddings(chunks)
    
    # Save embeddings and metadata
    emb_file, meta_file = save_embeddings(embeddings, metadata)
    
    # Print summary
    print("\n=== Embedding Summary ===")
    print(f"Total chunks embedded: {len(chunks)}")
    print(f"Embedding dimensions: {embeddings.shape}")
    print(f"Model used: {MODEL_NAME}")
    print(f"Files created:")
    print(f"  - {emb_file}")
    print(f"  - {meta_file}")
    
    # Return embeddings and metadata for potential further use
    return embeddings, metadata

if __name__ == "__main__":
    main()