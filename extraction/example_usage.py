#!/usr/bin/env python3
"""
Example usage of the ConfluenceExtractor class

This demonstrates how to use the extractor programmatically in your own scripts.
"""

import os
from dotenv import load_dotenv
from confluence_data_extractor import ConfluenceExtractor

def main():
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    confluence_url = os.getenv('CONFLUENCE_URL')
    confluence_username = os.getenv('CONFLUENCE_USERNAME')
    confluence_api_token = os.getenv('CONFLUENCE_API_TOKEN')
    
    if not all([confluence_url, confluence_username, confluence_api_token]):
        print("Please set up your .env file with Confluence credentials")
        return
    
    # Create extractor instance
    extractor = ConfluenceExtractor(confluence_url, confluence_username, confluence_api_token)
    
    # Test connection
    if not extractor.test_connection():
        print("Failed to connect to Confluence")
        return
    
    print("✓ Connected to Confluence successfully!")
    
    # List all spaces
    print("\n--- Available Spaces ---")
    spaces = extractor.get_all_spaces()
    for space in spaces[:5]:  # Show first 5 spaces
        print(f"  {space['key']}: {space['name']}")
    
    # Extract data from a specific space (change this to your space)
    space_key = "Headspace IT"  # Change this to your actual space key
    
    print(f"\n--- Extracting data from space: {space_key} ---")
    df = extractor.extract_confluence_data_to_dataset(
        space_key=space_key,
        include_content=False,  # Set to True if you want content
        max_pages=3  # Limit for example
    )
    
    if not df.empty:
        print(f"\nExtracted {len(df)} pages:")
        print(df[['title', 'type', 'updated']].to_string(index=False))
        
        # Save to CSV
        output_file = f"example_export_{space_key}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n✓ Data saved to {output_file}")
    else:
        print("No data extracted. Check your space key and permissions.")

if __name__ == "__main__":
    main() 