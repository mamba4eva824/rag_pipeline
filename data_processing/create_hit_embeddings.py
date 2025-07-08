#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HIT Confluence Data Embedding

This script processes the cleaned HIT Confluence data chunks, tokenizes the text,
and creates embeddings using SentenceTransformers. The embeddings are then saved
for use in a RAG system.
"""

import json
import os
import numpy as np
import pandas as pd
import argparse
from datetime import datetime
from typing import List, Dict, Any, Tuple
import torch
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

def find_latest_chunks_file(space: str = "HIT") -> str:
    """Find the most recent chunks file for the given space"""
    exports_dir = "exports"
    chunks_files = [f for f in os.listdir(exports_dir) if f.startswith(f"{space}_confluence_chunks_") and f.endswith(".json")]
    
    if not chunks_files:
        raise FileNotFoundError(f"No chunks file found for space '{space}' in {exports_dir}")
    
    # Sort by timestamp (assuming filename format includes timestamp)
    chunks_files.sort(reverse=True)
    latest_file = os.path.join(exports_dir, chunks_files[0])
    
    print(f"Using chunks file: {latest_file}")
    return latest_file

def load_chunks(chunks_file: str) -> List[Dict[str, Any]]:
    """Load the cleaned chunks from the JSON file"""
    try:
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        print(f"Loaded {len(chunks)} chunks from {chunks_file}")
        return chunks
    except Exception as e:
        print(f"Error loading chunks: {e}")
        return []

def create_embeddings(chunks: List[Dict[str, Any]], model_name: str = "all-MiniLM-L6-v2") -> Tuple[np.ndarray, List[Dict[str, Any]]]:
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
    batch_size = 32  # Increased batch size for better performance
    
    for i in tqdm(range(0, len(texts), batch_size)):
        batch_texts = texts[i:i+batch_size]
        batch_embeddings = model.encode(batch_texts, 
                                        convert_to_numpy=True,
                                        show_progress_bar=False)
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
            "space": chunk["space"],
            "url": chunk["url"],
            "chunk_index": chunk["chunk_index"],
            "total_chunks": chunk["total_chunks"],
            "content": chunk["content"],
            "ancestors": chunk["metadata"]["ancestors"],
            "last_updated": chunk["metadata"]["last_updated"],
            "created_by": chunk["metadata"].get("created_by", "Unknown"),
            "created_by_email": chunk["metadata"].get("created_by_email", ""),
            "updated_by": chunk["metadata"].get("updated_by", "Unknown"),
            "updated_by_email": chunk["metadata"].get("updated_by_email", ""),
            "version_by": chunk["metadata"].get("version_by", "Unknown"),
            "word_count": chunk["metadata"]["word_count"],
            "char_count": chunk["metadata"]["char_count"]
        })
    
    print(f"Created {len(embeddings)} embeddings of dimension {embeddings_array.shape[1]}")
    return embeddings_array, metadata

def save_embeddings(embeddings: np.ndarray, metadata: List[Dict[str, Any]], space: str = "HIT") -> Tuple[str, str]:
    """Save embeddings and metadata to disk"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create file paths
    embeddings_file = f"exports/{space}_confluence_embeddings_{timestamp}.npy"
    metadata_file = f"exports/{space}_confluence_embedding_metadata_{timestamp}.json"
    
    # Save embeddings as numpy array
    np.save(embeddings_file, embeddings)
    
    # Save metadata as JSON
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"Embeddings saved to: {embeddings_file}")
    print(f"Metadata saved to: {metadata_file}")
    
    return embeddings_file, metadata_file

def analyze_embeddings(chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> None:
    """Provide analysis of the embedding dataset"""
    print("\n=== Embedding Analysis ===")
    
    # Basic stats
    print(f"Total embeddings: {len(embeddings)}")
    print(f"Embedding dimensions: {embeddings.shape[1]}")
    print(f"Memory usage: {embeddings.nbytes / 1024 / 1024:.2f} MB")
    
    # Content analysis
    total_words = sum(chunk["metadata"]["word_count"] for chunk in chunks)
    total_chars = sum(chunk["metadata"]["char_count"] for chunk in chunks)
    
    print(f"Total words embedded: {total_words:,}")
    print(f"Total characters: {total_chars:,}")
    print(f"Average words per chunk: {total_words / len(chunks):.1f}")
    
    # Space analysis
    spaces = {}
    for chunk in chunks:
        space = chunk["space"]
        if space not in spaces:
            spaces[space] = 0
        spaces[space] += 1
    
    print(f"Spaces covered:")
    for space, count in spaces.items():
        print(f"  - {space}: {count} chunks")
    
    # Top pages by chunk count
    page_chunks = {}
    for chunk in chunks:
        page_id = chunk["page_id"]
        if page_id not in page_chunks:
            page_chunks[page_id] = {"title": chunk["title"], "count": 0}
        page_chunks[page_id]["count"] += 1
    
    print(f"\nTop 5 pages by chunk count:")
    sorted_pages = sorted(page_chunks.items(), key=lambda x: x[1]["count"], reverse=True)
    for page_id, info in sorted_pages[:5]:
        print(f"  - {info['title']}: {info['count']} chunks")

def main():
    parser = argparse.ArgumentParser(description='Create embeddings for HIT Confluence data')
    parser.add_argument('--space', '-s', default='HIT',
                       help='Space name for the data')
    parser.add_argument('--model', '-m', default='all-MiniLM-L6-v2',
                       help='SentenceTransformers model name')
    parser.add_argument('--chunks-file', '-c', 
                       help='Specific chunks file to use (optional)')
    
    args = parser.parse_args()
    
    print("=== HIT Confluence Data Embedding ===")
    print(f"Space: {args.space}")
    print(f"Model: {args.model}")
    print()

    # Create output directory if it doesn't exist
    os.makedirs("exports", exist_ok=True)
    
    # Find or use specified chunks file
    if args.chunks_file:
        chunks_file = args.chunks_file
    else:
        chunks_file = find_latest_chunks_file(args.space)
    
    # Load the chunks
    chunks = load_chunks(chunks_file)
    if not chunks:
        print("No chunks to process. Exiting.")
        return
    
    # Create embeddings
    embeddings, metadata = create_embeddings(chunks, args.model)
    
    # Save embeddings and metadata
    emb_file, meta_file = save_embeddings(embeddings, metadata, args.space)
    
    # Analyze the dataset
    analyze_embeddings(chunks, embeddings)
    
    # Print summary
    print(f"\n=== Embedding Summary ===")
    print(f"Total chunks embedded: {len(chunks)}")
    print(f"Embedding dimensions: {embeddings.shape}")
    print(f"Model used: {args.model}")
    print(f"Files created:")
    print(f"  - {emb_file}")
    print(f"  - {meta_file}")
    print(f"\nReady for upload to Pinecone! 🚀")
    
    # Return files for potential further use
    return emb_file, meta_file

if __name__ == "__main__":
    main() 