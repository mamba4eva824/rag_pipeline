#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Clean Confluence Plain Text Data

This script cleans the plain text extracted from Confluence pages and 
outputs a structured JSON file optimized for embedding and RAG applications.
"""

import json
import re
import os
from datetime import datetime
import pandas as pd

def clean_text(text):
    """Clean the plain text from Confluence export"""
    if not isinstance(text, str) or not text.strip():
        return ""
    
    # Remove artifacts from HTML-to-text conversion
    text = re.sub(r':check_mark:atlassian-check_mark#[A-Z0-9]+', '', text)
    
    # Remove excessive blank lines (more than 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove trailing whitespace from each line
    text = '\n'.join([line.rstrip() for line in text.split('\n')])
    
    # Remove email markdown formatting
    text = re.sub(r'\[\s*([^\]]+)\]\(mailto:[^)]+\)', r'\1', text)
    
    # Remove link markdown formatting
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    
    # Remove excessive asterisks used for bullet points
    text = re.sub(r'^\s*\*\s*\*\s*\*\s*$', '', text, flags=re.MULTILINE)
    
    # Fix spacing for bullet points (consistent indentation)
    text = re.sub(r'^(\s*)\*\s*', r'\1- ', text, flags=re.MULTILINE)
    
    # Remove horizontal rules
    text = re.sub(r'\n\*\s*\*\s*\*\s*\n', '\n', text)
    
    # Remove "excerpts" artifact
    text = re.sub(r'\d+excerpts', '', text)
    
    # Standardize heading formatting (ensure space after #)
    text = re.sub(r'^(#+)([^#\s])', r'\1 \2', text, flags=re.MULTILINE)
    
    # Fix any double spaces
    text = re.sub(r'\s{2,}', ' ', text)
    
    # Remove empty bullet points
    text = re.sub(r'^\s*-\s*$', '', text, flags=re.MULTILINE)
    
    # Final trim
    text = text.strip()
    
    return text

def split_into_chunks(text, max_chunk_size=1000, overlap=100):
    """Split text into overlapping chunks for better embedding"""
    if not text or len(text) <= max_chunk_size:
        return [text] if text else []
    
    # Split by paragraphs first
    paragraphs = re.split(r'\n\n+', text)
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        # If adding this paragraph exceeds max size, store current chunk and start a new one
        if len(current_chunk) + len(paragraph) + 2 > max_chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            
            # Start new chunk with overlap from the end of previous chunk
            if len(current_chunk) > overlap:
                # Find the last complete sentence or paragraph break within overlap
                overlap_text = current_chunk[-overlap:]
                sentence_break = max(overlap_text.rfind('. '), overlap_text.rfind('\n'))
                
                if sentence_break != -1:
                    # Start new chunk with text after the last sentence in overlap
                    current_chunk = current_chunk[-(overlap-sentence_break):]
                else:
                    current_chunk = ""
            else:
                current_chunk = ""
                
        # Add paragraph to current chunk
        if current_chunk and not current_chunk.endswith('\n'):
            current_chunk += "\n\n"
        current_chunk += paragraph
        
        # If a single paragraph exceeds max size, split it by sentences
        if len(current_chunk) > max_chunk_size:
            sentences = re.split(r'(?<=\. )', current_chunk)
            current_chunk = ""
            temp_chunk = ""
            
            for sentence in sentences:
                if len(temp_chunk) + len(sentence) > max_chunk_size and temp_chunk:
                    chunks.append(temp_chunk.strip())
                    temp_chunk = sentence
                else:
                    temp_chunk += sentence
            
            if temp_chunk:
                current_chunk = temp_chunk
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def main():
    # Load the Confluence data
    confluence_file_path = '../extraction/exports/confluence_full_content_Founders_20250503_140439.json'

    try:
        with open(confluence_file_path, 'r', encoding='utf-8') as f:
            confluence_data = json.load(f)
        print(f"Loaded {len(confluence_data)} pages from the Confluence export.")
    except Exception as e:
        print(f"Error loading Confluence data: {e}")
        return

    # Process each page
    cleaned_data = []

    for page in confluence_data:
        # Clean the plain text
        cleaned_text = clean_text(page.get('plain_text', ''))
        
        # Calculate word and character counts
        word_count = len(cleaned_text.split())
        char_count = len(cleaned_text)
        
        # Create cleaned page record
        cleaned_page = {
            'id': page.get('id', ''),
            'title': page.get('title', ''),
            'url': page.get('url', ''),
            'space': 'Founders',  # From the filename
            'ancestors': page.get('ancestors', ''),
            'last_updated': page.get('last_updated', ''),
            'cleaned_text': cleaned_text,
            'metadata': {
                'word_count': word_count,
                'char_count': char_count,
                'version': page.get('version', 0)
            }
        }
        
        cleaned_data.append(cleaned_page)
        
    print(f"Processed {len(cleaned_data)} pages.")

    # Create chunked version for RAG
    chunked_data = []

    for page in cleaned_data:
        # Get chunks from the cleaned text
        chunks = split_into_chunks(page['cleaned_text'], max_chunk_size=1000, overlap=100)
        
        # Create a record for each chunk
        for i, chunk_content in enumerate(chunks):
            chunk = {
                'chunk_id': f"{page['id']}-{i+1}",
                'page_id': page['id'],
                'title': page['title'],
                'space': page['space'],
                'url': page['url'],
                'chunk_index': i + 1,
                'total_chunks': len(chunks),
                'content': chunk_content,
                'metadata': {
                    'ancestors': page['ancestors'],
                    'last_updated': page['last_updated'],
                    'word_count': len(chunk_content.split()),
                    'char_count': len(chunk_content)
                }
            }
            chunked_data.append(chunk)

    print(f"Generated {len(chunked_data)} chunks from {len(cleaned_data)} pages.")

    # Display a comparison of original vs. cleaned text (for the first page)
    if cleaned_data and confluence_data:
        print("\n=== Original Text Sample (First 200 chars) ===\n")
        print(confluence_data[0].get('plain_text', '')[:200] + "...\n")
        
        print("=== Cleaned Text Sample (First 200 chars) ===\n")
        print(cleaned_data[0].get('cleaned_text', '')[:200] + "...\n")
        
        print("=== First Chunk (RAG Format) ===\n")
        first_chunk = next((chunk for chunk in chunked_data if chunk['page_id'] == cleaned_data[0]['id'] and chunk['chunk_index'] == 1), None)
        if first_chunk:
            print(f"Chunk {first_chunk['chunk_index']} of {first_chunk['total_chunks']}\n")
            print(first_chunk['content'][:200] + "...\n")

    # Create exports directory if it doesn't exist
    os.makedirs('exports', exist_ok=True)

    # Export the cleaned data (page level)
    cleaned_file_path = 'exports/founders_confluence_cleaned.json'

    try:
        with open(cleaned_file_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        print(f"Cleaned data exported to {cleaned_file_path}")
    except Exception as e:
        print(f"Error exporting cleaned data: {e}")

    # Export the chunked data (for RAG)
    chunked_file_path = 'exports/founders_confluence_chunks.json'

    try:
        with open(chunked_file_path, 'w', encoding='utf-8') as f:
            json.dump(chunked_data, f, ensure_ascii=False, indent=2)
        print(f"Chunked data exported to {chunked_file_path}")
    except Exception as e:
        print(f"Error exporting chunked data: {e}")

    # Provide summary of the data
    if cleaned_data:
        # Create a DataFrame for analysis
        df = pd.DataFrame([
            {
                'id': page['id'],
                'title': page['title'],
                'word_count': page['metadata']['word_count'],
                'char_count': page['metadata']['char_count'],
                'chunks': len([c for c in chunked_data if c['page_id'] == page['id']])
            } for page in cleaned_data
        ])
        
        print("\n=== Data Summary ===\n")
        print(f"Total pages: {len(cleaned_data)}")
        print(f"Total chunks: {len(chunked_data)}")
        print(f"Average chunks per page: {df['chunks'].mean():.1f}")
        print(f"Average word count per page: {df['word_count'].mean():.1f}")
        print(f"Average word count per chunk: {sum(c['metadata']['word_count'] for c in chunked_data) / len(chunked_data):.1f}")
        
        print("\nPage details:")
        for _, row in df.iterrows():
            print(f"- {row['title']}: {row['word_count']} words, {row['chunks']} chunks")

if __name__ == "__main__":
    main()