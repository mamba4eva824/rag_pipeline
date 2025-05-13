# Confluence Knowledge Assistant

A complete RAG (Retrieval-Augmented Generation) pipeline that extracts Confluence knowledge base content, processes it into embeddings, and makes it accessible through a Slack bot powered by Claude AI.

## Project Overview

This project enables teams to:
- Extract content from Confluence knowledge bases
- Process and clean the extracted text
- Create embeddings from the processed text
- Store embeddings in a Pinecone vector database
- Query the knowledge base using natural language through Slack
- Receive AI-generated answers from Claude that are grounded in your Confluence content

## Architecture

The system consists of three main components:

1. **Data Extraction & Processing Pipeline**
   - Pulls content from Confluence via API
   - Cleans and chunks the text
   - Creates embeddings using SentenceTransformer
   - Uploads embeddings to Pinecone

2. **Retrieval System**
   - Queries Pinecone for relevant content based on user questions
   - Provides context to the Claude AI model

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
# Confluence credentials
CONFLUENCE_URL=https://your-instance.atlassian.net
CONFLUENCE_USERNAME=your-email@example.com
CONFLUENCE_API_TOKEN=your-api-token

# Pinecone credentials
PINECONE_API_KEY=your-pinecone-api-key

# Claude API credentials
ANTHROPIC_API_KEY=your-anthropic-api-key

# Slack credentials
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
```

### 3. Running the Pipeline

Follow these steps in order to set up and run the complete system:

#### Step 1: Extract Content from Confluence

Run the Jupyter Notebook to extract data from your Confluence instance:

```bash
jupyter notebook extraction/confluence_data_extractor.ipynb
```

- Set your target Confluence space in the notebook
- Run all cells to extract the content
- This will create files in the `extraction/exports/` directory

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

1. **Slash Command**: `/rovo [your question]`
   - Example: `/rovo What is our marketing strategy?`

2. **Mention**: `@Confluence-Assistant [your question]`
   - Example: `@Confluence-Assistant What are our pricing tiers?`

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
confluence_extraction/
├── data_processing/
│   ├── embedding.py             # Creates embeddings from chunks
│   ├── embedding.txt            # Documentation for embedding process
│   ├── initialize_pinecone.py   # Sets up Pinecone index (first-time)
│   ├── pinecone_uploader.py     # Uploads embeddings to Pinecone
│   └── exports/                 # Stores generated embeddings and metadata
├── extraction/
│   ├── clean_confluence_data.py # Processes raw Confluence content
│   ├── confluence_data_extractor.ipynb # Extracts data from Confluence
│   └── exports/                 # Stores raw extracted data
├── logs/                        # Contains system and interaction logs
├── retreiver/
│   ├── claude.py                # Interfaces with Claude AI API
│   ├── retrieval.py             # Handles retrieving content from Pinecone
│   ├── slack.py                 # Slack bot implementation
│   └── slack.txt                # Documentation for Slack integration
└── .env                         # Environment variables (create this file)
```

## Dependencies

- Python 3.8+
- Jupyter Notebook
- SentenceTransformers
- Pinecone
- Claude AI (Anthropic)
- Slack Bolt SDK
- pandas, numpy, requests, etc.

## Troubleshooting

If you encounter issues with the Slack integration:
- Verify your Slack tokens are correctly configured
- Ensure the bot has been invited to the channels where it's used
- Check the logs in the `logs/` directory for detailed error information
- For direct message issues, try reinstalling the Slack app to refresh permissions

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.