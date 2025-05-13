#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Retrieval System for Confluence Content with LangChain Integration

This script provides functionality to convert a user's free-text query
into the most relevant Confluence chunks by:
1. Loading the SentenceTransformer model used for embedding
2. Encoding the query string to a vector
3. Querying the Pinecone index for the top K nearest vectors
4. Returning both vector IDs and their stored metadata
5. Using LangChain for enhanced retrieval capabilities
"""

import os
from typing import List, Dict, Any, Optional, Union
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

# LangChain imports
from langchain_core.vectorstores import VectorStore
from langchain_pinecone import PineconeVectorStore
from langchain_core.embeddings import Embeddings
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_core.documents import Document

# Load environment variables
load_dotenv()

# Default parameters
DEFAULT_INDEX_NAME = "confluence-founders"
DEFAULT_TOP_K = 5
MODEL_NAME = "all-MiniLM-L6-v2"  # Make sure this matches the model used for embedding

class SentenceTransformerEmbeddingsWrapper(Embeddings):
    """Wrapper class to adapt SentenceTransformer to LangChain's Embeddings interface"""
    
    def __init__(self, model_name: str = MODEL_NAME):
        self.model = SentenceTransformer(model_name)
        
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents using the SentenceTransformer model"""
        embeddings = self.model.encode(texts)
        return embeddings.tolist()
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a query using the SentenceTransformer model"""
        embedding = self.model.encode(text)
        return embedding.tolist()

class ConfluenceRetriever:
    """Class for retrieving relevant Confluence chunks based on user queries using LangChain"""
    
    def __init__(
        self, 
        index_name: str = DEFAULT_INDEX_NAME,
        model_name: str = MODEL_NAME,
        top_k: int = DEFAULT_TOP_K
    ):
        """Initialize the retriever with Pinecone and the embedding model"""
        # Set up embedding model for LangChain
        self.embedding_model = SentenceTransformerEmbeddingsWrapper(model_name)
        print(f"Loaded model: {model_name}")
        
        # Initialize Pinecone client
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY must be set in environment variables")
        
        self.pc = Pinecone(api_key=api_key)
        
        # Store parameters
        self.index_name = index_name
        self.top_k = top_k
        
        # Create LangChain vectorstore with content field specified
        self.vector_store = PineconeVectorStore(
            index_name=index_name,
            embedding=self.embedding_model,
            text_key="content"  # Tell LangChain to use "content" field for text
        )
        print(f"Connected to Pinecone index: {index_name}")
        
        # Keep the original Pinecone client for direct access
        self.index = self.pc.Index(index_name)
    
    def search_langchain(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict] = None
    ) -> List[Document]:
        """
        Search for relevant documents using LangChain's similarity search
        
        Args:
            query_text: The text query from the user
            top_k: Number of results to return
            filter: Optional filters to apply to the query
            
        Returns:
            List of Document objects
        """
        if not top_k:
            top_k = self.top_k
            
        # Use similarity_search_with_score instead of similarity_search
        docs_with_scores = self.vector_store.similarity_search_with_score(
            query_text,
            k=top_k,
            filter=filter
        )
        
        # Process the results to include scores in metadata
        docs = []
        for doc, score in docs_with_scores:
            # Add the score to the document's metadata
            doc.metadata["score"] = float(score)
            docs.append(doc)
        
        return docs
    
    def search_hybrid(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict] = None,
        alpha: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents using LangChain's hybrid search (if supported)
        
        Args:
            query_text: The text query from the user
            top_k: Number of results to return
            filter: Optional filters to apply to the query
            alpha: Balance between dense (0) and sparse (1) retrieval
            
        Returns:
            List of formatted results
        """
        try:
            if not top_k:
                top_k = self.top_k
                
            # Attempt to use hybrid search if available
            docs = self.vector_store.similarity_search_with_score(
                query_text,
                k=top_k,
                filter=filter
            )
            
            # Format results
            results = []
            for doc, score in docs:
                # Extract metadata
                metadata = doc.metadata
                
                # Create result object
                result = {
                    "id": metadata.get("chunk_id", "unknown"),
                    "score": float(score),  # Ensure score is a Python float
                    "metadata": metadata
                }
                
                # Add page content to metadata if not already there
                if "content" not in metadata and hasattr(doc, "page_content"):
                    result["metadata"]["content"] = doc.page_content
                    
                results.append(result)
                
            return results
        except Exception as e:
            print(f"Hybrid search not supported: {e}. Falling back to regular search.")
            # Fall back to regular search
            docs = self.search_langchain(query_text, top_k, filter)
            return self._format_langchain_docs(docs)
    
    def _format_langchain_docs(self, docs: List[Document]) -> List[Dict[str, Any]]:
        """Convert LangChain Document objects to our result format"""
        results = []
        
        for doc in docs:
            # Extract metadata
            metadata = doc.metadata
            
            # Create result object with score from metadata
            result = {
                "id": metadata.get("chunk_id", "unknown"),
                "score": metadata.get("score", 0.0),  # Score is now in metadata
                "metadata": metadata
            }
            
            # Add page content to metadata if not already there
            if "content" not in metadata and hasattr(doc, "page_content"):
                result["metadata"]["content"] = doc.page_content
                
            results.append(result)
            
        return results
    
    def encode_query(self, query_text: str) -> List[float]:
        """Encode the query text into a vector using the embedding model"""
        return self.embedding_model.embed_query(query_text)
    
    def retrieve(
        self, 
        query_text: str, 
        top_k: Optional[int] = None, 
        filter: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Legacy method: Retrieve the most relevant chunks directly through Pinecone
        
        Args:
            query_text: The text query from the user
            top_k: Number of results to return (default: self.top_k)
            filter: Optional filters to apply to the query
            
        Returns:
            Dict containing matches and their metadata
        """
        if not top_k:
            top_k = self.top_k
            
        # Encode the query to a vector
        query_vector = self.encode_query(query_text)
        
        # Query Pinecone for similar vectors
        query_result = self.index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter
        )
        
        return query_result
    
    def format_results(self, query_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format the legacy query results into a more readable structure
        
        Args:
            query_result: The raw result from Pinecone query
            
        Returns:
            List of dicts with formatted results
        """
        formatted_results = []
        
        for match in query_result.get("matches", []):
            # Extract relevant information from each match
            result = {
                "id": match.get("id", ""),
                "score": match.get("score", 0),
                "metadata": match.get("metadata", {})
            }
            formatted_results.append(result)
            
        return formatted_results
    
    def search(
        self, 
        query_text: str, 
        top_k: Optional[int] = None, 
        filter: Optional[Dict] = None,
        use_hybrid: bool = False,
        use_legacy: bool = False,
        format_results: bool = True
    ) -> Union[Dict[str, Any], List[Dict[str, Any]], List[Document]]:
        """
        Search for relevant Confluence chunks - main entry point
        
        Args:
            query_text: The text query from the user
            top_k: Number of results to return
            filter: Optional filters to apply to the query
            use_hybrid: Whether to use hybrid search (if available)
            use_legacy: Whether to use the legacy Pinecone API directly
            format_results: Whether to format the results (default: True)
            
        Returns:
            If format_results is True, returns a list of formatted results
            Otherwise, returns the raw query result or LangChain documents
        """
        # Determine which search method to use
        if use_legacy:
            # Use legacy Pinecone API directly
            query_result = self.retrieve(query_text, top_k, filter)
            
            # Format results if requested
            if format_results:
                return self.format_results(query_result)
            return query_result
        elif use_hybrid:
            # Use hybrid search with LangChain
            return self.search_hybrid(query_text, top_k, filter)
        else:
            # Use standard LangChain search
            docs = self.search_langchain(query_text, top_k, filter)
            
            # Format results if requested
            if format_results:
                return self._format_langchain_docs(docs)
            return docs

def main():
    """Demo the retriever with a sample query"""
    # Initialize the retriever
    retriever = ConfluenceRetriever()
    
    # Sample query
    sample_query = "What is our pitch to investors?"
    print(f"\nSample query: '{sample_query}'")
    
    # Get and display results using LangChain
    print("\n=== LangChain Results ===")
    results = retriever.search(sample_query)
    print(f"Top {len(results)} results:")
    
    for i, result in enumerate(results):
        print(f"\n--- Result {i+1} (Score: {result.get('score', 0):.4f}) ---")
        print(f"ID: {result['id']}")
        meta = result['metadata']
        print(f"Title: {meta.get('title', 'N/A')}")
        print(f"URL: {meta.get('url', 'N/A')}")
        
        # Display content excerpt
        if 'content' in meta:
            print(f"Excerpt: {meta['content'][:150]}...")
        else:
            print("No excerpt available")
    
    # Try hybrid search if available
    print("\n=== Hybrid Search (if available) ===")
    try:
        hybrid_results = retriever.search(sample_query, use_hybrid=True)
        print(f"Top {len(hybrid_results)} results:")
        
        for i, result in enumerate(hybrid_results):
            print(f"\n--- Result {i+1} (Score: {result.get('score', 0):.4f}) ---")
            print(f"ID: {result['id']}")
            meta = result['metadata']
            print(f"Title: {meta.get('title', 'N/A')}")
    except Exception as e:
        print(f"Hybrid search not available: {e}")
        
    # Compare with legacy results
    print("\n=== Legacy Pinecone API Results ===")
    legacy_results = retriever.search(sample_query, use_legacy=True)
    print(f"Top {len(legacy_results)} results:")
    
    for i, result in enumerate(legacy_results):
        print(f"\n--- Result {i+1} (Score: {result.get('score', 0):.4f}) ---")
        print(f"ID: {result['id']}")
        meta = result['metadata']
        print(f"Title: {meta.get('title', 'N/A')}")
    
    # Interactive mode
    print("\n=== Interactive Mode ===")
    print("Type 'exit' to quit")
    while True:
        user_query = input("\nEnter your query: ")
        if user_query.lower() == 'exit':
            break
            
        results = retriever.search(user_query)
        print(f"\nTop {len(results)} results:")
        
        for i, result in enumerate(results):
            print(f"\n--- Result {i+1} (Score: {result.get('score', 0):.4f}) ---")
            print(f"ID: {result['id']}")
            meta = result['metadata']
            print(f"Title: {meta.get('title', 'N/A')}")
            print(f"URL: {meta.get('url', 'N/A')}")
            
            # Display content excerpt
            if 'content' in meta:
                print(f"Excerpt: {meta['content'][:150]}...")
            else:
                print("No excerpt available")

if __name__ == "__main__":
    main()