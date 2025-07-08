# Confluence RAG Pipeline

A Retrieval-Augmented Generation (RAG) system that extracts content from Confluence spaces, processes it into searchable chunks, and makes it accessible through a Slack bot powered by OpenAI's ChatGPT.

## Features

- **Automated Confluence Data Extraction**: Pulls content from specified Confluence spaces
- **Intelligent Text Processing**: Cleans and chunks content for optimal retrieval
- **Vector Search**: Uses Pinecone for semantic similarity search
- **Smart Retrieval**: Finds the most relevant information for user queries
- **Slack Integration**: Easy-to-use Slack bot interface
- **Receive AI-generated answers from OpenAI that are grounded in your Confluence content
- **Author & Timestamp Tracking**: Shows who created/updated documents and when

## Project Overview

This project enables teams to:
- Extract content from Confluence knowledge bases
- Process and clean the extracted text
- Create embeddings from the processed text
- Store embeddings in a Pinecone vector database
- Query the knowledge base using natural language through Slack
- Receive AI-generated answers from Claude that are grounded in your Confluence content

## How It Works

1. **Data Extraction**: Retrieves content from specified Confluence spaces using the Confluence API
2. **Text Processing**: Cleans and segments the content into semantically meaningful chunks
3. **Embedding Generation**: Converts text chunks into vector embeddings using SentenceTransformers
4. **Vector Storage**: Uploads embeddings to Pinecone for fast similarity search
5. **Query Processing**: When a user asks a question, the system:
   - Converts the question to a vector embedding
   - Searches Pinecone for the most relevant content chunks
   - Provides context to the OpenAI model
   - Generate a comprehensive answer using OpenAI's ChatGPT
6. **Response Delivery**: Returns a natural language answer grounded in the retrieved Confluence content

## Architecture

The system consists of three main components:

1. **Data Extraction & Processing Pipeline**
   - Pulls content from Confluence via API
   - Cleans and chunks the text
   - Creates embeddings using SentenceTransformer
   - Uploads embeddings to Pinecone

2. **Retrieval System**
   - Queries Pinecone for relevant content based on user questions
   - Provides context to the OpenAI model

3. **Slack Integration**
   - Handles user queries via slash commands, mentions, or direct messages
   - Processes responses asynchronously
   - Returns formatted answers to users

## Setup Instructions

### 1. Environment Setup

```bash
# Clone the repository
git clone [repository-url]
cd confluence_extraction

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the project root with the following variables:

```
# Required API credentials
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_USERNAME=your-email@company.com
CONFLUENCE_API_TOKEN=your-confluence-api-token

# OpenAI API credentials
OPENAI_API_KEY=your-openai-api-key

# Pinecone Vector Database
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=us-west-2

# Optional: Slack Bot credentials (for Slack integration)
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_APP_TOKEN=xapp-your-slack-app-token
```

### 3. Running the Pipeline

Follow these steps in order to set up and run the complete system:

#### Step 1: Extract Content from Confluence

**Option A: Command Line Script (Recommended)**

```bash
# List available spaces
python extraction/confluence_data_extractor.py --list-spaces

# Extract data from a specific space
python extraction/confluence_data_extractor.py --space SPACE_KEY --include-content

# Example with options
python extraction/confluence_data_extractor.py --space Founders --include-content --max-pages 10
```

**Option B: Jupyter Notebook**

Run the Jupyter Notebook (legacy method):

```bash
jupyter notebook extraction/confluence_data_extractor_legacy.ipynb
```

Both methods will create files in the `extraction/exports/` directory.

#### Step 2: Process Content and Create Chunks

Run the cleaning script to process the extracted content:

```bash
python extraction/clean_confluence_data.py
```

This will:
- Clean the raw Confluence text
- Chunk the content into smaller pieces
- Save the chunks to `data_processing/exports/founders_confluence_chunks.json`

#### Step 3: Generate Embeddings

Create embeddings from the processed chunks:

```bash
python data_processing/embedding.py
```

This generates:
- A NumPy file containing the embeddings
- A JSON file with metadata for each embedding

#### Step 4: Initialize Pinecone (First-time only)

If you haven't already set up a Pinecone index:

```bash
python data_processing/initialize_pinecone.py
```

#### Step 5: Upload Embeddings to Pinecone

Upload the generated embeddings to Pinecone:

```bash
python data_processing/pinecone_uploader.py
```

#### Step 6: Start the Slack Bot

Launch the Slack integration to enable user queries:

```bash
python retreiver/slack.py
```

## Usage

Once the system is running, users can interact with the Confluence knowledge base in several ways:

1. **Slash Command**: `/shelby [your question]`
   - Example: `/shelby What is our marketing strategy?`

2. **Mention**: `@Shelby [your question]`
   - Example: `@Shelby What are our pricing tiers?`

3. **Direct Message**: Simply send a message to the bot
   - Example: `How do we handle onboarding for new customers?`

The bot will:
- Acknowledge the query immediately
- Process it in the background
- Retrieve relevant content from Confluence
- Generate a comprehensive answer using Claude AI
- Format and post the response back to the channel/thread

## Project Structure

```
rag_pipeline/
├── extraction/                 # Confluence data extraction
│   ├── confluence_data_extractor.py
│   └── clean_confluence_data.py
├── data_processing/           # Data processing and embeddings
│   ├── clean_hit_confluence_data.py
│   ├── create_hit_embeddings.py
│   └── pinecone_uploader.py
├── retreiver/                 # Retrieval and response generation
│   ├── retrieval.py          # Vector search functionality
│   ├── openai_assistant.py   # Interfaces with OpenAI ChatGPT API
│   └── slack.py              # Slack bot integration
├── exports/                   # Generated data files
└── logs/                      # Application logs
```

## Dependencies

- **Python 3.8+**
- **Confluence API** (for data extraction)
- **Pinecone** (vector database for semantic search)
- **OpenAI API** (for ChatGPT responses)
- **SentenceTransformers** (for text embeddings)
- **LangChain** (for enhanced retrieval capabilities)
- **Slack SDK** (optional, for Slack bot integration)

## Troubleshooting

If you encounter issues with the Slack integration:
- Verify your Slack tokens are correctly configured
- Ensure the bot has been invited to the channels where it's used
- Check the logs in the `logs/` directory for detailed error information
- For direct message issues, try reinstalling the Slack app to refresh permissions

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.