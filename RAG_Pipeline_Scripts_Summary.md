# RAG Pipeline Scripts Summary

## Overview
This document summarizes the complete data processing pipeline for converting Confluence knowledge base content into a RAG (Retrieval-Augmented Generation) system. The pipeline consists of four main phases: extraction, cleaning, chunking, and embedding.

---

## 1. Data Extraction Phase

### Script: `extraction/confluence_data_extractor.py`

**Purpose**: Extract content from Confluence using the REST API and convert it to structured data.

**Key Functions**:

- **`ConfluenceExtractor.__init__()`**: Initialize connection with Confluence credentials
- **`authenticate()`**: Set up HTTP Basic Auth for API requests
- **`get_spaces()`**: Retrieve all available Confluence spaces
- **`get_pages_in_space()`**: Get all pages from a specific space with pagination
- **`get_page_content()`**: Extract detailed content including plain text from individual pages
- **`get_page_ancestors()`**: Build hierarchical path (breadcrumb) for each page
- **`extract_space_data()`**: Orchestrate full extraction process for a space
- **`export_to_csv()`**: Save extracted data to CSV format

**Key Features**:
- Command-line interface with options for space selection, content inclusion, pagination
- Hierarchical structure preservation (parent > child > grandchild)
- Rate limiting and error handling for API requests
- Progress tracking with detailed output
- Flexible export options (CSV, with/without content)

**Input**: Confluence space key (e.g., "HIT")
**Output**: CSV file with page metadata, content, and hierarchy

**Example Usage**:
```bash
python confluence_data_extractor.py --space HIT --include-content
```

---

## 2. Data Processing & Cleaning Phase

### Script: `data_processing/clean_hit_confluence_data.py`

**Purpose**: Clean raw Confluence text and prepare it for embedding by removing artifacts and formatting consistently.

**Key Functions**:

- **`clean_text()`**: Core text cleaning function
  - Remove HTML artifacts and Confluence-specific formatting
  - Standardize bullet points and heading formats
  - Clean up table formatting and excessive whitespace
  - Remove email/link markdown while preserving URLs
  - Filter out empty content and page breaks

- **`split_into_chunks()`**: Intelligent text chunking
  - Split text into 1000-character chunks with 100-character overlap
  - Preserve paragraph and sentence boundaries
  - Handle overlap at sentence boundaries for context continuity
  - Manage large paragraphs by splitting at sentence level

- **`process_confluence_data()`**: Convert CSV to internal format
  - Read CSV data and normalize column names
  - Handle missing values and data type conversion
  - Create standardized page objects

- **`main()`**: Orchestrate the cleaning pipeline
  - Load and process all pages
  - Filter out pages with minimal content (<50 characters)
  - Generate both cleaned pages and chunks
  - Export results with timestamps
  - Provide detailed processing statistics

**Key Features**:
- Configurable chunk size and overlap parameters
- Content quality filtering (removes very short pages)
- Comprehensive text cleaning with regex-based processing
- Detailed analytics and reporting
- Preserves page hierarchy and metadata

**Input**: CSV file from extractor (e.g., `confluence_data_HIT_20250528_153131.csv`)
**Output**: 
- Cleaned page data: `HIT_confluence_cleaned_TIMESTAMP.json`
- Chunked data: `HIT_confluence_chunks_TIMESTAMP.json`

**Processing Results**:
- 508 pages → 450 meaningful pages → 1,465 chunks
- Average 3.3 chunks per page, 112 words per chunk
- Total: 159,315 words processed

---

## 3. Embedding Generation Phase

### Script: `data_processing/create_hit_embeddings.py`

**Purpose**: Convert text chunks into high-dimensional vector embeddings using SentenceTransformers.

**Key Functions**:

- **`find_latest_chunks_file()`**: Automatically locate the most recent chunks file
- **`load_chunks()`**: Load and validate chunk data from JSON
- **`create_embeddings()`**: Core embedding generation
  - Load SentenceTransformers model (all-MiniLM-L6-v2)
  - Process text in optimized batches (batch_size=32)
  - Generate 384-dimensional embeddings
  - Handle GPU/CPU device selection automatically
  - Create comprehensive metadata for each embedding

- **`save_embeddings()`**: Persist embeddings and metadata
  - Save embeddings as numpy arrays (.npy format)
  - Save metadata as structured JSON
  - Include timestamps in filenames

- **`analyze_embeddings()`**: Provide dataset analysis
  - Calculate memory usage and dimension statistics
  - Analyze content distribution by pages/spaces
  - Report word/character counts
  - Identify top content contributors

**Key Features**:
- Automatic model loading and device optimization
- Batch processing for memory efficiency
- Progress tracking with tqdm
- Comprehensive metadata preservation
- Detailed analytics and quality metrics

**Input**: Chunked JSON data from cleaning phase
**Output**:
- Vector embeddings: `HIT_confluence_embeddings_TIMESTAMP.npy`
- Metadata: `HIT_confluence_embedding_metadata_TIMESTAMP.json`

**Results**:
- 1,465 embeddings generated (384 dimensions each)
- 164,166 words embedded
- 2.15 MB memory footprint
- Ready for vector database upload

---

## 4. Pipeline Integration & Data Flow

### Overall Architecture

```
Confluence API → CSV Extract → Text Cleaning → Chunking → Embeddings → Pinecone
     ↓              ↓             ↓            ↓          ↓
Raw Confluence → Structured → Clean Text → Chunks → Vectors → Vector DB
   Content       Data (CSV)   (JSON)      (JSON)   (NumPy)
```

### Data Transformations

1. **Extraction**: 508 raw Confluence pages → Structured CSV with hierarchy
2. **Cleaning**: 508 pages → 450 meaningful pages (filtered)
3. **Chunking**: 450 pages → 1,465 text chunks (with overlap)
4. **Embedding**: 1,465 chunks → 1,465 vector embeddings (384-dim)

### Key Design Principles

- **Modularity**: Each script handles one phase, can be run independently
- **Configurability**: Command-line arguments for key parameters
- **Data Preservation**: Maintains hierarchy, metadata, and traceability
- **Quality Control**: Filtering, validation, and comprehensive reporting
- **Efficiency**: Batch processing, memory optimization, progress tracking

### File Naming Convention

All scripts use timestamped filenames to prevent overwrites and maintain version history:
- `confluence_data_HIT_YYYYMMDD_HHMMSS.csv`
- `HIT_confluence_cleaned_YYYYMMDD_HHMMSS.json`
- `HIT_confluence_chunks_YYYYMMDD_HHMMSS.json`
- `HIT_confluence_embeddings_YYYYMMDD_HHMMSS.npy`

### Quality Metrics

- **Extraction**: 508 pages successfully extracted with full hierarchy
- **Cleaning**: 88.6% retention rate (450/508 pages with meaningful content)
- **Chunking**: Optimal chunk size for semantic coherence (112 avg words/chunk)
- **Embedding**: High-quality 384-dimensional vectors ready for similarity search

---

## 5. Supporting Infrastructure

### Dependencies Management
- Virtual environment with pinned package versions
- Requirements.txt with all necessary libraries
- Cross-platform compatibility (macOS, Linux, Windows)

### Configuration Management
- Environment variables for credentials (.env file)
- Command-line interfaces for all scripts
- Sensible defaults with override options

### Error Handling & Monitoring
- Comprehensive error catching and reporting
- Progress bars and status updates
- Detailed logging and analytics output
- Graceful handling of API rate limits and network issues

### Next Phase: Vector Database Upload
The pipeline outputs are optimized for upload to Pinecone vector database:
- Embeddings in efficient NumPy format
- Rich metadata for filtering and retrieval
- Chunk-level granularity for precise matching
- Hierarchical information preserved for context

This completes the preprocessing pipeline, transforming unstructured Confluence knowledge into a searchable vector database ready for RAG applications. 