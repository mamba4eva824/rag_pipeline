#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Clean HIT Confluence Data

This script cleans the plain text extracted from HIT Confluence pages and 
outputs a structured JSON file optimized for embedding and RAG applications.
"""

import json
import re
import os
import argparse
from datetime import datetime
import pandas as pd
from typing import List, Dict, Any

def clean_text(text: str) -> str:
    """Clean the plain text from Confluence export"""
    if not isinstance(text, str) or not text.strip():
        return ""
    
    # Remove HTML artifacts and Confluence-specific formatting
    text = re.sub(r':check_mark:atlassian-check_mark#[A-Z0-9]+', '', text)
    text = re.sub(r'atlassian-[a-zA-Z0-9_-]+', '', text)
    
    # Remove excessive blank lines (more than 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove trailing whitespace from each line
    text = '\n'.join([line.rstrip() for line in text.split('\n')])
    
    # Remove email markdown formatting
    text = re.sub(r'\[\s*([^\]]+)\]\(mailto:[^)]+\)', r'\1', text)
    
    # Remove link markdown formatting but preserve the URL in parentheses
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
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove empty bullet points
    text = re.sub(r'^\s*-\s*$', '', text, flags=re.MULTILINE)
    
    # Clean up table formatting artifacts
    text = re.sub(r'\|[\s-]*\|', '', text)
    text = re.sub(r'\|\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\|', '', text, flags=re.MULTILINE)
    
    # Remove page breaks and form feeds
    text = re.sub(r'[\f\v]+', '\n', text)
    
    # Final trim and ensure no trailing newlines
    text = text.strip()
    
    return text

def split_into_chunks(text: str, max_chunk_size: int = 1000, overlap: int = 100) -> List[str]:
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

def process_confluence_data(input_file: str, space_name: str = "HIT") -> tuple:
    """Process the confluence data from JSON format (preserves all metadata including authors)"""
    try:
        # Check if it's JSON or CSV and handle accordingly
        if input_file.endswith('.json'):
            # Read the JSON file directly (preserves all metadata)
            with open(input_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            print(f"Loaded {len(json_data)} pages from JSON: {input_file}")
            
            # Convert to our expected format (JSON already has all the fields we need)
            confluence_data = []
            for page in json_data:
                page_data = {
                    'id': str(page.get('id', '')),
                    'title': page.get('title', ''),
                    'url': page.get('url', ''),
                    'space': page.get('space', space_name),
                    'ancestors': page.get('ancestors', ''),
                    'last_updated': page.get('updated', ''),
                    'created': page.get('created', ''),
                    'plain_text': page.get('plain_text', ''),
                    'version': page.get('version', 1),
                    # Preserve author information from JSON export
                    'created_by': page.get('created_by', 'Unknown'),
                    'created_by_email': page.get('created_by_email', ''),
                    'updated_by': page.get('updated_by', 'Unknown'),
                    'updated_by_email': page.get('updated_by_email', ''),
                    'version_by': page.get('version_by', 'Unknown')
                }
                confluence_data.append(page_data)
            
            return confluence_data
            
        else:
            # Legacy CSV processing (for backward compatibility)
            df = pd.read_csv(input_file)
            print(f"Loaded {len(df)} pages from CSV: {input_file}")
            print("⚠️  WARNING: CSV format doesn't contain author information. Use JSON export for complete metadata.")
            
            # Convert to our expected format
            confluence_data = []
            for _, row in df.iterrows():
                page_data = {
                    'id': str(row['id']),
                    'title': row['title'],
                    'url': row['url'] if pd.notna(row['url']) else '',
                    'space': space_name,
                    'ancestors': row['ancestors'] if pd.notna(row['ancestors']) else '',
                    'last_updated': row['updated'] if pd.notna(row['updated']) else '',
                    'plain_text': row['plain_text'] if pd.notna(row['plain_text']) else '',
                    'version': row.get('version', 1),
                    # CSV doesn't have author fields - will show as Unknown
                    'created_by': 'Unknown',
                    'created_by_email': '',
                    'updated_by': 'Unknown', 
                    'updated_by_email': '',
                    'version_by': 'Unknown'
                }
                confluence_data.append(page_data)
            
            return confluence_data
        
    except Exception as e:
        print(f"Error loading Confluence data: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description='Clean and chunk HIT Confluence data')
    parser.add_argument('--input', '-i', default='../extraction/exports/confluence_data_HIT_20250602_155532.json',
                       help='Input JSON file path (preferred) or CSV file path for legacy support')
    parser.add_argument('--space', '-s', default='HIT',
                       help='Space name for the data')
    parser.add_argument('--chunk-size', '-c', type=int, default=1000,
                       help='Maximum chunk size in characters')
    parser.add_argument('--overlap', '-o', type=int, default=100,
                       help='Overlap between chunks in characters')
    
    args = parser.parse_args()
    
    print("=== HIT Confluence Data Cleaning ===")
    print(f"Input file: {args.input}")
    print(f"Space: {args.space}")
    print(f"Chunk size: {args.chunk_size}")
    print(f"Overlap: {args.overlap}")
    print()

    # Load the Confluence data
    confluence_data = process_confluence_data(args.input, args.space)
    if not confluence_data:
        print("No data to process. Exiting.")
        return

    # Process each page
    cleaned_data = []
    pages_with_content = 0

    for page in confluence_data:
        # Clean the plain text
        cleaned_text = clean_text(page.get('plain_text', ''))
        
        # Skip pages with no meaningful content
        if len(cleaned_text.strip()) < 50:  # Skip very short pages
            continue
        
        pages_with_content += 1
        
        # Calculate word and character counts
        word_count = len(cleaned_text.split())
        char_count = len(cleaned_text)
        
        # Create cleaned page record
        cleaned_page = {
            'id': page.get('id', ''),
            'title': page.get('title', ''),
            'url': page.get('url', ''),
            'space': args.space,
            'ancestors': page.get('ancestors', ''),
            'last_updated': page.get('last_updated', ''),
            'created': page.get('created', ''),
            'cleaned_text': cleaned_text,
            # Preserve author information from JSON
            'created_by': page.get('created_by', 'Unknown'),
            'created_by_email': page.get('created_by_email', ''),
            'updated_by': page.get('updated_by', 'Unknown'),
            'updated_by_email': page.get('updated_by_email', ''),
            'version_by': page.get('version_by', 'Unknown'),
            'metadata': {
                'word_count': word_count,
                'char_count': char_count,
                'version': page.get('version', 1)
            }
        }
        
        cleaned_data.append(cleaned_page)
        
    print(f"Processed {len(cleaned_data)} pages with meaningful content (from {len(confluence_data)} total pages).")

    # Create chunked version for RAG
    chunked_data = []

    for page in cleaned_data:
        # Get chunks from the cleaned text
        chunks = split_into_chunks(page['cleaned_text'], 
                                 max_chunk_size=args.chunk_size, 
                                 overlap=args.overlap)
        
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
                    'created_by': page.get('created_by', 'Unknown'),
                    'created_by_email': page.get('created_by_email', ''),
                    'updated_by': page.get('updated_by', 'Unknown'),
                    'updated_by_email': page.get('updated_by_email', ''),
                    'version_by': page.get('version_by', 'Unknown'),
                    'word_count': len(chunk_content.split()),
                    'char_count': len(chunk_content)
                }
            }
            chunked_data.append(chunk)

    print(f"Generated {len(chunked_data)} chunks from {len(cleaned_data)} pages.")

    # Display a comparison of original vs. cleaned text (for the first page)
    if cleaned_data and confluence_data:
        first_page_with_content = next((p for p in confluence_data if len(clean_text(p.get('plain_text', ''))) >= 50), None)
        if first_page_with_content:
            print(f"\n=== Sample: {first_page_with_content['title']} ===")
            print("Original Text Sample (First 200 chars):")
            print(first_page_with_content.get('plain_text', '')[:200] + "...\n")
            
            cleaned_sample = next((p for p in cleaned_data if p['id'] == first_page_with_content['id']), None)
            if cleaned_sample:
                print("Cleaned Text Sample (First 200 chars):")
                print(cleaned_sample.get('cleaned_text', '')[:200] + "...\n")
                
                print("First Chunk (RAG Format):")
                first_chunk = next((chunk for chunk in chunked_data if chunk['page_id'] == cleaned_sample['id'] and chunk['chunk_index'] == 1), None)
                if first_chunk:
                    print(f"Chunk {first_chunk['chunk_index']} of {first_chunk['total_chunks']}")
                    print(first_chunk['content'][:200] + "...\n")

    # Create exports directory if it doesn't exist
    os.makedirs('exports', exist_ok=True)

    # Generate timestamp for filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Export the cleaned data (page level)
    cleaned_file_path = f'exports/{args.space}_confluence_cleaned_{timestamp}.json'
    try:
        with open(cleaned_file_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        print(f"Cleaned data exported to {cleaned_file_path}")
    except Exception as e:
        print(f"Error exporting cleaned data: {e}")

    # Export the chunked data (for RAG)
    chunked_file_path = f'exports/{args.space}_confluence_chunks_{timestamp}.json'
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
        
        print(f"\n=== Data Processing Summary ===")
        print(f"Total pages processed: {len(cleaned_data)}")
        print(f"Total chunks generated: {len(chunked_data)}")
        print(f"Average chunks per page: {df['chunks'].mean():.1f}")
        print(f"Average words per page: {df['word_count'].mean():.1f}")
        print(f"Average words per chunk: {sum(c['metadata']['word_count'] for c in chunked_data) / len(chunked_data):.1f}")
        print(f"Total words in dataset: {df['word_count'].sum():,}")
        
        # Show top pages by content
        print(f"\nTop 10 pages by word count:")
        top_pages = df.nlargest(10, 'word_count')
        for _, row in top_pages.iterrows():
            print(f"- {row['title']}: {row['word_count']} words, {row['chunks']} chunks")
    
    return cleaned_file_path, chunked_file_path

if __name__ == "__main__":
    main() 