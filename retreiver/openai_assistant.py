#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OpenAI Integration for Confluence Knowledge Base

This script provides functionality to generate coherent answers from OpenAI GPT
based on user questions and retrieved context from Confluence chunks.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any, Union, Optional, Tuple, Iterator
from datetime import datetime
import time
from openai import OpenAI
from dotenv import load_dotenv

# Add parent directory to path to allow imports from sibling modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from retreiver.retrieval import ConfluenceRetriever

# Load environment variables
load_dotenv()

# Configure OpenAI model
DEFAULT_MODEL = "gpt-4o" 

# Configure logging
LOG_DIR = os.path.join(parent_dir, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"openai_interactions_{datetime.now().strftime('%Y%m%d')}.log")

# Set up logger
logger = logging.getLogger("openai_assistant")
logger.setLevel(logging.INFO)

# File handler for logging to file
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# Console handler for logging to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
console_handler.setFormatter(file_format)
logger.addHandler(console_handler)

class OpenAIAssistant:
    """Class for generating answers from OpenAI GPT based on retrieved context"""
    
    def __init__(
        self, 
        retriever: Optional[ConfluenceRetriever] = None,
        model_name: str = DEFAULT_MODEL,
        max_tokens: int = 1000,
        temperature: float = 0.7,  # 0 for deterministic responses
        top_k: int = 5,  # Number of chunks to retrieve
        system_prompt_template: Optional[str] = None,
        enable_logging: bool = True
    ):
        """Initialize the OpenAI Assistant with configuration"""
        # Set up API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=api_key)
        
        # Initialize retriever if not provided
        if not retriever:
            self.retriever = ConfluenceRetriever()
        else:
            self.retriever = retriever
        
        # Store parameters
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_k = top_k
        self.enable_logging = enable_logging
        
        # Set up default system prompt if not provided
        if not system_prompt_template:
            self.system_prompt_template = """
            You are a helpful, accurate, and concise internal knowledge assistant for the company.
            Answer questions based ONLY on the provided Confluence context.
            If the context doesn't contain the answer, say "I don't have enough information to answer that question."
            Do not make up information or use knowledge outside the provided context.
            
            IMPORTANT: You will be provided with multiple document chunks. Search through ALL of them carefully to find the most relevant information. The answer might be in any of the provided chunks, not necessarily the first one.
            
            Provide clear, direct answers without including URLs or links in your response text.
            Focus on delivering the information content - source attribution will be handled separately.
            Provide clear, direct answers without adding generic statements about document dates or creation information.
            """
        else:
            self.system_prompt_template = system_prompt_template
        
        # Log initialization
        if self.enable_logging:
            logger.info(f"OpenAIAssistant initialized with model: {model_name}, top_k: {top_k}")
    
    def retrieve_context(
        self, 
        query: str, 
        top_k: Optional[int] = None, 
        filter: Optional[Dict] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Retrieve relevant chunks for a query
        
        Args:
            query: The user question
            top_k: Number of chunks to retrieve
            filter: Optional filter criteria
            
        Returns:
            Tuple of (retrieved results, formatted context string)
        """
        # Use class default if not provided
        if not top_k:
            top_k = self.top_k
        
        # Get results from retriever
        results = self.retriever.search(query, top_k=top_k, filter=filter)
        
        # Use the formatting function for consistent author information
        formatted_context = format_results_for_openai(results)
        
        # Log retrieval results
        if self.enable_logging:
            doc_titles = [result['metadata'].get('title', 'Untitled') for result in results]
            doc_scores = [result.get('score', 0) for result in results]
            logger.info(f"Retrieved {len(results)} documents for query: '{query}'")
            for i, (title, score) in enumerate(zip(doc_titles, doc_scores)):
                logger.info(f"  Doc {i+1}: {title} (Score: {score:.4f})")
        
        return results, formatted_context
    
    def generate_answer(
        self,
        query: str,
        context: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False
    ) -> Union[str, Any]:
        """
        Generate an answer from OpenAI GPT based on the query and context
        
        Args:
            query: The user question
            context: Optional pre-retrieved context string
            model: Override the default model
            max_tokens: Override the default max tokens
            temperature: Override the default temperature
            stream: Whether to stream the response
            
        Returns:
            OpenAI's response as a string or a stream
        """
        # Use class defaults if not provided
        if not model:
            model = self.model_name
        if not max_tokens:
            max_tokens = self.max_tokens
        if not temperature:
            temperature = self.temperature
            
        # Retrieve context if not provided
        if not context:
            _, context = self.retrieve_context(query)
        
        # Construct the system prompt
        system_prompt = self.system_prompt_template.strip()
        
        # Log request to OpenAI
        if self.enable_logging:
            logger.info(f"Sending request to OpenAI model: {model}")
            logger.info(f"Query: '{query}'")
            # Log more of the context to better understand what's being sent
            context_preview = context[:2000] + "..." if len(context) > 2000 else context
            logger.info(f"Context (first 2000 chars): {context_preview}")
        
        # Send request to OpenAI API
        try:
            response = self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"I need information based on our company's internal knowledge base. Here are the most relevant documents:\n\n{context}\n\nQuestion: {query}"
                    }
                ],
                stream=stream
            )
            
            if stream:
                if self.enable_logging:
                    logger.info("Streaming response initiated")
                return response
            else:
                answer = response.choices[0].message.content
                # Log OpenAI's response
                if self.enable_logging:
                    answer_preview = answer[:500] + "..." if len(answer) > 500 else answer
                    logger.info(f"OpenAI response: {answer_preview}")
                return answer

        except Exception as e:
            error_msg = f"Error generating answer from OpenAI: {e}"
            if self.enable_logging:
                logger.error(error_msg)
            print(error_msg)
            return error_msg
    
    def answer_question(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict] = None,
        stream: bool = False,
        verbose: bool = False,
        log_interaction: bool = True
    ) -> Union[str, Any]:
        """
        Complete process to answer a question - retrieve context and generate answer
        
        Args:
            query: The user question
            top_k: Number of chunks to retrieve
            filter: Optional filter criteria
            stream: Whether to stream the response
            verbose: Whether to print additional info
            log_interaction: Whether to log this specific interaction
            
        Returns:
            OpenAI's response as a string or a stream
        """
        interaction_id = datetime.now().strftime("%Y%m%d%H%M%S")
        start_time = time.time()
        
        # Log the start of the interaction
        local_logging = self.enable_logging and log_interaction
        if local_logging:
            logger.info(f"------- New Interaction [{interaction_id}] -------")
            logger.info(f"User query: '{query}'")
        
        if verbose:
            print(f"Query: {query}")
        
        # Retrieve context
        results, context = self.retrieve_context(query, top_k=top_k, filter=filter)
        retrieval_time = time.time() - start_time
        
        if verbose:
            print(f"Retrieved {len(results)} chunks in {retrieval_time:.2f}s")
            for i, result in enumerate(results):
                print(f"  {i+1}. {result['metadata'].get('title', 'Untitled')} (Score: {result.get('score', 0):.4f})")
        
        # Generate answer
        gen_start_time = time.time()
        response = self.generate_answer(query, context, stream=stream)
        generation_time = time.time() - gen_start_time
        total_time = time.time() - start_time
        
        # Log timing information
        if local_logging and not stream:
            logger.info(f"Retrieval time: {retrieval_time:.2f}s")
            logger.info(f"Generation time: {generation_time:.2f}s")
            logger.info(f"Total time: {total_time:.2f}s")
            logger.info(f"------- End Interaction [{interaction_id}] -------")
        
        if verbose and not stream:
            print(f"Generated answer in {generation_time:.2f}s")
            print(f"Total time: {total_time:.2f}s")
        
        return response
    
    def handle_stream(self, stream, log_response: bool = True):
        """
        Process and print a streaming response
        
        Args:
            stream: The streaming response from OpenAI
            log_response: Whether to log the complete response after streaming
        """
        response_chunks = []
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                text = chunk.choices[0].delta.content
                print(text, end="", flush=True)
                response_chunks.append(text)
        
        print()  # Print newline at the end
        
        # Log the complete response
        if self.enable_logging and log_response:
            full_response = "".join(response_chunks)
            response_preview = full_response[:500] + "..." if len(full_response) > 500 else full_response
            logger.info(f"OpenAI streaming response (reconstructed): {response_preview}")


def format_results_for_openai(results: List[Dict[str, Any]]) -> str:
    """Format search results for OpenAI context"""
    formatted_chunks = []
    
    for i, result in enumerate(results, 1):
        metadata = result.get('metadata', {})
        content = metadata.get('content', 'No content available')
        title = metadata.get('title', 'Untitled')
        url = metadata.get('url', '')
        ancestors = metadata.get('ancestors', '')
        last_updated = metadata.get('last_updated', '')
        created_by = metadata.get('created_by', 'Unknown')
        updated_by = metadata.get('updated_by', 'Unknown')
        score = result.get('score', 0)
        
        # Format dates for display
        date_info = []
        if last_updated and last_updated != '':
            date_info.append(f"Updated: {last_updated}")
        
        # Format author info
        author_info = []
        if created_by and created_by != 'Unknown':
            author_info.append(f"Created by: {created_by}")
        if updated_by and updated_by != 'Unknown' and updated_by != created_by:
            author_info.append(f"Last updated by: {updated_by}")
        
        # Build metadata string
        meta_parts = []
        if ancestors:
            meta_parts.append(f"Path: {ancestors}")
        if date_info:
            meta_parts.append(" | ".join(date_info))
        if author_info:
            meta_parts.append(" | ".join(author_info))
        
        metadata_str = " | ".join(meta_parts) if meta_parts else "No metadata"
        
        chunk_text = f"""
CHUNK {i} (Relevance: {score:.3f})
Title: {title}
{metadata_str}
URL: {url}

Content:
{content}

---
"""
        formatted_chunks.append(chunk_text)
    
    return "\n".join(formatted_chunks)


def main():
    """Interactive demo of OpenAI Assistant"""
    print("=== OpenAI Assistant for Confluence Knowledge Base ===")
    
    # Initialize OpenAI Assistant
    try:
        assistant = OpenAIAssistant(top_k=3, model_name="gpt-4o")  
        print(f"Using top_k = {assistant.top_k} for retrieval")
        print(f"Logging enabled: interactions will be logged to {LOG_FILE}")
    except ValueError as e:
        print(f"Error: {e}")
        print("Set the OPENAI_API_KEY environment variable and try again.")
        return
    
    # Interactive query loop
    print("\nEnter your questions below (type 'exit' to quit):")
    while True:
        query = input("\nQ: ")
        if query.lower() in ["exit", "quit", "q"]:
            break
        
        print("\nGenerating answer...")
        try:
            # Use streaming for better UX in interactive mode
            stream = assistant.answer_question(query, stream=True, verbose=True)
            assistant.handle_stream(stream)
        except Exception as e:
            print(f"Error: {e}")
            logger.error(f"Error in interactive mode: {e}")


if __name__ == "__main__":
    main() 