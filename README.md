# Wayback Machine Copilot

Wayback Machine Copilot is an AI assistant designed to explore, summarize, and analyze temporal web data using the Internet Archive's Wayback Machine. It combines LLM tool calling, semantic routing, and CDX index metrics to provide insights into website histories, trend stability, resilience, and archival snapshots.

## Features

- **Historical Snapshot Exploration**: Fetch and view past snapshots of websites directly from the Wayback Machine.
- **Trend & Stability Analysis**: Compute resilience, fixity, and chaos metrics over a domain's lifespan.
- **CDX Index Querying**: Retrieve detailed archive capture metadata across specified date ranges.
- **Semantic Intent Routing**: Automatically identify user intent to route queries to appropriate Wayback APIs.
- **Streamlit Interactive UI**: Intuitive web interface with embedded snapshot views and metric visualization charts.

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Namanv0509/wayback-machine-copilot.git
   cd wayback-machine-copilot
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**:
   Create a `.env` file in the root directory:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

4. **Run the Streamlit application**:
   ```bash
   streamlit run main.py
   ```

## Docker

Build and run using Docker:
```bash
docker build -t wayback-machine-copilot .
docker run -p 8501:8501 -e OPENAI_API_KEY=your_api_key wayback-machine-copilot
```
