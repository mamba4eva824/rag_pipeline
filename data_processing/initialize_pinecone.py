# Import the Pinecone library
from pinecone import Pinecone
from pinecone import ServerlessSpec
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize a Pinecone client with your API key
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Create a dense index with integrated embedding
index_name = "confluence-embeddings" # Replace with your index name

pc.create_index(
    name=index_name,
    dimension=384, # Replace with your model dimensions
    metric="cosine", # Replace with your model metric
    spec=ServerlessSpec(
        cloud="aws",
        region="us-east-1"
    ) 
)