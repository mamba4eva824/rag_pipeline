#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pinecone Uploader

This script loads the embeddings and metadata generated from Confluence content,
and uploads them to Pinecone for vector search.
"""

import os
import glob
import json
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Configure paths
DATA_DIR = "exports"

def find_latest_files() -> tuple:
    """Find the latest embeddings and metadata files in the exports directory"""
    # Find all embedding files
    embedding_files = glob.glob(os.path.join(DATA_DIR, "founders_confluence_embeddings_*.npy"))
    metadata_files = glob.glob(os.path.join(DATA_DIR, "founders_confluence_embedding_metadata_*.json"))
    
    if not embedding_files or not metadata_files:
        raise FileNotFoundError("Embedding or metadata files not found")
    
    # Get the latest files based on modification time
    latest_embedding = max(embedding_files, key=os.path.getmtime)
    latest_metadata = max(metadata_files, key=os.path.getmtime)
    
    print(f"Found latest embedding file: {os.path.basename(latest_embedding)}")
    print(f"Found latest metadata file: {os.path.basename(latest_metadata)}")
    
    return latest_embedding, latest_metadata

def load_data(embedding_file: str, metadata_file: str) -> tuple:
    """Load embeddings and metadata from files"""
    try:
        # Load embeddings
        embeddings = np.load(embedding_file)
        print(f"Loaded embeddings with shape: {embeddings.shape}")
        
        # Load metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        print(f"Loaded metadata for {len(metadata)} chunks")
        
        # Verify dimensions match
        if len(metadata) != embeddings.shape[0]:
            raise ValueError(f"Mismatch between embeddings ({embeddings.shape[0]}) and metadata ({len(metadata)})")
            
        return embeddings, metadata
    except Exception as e:
        print(f"Error loading data: {e}")
        raise

def initialize_pinecone(index_name: str, dimension: int):
    """Initialize Pinecone client and ensure index exists"""
    # Get API key from environment variables
    api_key = os.getenv("PINECONE_API_KEY")
    
    if not api_key:
        raise ValueError("PINECONE_API_KEY must be set in environment variables")
    
    # Initialize Pinecone
    pc = Pinecone(api_key=api_key)
    print(f"Connected to Pinecone")
    
    # Check if index exists
    existing_indexes = pc.list_indexes().names()
    if index_name not in existing_indexes:
        print(f"Creating new index: {index_name}")
        pc.create_index(
            name=index_name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"  # Using a region supported by the free tier
            )
        )
    else:
        print(f"Using existing index: {index_name}")
    
    # Connect to the index
    index = pc.Index(index_name)
    return index

def prepare_vectors_for_upsert(embeddings: np.ndarray, metadata: List[Dict]) -> List[Dict]:
    """Prepare vectors for upsert to Pinecone"""
    vectors = []
    
    for i, (embedding, meta) in enumerate(zip(embeddings, metadata)):
        # Ensure chunk_id exists and is used as the vector ID
        if "chunk_id" not in meta:
            raise ValueError(f"Missing chunk_id in metadata at index {i}")
            
        vector = {
            "id": meta["chunk_id"],
            "values": embedding.tolist(),
            "metadata": meta
        }
        vectors.append(vector)
    
    return vectors

def upsert_to_pinecone(index, vectors: List[Dict], batch_size: int = 100) -> None:
    """Upsert vectors to Pinecone in batches"""
    total_vectors = len(vectors)
    print(f"Upserting {total_vectors} vectors to Pinecone in batches of {batch_size}")
    
    # Process in batches
    for i in tqdm(range(0, total_vectors, batch_size)):
        batch = vectors[i:i + batch_size]
        try:
            upsert_response = index.upsert(vectors=batch)
            if i == 0:  # Print response for first batch only
                print(f"First batch upsert response: {upsert_response}")
        except Exception as e:
            print(f"Error upserting batch {i // batch_size}: {e}")
            raise

def main():
    """Main execution flow"""
    print("=== Pinecone Uploader ===")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Find latest files
        embedding_file, metadata_file = find_latest_files()
        
        # Load embeddings and metadata
        embeddings, metadata = load_data(embedding_file, metadata_file)
        
        # Determine embedding dimension
        dimension = embeddings.shape[1]
        print(f"Embedding dimension: {dimension}")
        
        # Initialize Pinecone with appropriate index name
        index_name = "confluence-founders"
        index = initialize_pinecone(index_name, dimension)
        
        # Prepare vectors for upsert
        vectors = prepare_vectors_for_upsert(embeddings, metadata)
        
        # Upsert vectors to Pinecone
        upsert_to_pinecone(index, vectors)
        
        # Get index stats
        stats = index.describe_index_stats()
        print(f"\nIndex statistics after upsert:")
        print(f"Total vectors in index: {stats['total_vector_count']}")
        print(f"Index dimension: {stats['dimension']}")
        
        print("\n✅ Successfully uploaded embeddings to Pinecone")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()