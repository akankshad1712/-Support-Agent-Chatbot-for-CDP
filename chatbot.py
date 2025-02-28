# main.py

from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from elasticsearch import Elasticsearch
import requests
from bs4 import BeautifulSoup

app = FastAPI()
es = Elasticsearch("http://localhost:9200")

# OpenAI API Key (Replace with your own)
OPENAI_API_KEY = "your-openai-api-key"

# Documentation URLs
CDP_DOCS = {
    "Segment": "https://segment.com/docs/",
    "mParticle": "https://docs.mparticle.com/",
    "Lytics": "https://docs.lytics.com/",
    "Zeotap": "https://docs.zeotap.com/home/en-us/"
}

# Function to fetch and parse documentation
def fetch_docs(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text()
    return None

# Index documentation in Elasticsearch
def index_document(doc_id, content, source):
    es.index(index="cdp_docs", id=doc_id, body={"text": content, "source": source})

# Scrape and store documentation
def scrape_and_store_docs():
    for idx, (source, url) in enumerate(CDP_DOCS.items(), start=1):
        content = fetch_docs(url)
        if content:
            index_document(idx, content, source)
            print(f"✅ Indexed {source} documentation.")

scrape_and_store_docs()

# Request model for chatbot queries
class QueryRequest(BaseModel):
    question: str

# API Endpoint: Answer "How-to" questions
@app.post("/ask")
async def ask_chatbot(request: QueryRequest):
    query = request.question

    # Search relevant docs from Elasticsearch
    search_results = es.search(index="cdp_docs", body={"query": {"match": {"text": query}}})

    if search_results["hits"]["total"]["value"] > 0:
        best_match = search_results["hits"]["hits"][0]["_source"]["text"]
    else:
        best_match = "I couldn't find relevant information."

    # Use OpenAI to generate a response
    response = OpenAI(api_key=OPENAI_API_KEY).chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a support agent for CDPs."},
            {"role": "user", "content": f"Question: {query}"},
            {"role": "assistant", "content": f"Relevant Docs: {best_match}"}
        ]
    )

    return {"answer": response["choices"][0]["message"]["content"]}

# API Endpoint: Cross-CDP Comparison
@app.post("/compare")
async def compare_cdp_features(request: QueryRequest):
    query = request.question
    sources = ["Segment", "mParticle", "Lytics", "Zeotap"]
    comparisons = {}

    for source in sources:
        search_results = es.search(index="cdp_docs", body={"query": {"match": {"source": source}}})
        if search_results["hits"]["total"]["value"] > 0:
            comparisons[source] = search_results["hits"]["hits"][0]["_source"]["text"]

    return {"comparison": comparisons}

# Run the server with: uvicorn main:app --reload
