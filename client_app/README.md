# Agent Autopsy Client App

A Streamlit web interface for analyzing AI workflow traces and generating diagnostic reports with single-trace focus.

## Features

- **Single Trace Analysis**: Analyze one trace at a time for better depth and focus
- **Interactive Reports**: View autopsy summaries and detailed reports
- **Download Options**: Export reports in Markdown or PDF format
- **Real-time API Integration**: Fetches data from Agent Autopsy API
- **Professional UI**: Modern, visually appealing interface with gradient cards
- **PDF Export**: Generate professional formatted reports for sharing

## Setup

### Prerequisites

1. Agent Autopsy API server running on `http://127.0.0.1:8000`
2. Reports generated and available in `../reports/` directory

### Installation

1. Navigate to the client app directory:
   ```bash
   cd client_app
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the App

1. Start the Streamlit app:
   ```bash
   streamlit run app.py
   ```

2. Open your browser and navigate to the URL shown (usually `http://localhost:8501`)

## Usage

1. **Enter Trace ID**: Paste a single trace ID in the sidebar
2. **Select Provider**: Choose the trace provider (default: langfuse)
3. **Generate Report**: Click "Generate Autopsy Report" to fetch and display results
4. **View Results**: Browse the summary and full report
5. **Download**: Export the report in Markdown or PDF format

## API Integration

The client app integrates with the Agent Autopsy API:
- Endpoint: `POST /api/v1/autopsy`
- Request body: `{"trace_id": "trace_id", "provider": "langfuse"}`
- Response: Autopsy analysis data

## File Structure

```
client_app/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── start.bat          # Windows startup script
├── test_app.py        # Test script
├── README.md          # This file
├── SETUP.md           # Setup guide
└── ENHANCEMENTS.md    # Visual and PDF enhancement details
```

## Troubleshooting

### API Connection Issues
- **Error**: "Failed to fetch autopsy"
- **Solution**: Ensure API server is running on port 8000
- **Check**: Visit `http://127.0.0.1:8000/docs` to verify API

### Report Not Found
- **Error**: "Report file not found"
- **Solution**: Run `test_autopsy.py` to generate reports
- **Check**: Verify files exist in `../reports/passed/` and `../reports/failed/`

### PDF Generation Issues
- **Error**: "PDF generation failed"
- **Solution**: Use Markdown download instead
- **Check**: Ensure ReportLab is properly installed

### Port Conflicts
- **Error**: Port 8502 already in use
- **Solution**: Stop other Streamlit apps or use different port
- **Command**: `streamlit run app.py --server.port 8503`

### Sample Trace IDs
Use these to test the application:
- `7ac530db0f09dd7bb0f4cff9ce0165d5` (Failed - Empty Output)
- `a953ab066e2f9b4c40911c35b9b18bbc` (Passed - Correct Query)
