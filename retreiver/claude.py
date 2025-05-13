#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Claude Integration for Confluence Knowledge Base

This script provides functionality to generate coherent answers from Claude AI
based on user questions and retrieved context from Confluence chunks.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any, Union, Optional, Tuple, Iterator
from datetime import datetime
import time
import anthropic
from anthropic import Anthropic
from dotenv import load_dotenv

# Add parent directory to path to allow imports from sibling modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from retreiver.retrieval import ConfluenceRetriever

# Load environment variables
load_dotenv()

# Configure Claude model
DEFAULT_MODEL = "claude-3-opus-20240229"  # Highest quality
# DEFAULT_MODEL = "claude-3-sonnet-20240229"  # Good balance of quality and speed
# DEFAULT_MODEL = "claude-3-haiku-20240307"  # Fastest option

# Configure logging
LOG_DIR = os.path.join(parent_dir, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"claude_interactions_{datetime.now().strftime('%Y%m%d')}.log")

# Set up logger
logger = logging.getLogger("claude_assistant")
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

class ClaudeAssistant:
    """Class for generating answers from Claude based on retrieved context"""
    
    def __init__(
        self, 
        retriever: Optional[ConfluenceRetriever] = None,
        model_name: str = DEFAULT_MODEL,
        max_tokens: int = 1000,
        temperature: float = 0.0,  # 0 for deterministic responses
        top_k: int = 5,  # Number of chunks to retrieve
        system_prompt_template: Optional[str] = None,
        enable_logging: bool = True
    ):
        """Initialize the Claude Assistant with configuration"""
        # Set up API key
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set in environment variables")
        
        # Initialize Anthropic client
        self.client = Anthropic(api_key=api_key)
        
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
            Include relevant URLs from the context when appropriate.
            """
        else:
            self.system_prompt_template = system_prompt_template
        
        # Log initialization
        if self.enable_logging:
            logger.info(f"ClaudeAssistant initialized with model: {model_name}, top_k: {top_k}")
    
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
        
        # Format context for prompt
        context_parts = []
        for i, result in enumerate(results):
            metadata = result['metadata']
            title = metadata.get('title', 'Untitled')
            url = metadata.get('url', 'No URL')
            content = metadata.get('content', 'No content available')
            
            chunk_context = f"Document {i+1}: {title}\nURL: {url}\nContent:\n{content}\n"
            context_parts.append(chunk_context)
        
        formatted_context = "\n---\n".join(context_parts)
        
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
    ) -> Union[str, Any]:  # Use Any for the streaming response type
        """
        Generate an answer from Claude based on the query and context
        
        Args:
            query: The user question
            context: Optional pre-retrieved context string
            model: Override the default model
            max_tokens: Override the default max tokens
            temperature: Override the default temperature
            stream: Whether to stream the response
            
        Returns:
            Claude's response as a string or a stream
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
        
        # Log request to Claude
        if self.enable_logging:
            logger.info(f"Sending request to Claude model: {model}")
            logger.info(f"Query: '{query}'")
            # Log a truncated version of the context to avoid excessive logging
            context_preview = context[:500] + "..." if len(context) > 500 else context
            logger.info(f"Context (truncated): {context_preview}")
        
        # Send request to Claude API
        try:
            response = self.client.messages.create(
                model=model,
                system=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
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
                answer = response.content[0].text
                # Log Claude's response
                if self.enable_logging:
                    answer_preview = answer[:500] + "..." if len(answer) > 500 else answer
                    logger.info(f"Claude response: {answer_preview}")
                return answer

        except Exception as e:
            error_msg = f"Error generating answer from Claude: {e}"
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
    ) -> Union[str, Any]:  # Use Any for the streaming response type
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
            Claude's response as a string or a stream
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
            stream: The streaming response from Claude
            log_response: Whether to log the complete response after streaming
        """
        response_chunks = []
        for chunk in stream:
            if chunk.type == "content_block_delta" and hasattr(chunk.delta, "text"):
                text = chunk.delta.text
                print(text, end="", flush=True)
                response_chunks.append(text)
        
        print()  # Print newline at the end
        
        # Log the complete response
        if self.enable_logging and log_response:
            full_response = "".join(response_chunks)
            response_preview = full_response[:500] + "..." if len(full_response) > 500 else full_response
            logger.info(f"Claude streaming response (reconstructed): {response_preview}")


def main():
    """Interactive demo of Claude Assistant"""
    print("=== Claude Assistant for Confluence Knowledge Base ===")
    
    # Initialize Claude Assistant
    try:
        assistant = ClaudeAssistant(top_k=3, model_name="claude-3-haiku-20240307")  # Use faster model for testing
        print(f"Initialized with model: {assistant.model_name}")
        print(f"Using top_k = {assistant.top_k} for retrieval")
        print(f"Logging enabled: interactions will be logged to {LOG_FILE}")
    except ValueError as e:
        print(f"Error: {e}")
        print("Set the ANTHROPIC_API_KEY environment variable and try again.")
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