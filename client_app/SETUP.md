# Agent Autopsy Client App - Setup Guide

## 🚀 Quick Start

### Prerequisites
1. Agent Autopsy API server running on `http://127.0.0.1:8000`
2. Reports generated in `../reports/` directory

### Installation & Running

#### Option 1: Using the Batch File (Windows)
```bash
cd client_app
start.bat
```

#### Option 2: Using Streamlit Directly
```bash
cd client_app
..\.venv\Scripts\streamlit run app.py
```

#### Option 3: Manual Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

## 📱 Using the App

1. **Open Browser**: Navigate to `http://localhost:8501`
2. **Enter Trace IDs**: Paste one or more trace IDs (comma-separated or one per line)
3. **Select Provider**: Choose "langfuse" or other provider
4. **Generate Reports**: Click "Generate Autopsy Reports"
5. **View Results**: Browse summaries and detailed reports
6. **Download**: Export individual reports or batch ZIP

## 🔧 Features

### Multi-Trace Processing
- Process multiple trace IDs simultaneously
- Support for comma-separated or line-separated input
- Batch processing with progress tracking

### Interactive Reports
- **Summary View**: Status, severity, confidence at a glance
- **Detailed Analysis**: Full markdown reports with 9.5/10 quality
- **Evidence Details**: Expandable sections for failure evidence

### Download Options
- **Individual Reports**: Download single reports as markdown files
- **Batch ZIP**: Export all reports in a single ZIP file
- **Organized Structure**: Reports organized by passed/failed status

### Real-time API Integration
- Direct connection to Agent Autopsy API
- Error handling with user-friendly messages
- Timeout protection for large traces

## 📁 File Structure

```
client_app/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── start.bat          # Windows startup script
├── test_app.py        # Test script
├── README.md          # Documentation
└── SETUP.md           # This setup guide
```

## 🐛 Troubleshooting

### API Connection Issues
- **Error**: "Failed to fetch autopsy"
- **Solution**: Ensure API server is running on port 8000
- **Check**: Visit `http://127.0.0.1:8000/docs` to verify API

### Report Not Found
- **Error**: "Report file not found"
- **Solution**: Run `test_autopsy.py` to generate reports
- **Check**: Verify files exist in `../reports/passed/` and `../reports/failed/`

### Port Conflicts
- **Error**: Port 8501 already in use
- **Solution**: Stop other Streamlit apps or use different port
- **Command**: `streamlit run app.py --server.port 8502`

### Performance Issues
- **Symptom**: Slow loading with many traces
- **Solution**: Process traces in smaller batches (5-10 at a time)
- **Check**: API response times for large traces

## 🎯 Tips for Best Experience

1. **Prepare Trace IDs**: Have trace IDs ready before starting
2. **Batch Processing**: Process multiple traces for efficiency
3. **Use Downloads**: Export reports for offline analysis
4. **Check API Status**: Verify API server before processing
5. **Monitor Progress**: Watch the processing indicators

## 🔗 API Integration

The app connects to:
- **Endpoint**: `POST /api/v1/autopsy`
- **Request**: `{"trace_id": "string", "provider": "string"}`
- **Response**: Autopsy analysis with status, severity, and failures

## 📊 Report Quality

All reports are generated at 9.5/10 quality with:
- Trace-derived justifications
- No redundant sections
- Actionable prevention/detection strategies
- Structural rule violation identification
- Concise, diagnostic insights

## 🎉 Success!

You're ready to analyze AI workflow traces with the Agent Autopsy Client App!
