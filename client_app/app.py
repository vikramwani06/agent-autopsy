"""Complete app.py with all fixes for clean UI without error messages"""

import streamlit as st
import httpx
import pandas as pd
import base64
import io
import json
import markdown
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# Set page config
st.set_page_config(
    page_title="Agent Autopsy",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for enhanced UI
st.markdown("""
<style>
    /* Main theme improvements */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        color: #1f2937;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: all 0.2s ease;
        border: 1px solid #e5e7eb;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    }
    
    .status-pass::before {
        background: linear-gradient(90deg, #10b981, #059669);
    }
    
    .status-fail::before {
        background: linear-gradient(90deg, #ef4444, #dc2626);
    }
    
    .severity-critical::before {
        background: linear-gradient(90deg, #dc2626, #991b1b);
    }
    
    .severity-high::before {
        background: linear-gradient(90deg, #f59e0b, #d97706);
    }
    
    .severity-medium::before {
        background: linear-gradient(90deg, #3b82f6, #2563eb);
    }
    
    .severity-low::before {
        background: linear-gradient(90deg, #8b5cf6, #7c3aed);
    }
    
    .sidebar-header {
        background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        text-align: center;
    }
    
    .download-button {
        background: white;
        color: #374151;
        padding: 0.75rem 1.25rem;
        border: 1px solid #d1d5db;
        border-radius: 0.5rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    }
    
    .download-button:hover {
        background: #f9fafb;
        border-color: #9ca3af;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    .download-button::before {
        content: '⬇';
        font-size: 1.2rem;
        margin-right: 0.25rem;
    }
    
    /* Streamlit specific overrides */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 0.5rem;
        font-weight: 600;
        padding: 0.75rem 1.5rem;
        transition: all 0.2s ease;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        transform: translateY(-1px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
    
    /* Improve expander styling */
    .streamlit-expanderHeader {
        background-color: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        padding: 0.75rem 1rem;
        font-weight: 600;
    }
    
    .streamlit-expanderContent {
        border: 1px solid #e5e7eb;
        border-top: none;
        border-radius: 0 0 0.5rem 0.5rem;
        padding: 1rem;
        background-color: #fafafa;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        padding: 0.25rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 0.375rem;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    .stTextArea > div > div {
        border-radius: 0.5rem;
        border: 2px solid #e5e7eb;
    }
    
    .stSelectbox > div > div {
        border-radius: 0.5rem;
        border: 2px solid #e5e7eb;
    }
    
    .stExpander {
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }

    /* Tool Call Card Styles */
    .tool-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 0.75rem;
        padding: 1.5rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s ease;
    }
    .tool-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .tool-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
    }
    .tool-card-title {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .tool-card-number {
        background: #f3f4f6;
        color: #6b7280;
        font-size: 0.75rem;
        font-weight: 600;
        width: 1.75rem;
        height: 1.75rem;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .tool-card-name {
        font-size: 1rem;
        font-weight: 600;
        color: #1f2937;
    }
    .tool-badge {
        background: #eff6ff;
        color: #3b82f6;
        font-size: 0.65rem;
        font-weight: 600;
        padding: 0.2rem 0.5rem;
        border-radius: 0.25rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .tool-card-parent {
        font-size: 0.75rem;
        color: #9ca3af;
        margin-top: 0.125rem;
    }
    .tool-card-duration {
        background: #f0fdf4;
        color: #16a34a;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
    }
    .tool-card-duration.error {
        background: #fef2f2;
        color: #dc2626;
    }
    .tool-io-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.375rem;
    }
    .tool-io-block {
        background: #1e293b;
        color: #5eead4;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.8rem;
        padding: 0.875rem 1rem;
        border-radius: 0.5rem;
        white-space: pre-wrap;
        word-break: break-word;
        line-height: 1.5;
        border-left: 3px solid #3b82f6;
    }
    .tool-io-block.output {
        border-left-color: #10b981;
    }
    .tool-io-block.error-block {
        border-left-color: #ef4444;
        color: #fca5a5;
    }
    .copy-json-btn {
        font-size: 0.7rem;
        color: #3b82f6;
        cursor: pointer;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .total-calls-badge {
        background: #f3f4f6;
        color: #6b7280;
        font-size: 0.8rem;
        font-weight: 500;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
    }

    /* Planner Decision Styles */
    .planner-section-label {
        font-size: 0.7rem;
        font-weight: 700;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.375rem;
    }
    .planner-section-label::before {
        content: '';
        width: 3px;
        height: 1rem;
        background: #3b82f6;
        border-radius: 2px;
    }
    .planner-input-box {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        padding: 1rem 1.25rem;
        font-size: 0.9rem;
        color: #374151;
        line-height: 1.6;
        margin-bottom: 1.25rem;
    }
    .planner-reasoning-box {
        background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
        border-radius: 0.75rem;
        padding: 1.25rem 1.5rem;
        color: white;
        margin-bottom: 1.25rem;
    }
    .planner-reasoning-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        opacity: 0.8;
        margin-bottom: 0.25rem;
    }
    .planner-reasoning-agent {
        display: inline-block;
        background: rgba(255,255,255,0.2);
        color: white;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.2rem 0.6rem;
        border-radius: 0.25rem;
        margin-bottom: 0.75rem;
    }
    .planner-reasoning-text {
        font-size: 0.9rem;
        line-height: 1.6;
    }
    .model-info-box {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        overflow: hidden;
    }
    .model-info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.625rem 1rem;
        border-bottom: 1px solid #f3f4f6;
    }
    .model-info-row:last-child {
        border-bottom: none;
    }
    .model-info-key {
        font-size: 0.8rem;
        color: #6b7280;
    }
    .model-info-value {
        font-size: 0.8rem;
        font-weight: 600;
        color: #1f2937;
    }
    .model-info-value.highlight {
        color: #3b82f6;
    }
    .capability-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 0.375rem;
        padding: 0.375rem 0.75rem;
        font-size: 0.8rem;
        color: #374151;
        margin: 0.25rem;
    }
    .capability-chip::before {
        content: '\1F527';
        font-size: 0.7rem;
    }
    .active-badge {
        background: #eff6ff;
        color: #3b82f6;
        font-size: 0.7rem;
        font-weight: 600;
        padding: 0.3rem 0.75rem;
        border-radius: 1rem;
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
    }
    .active-badge::before {
        content: '\2714';
    }
    .tools-count-badge {
        background: #f3f4f6;
        color: #6b7280;
        font-size: 0.65rem;
        font-weight: 600;
        padding: 0.15rem 0.5rem;
        border-radius: 0.25rem;
    }
    .step-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }
    .step-card-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .step-number {
        background: #eff6ff;
        color: #3b82f6;
        font-size: 0.7rem;
        font-weight: 700;
        width: 1.5rem;
        height: 1.5rem;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .step-action {
        font-weight: 600;
        color: #1f2937;
        font-size: 0.9rem;
    }
    .step-tools {
        display: flex;
        gap: 0.375rem;
        flex-wrap: wrap;
        margin-top: 0.375rem;
    }
    .step-tool-chip {
        background: #f0fdf4;
        color: #16a34a;
        font-size: 0.7rem;
        font-weight: 600;
        padding: 0.15rem 0.5rem;
        border-radius: 0.25rem;
    }
    .decision-branch {
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-radius: 0.5rem;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
API_BASE = "http://127.0.0.1:8000"

def get_available_sample_traces():
    """Return hardcoded sample traces for demonstration"""
    return [
        {
            "trace_id": "7ac530db0f09dd7bb0f4cff9ce0165d5",
            "status": "Failed",
            "description": "Detected issues - False terminal success with empty output"
        },
        {
            "trace_id": "a953ab066e2f9b4c40911c35b9b18bbc",
            "status": "Passed", 
            "description": "No issues detected - Correct execution"
        },
        {
            "trace_id": "b448b0904d18d5a59d87df8cfcac4bc9",
            "status": "Failed",
            "description": "Wrong tool usage - Semantically incorrect response"
        }
    ]

def fetch_autopsy(trace_id: str, provider: str = "langfuse") -> dict:
    """Fetch autopsy data from the API"""
    try:
        # Show loading toast
        st.toast("Fetching trace data...", icon="⏳")
        
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{API_BASE}/api/v1/autopsy",
                json={"trace_id": trace_id, "provider": provider}
            )
            
            # Handle different HTTP status codes
            if response.status_code == 404:
                st.toast(f"Trace not found: {trace_id}", icon="❌")
                return None
            elif response.status_code == 400:
                st.toast(f"Invalid request: {response.json().get('message', 'Bad request')}", icon="⚠️")
                return None
            elif response.status_code == 500:
                st.toast("Server error: Please try again later", icon="❌")
                return None
            elif response.status_code != 200:
                st.toast(f"Error {response.status_code}: {response.reason_phrase}", icon="❌")
                return None
                
            data = response.json()
            
            # Check if enhanced_data is present
            if "enhanced_data" not in data:
                st.toast("Enhanced visualization data not available", icon="⚠️")
            else:
                st.toast("Data loaded successfully!", icon="✅")
                
            return data
            
    except httpx.TimeoutException:
        st.toast("Request timed out. Please try again.", icon="⏱️")
        return None
    except httpx.ConnectError:
        st.toast("Cannot connect to API. Is the backend running?", icon="🔌")
        return None
    except httpx.HTTPError as e:
        st.toast(f"HTTP error: {str(e)}", icon="❌")
        return None
    except Exception as e:
        st.toast(f"Unexpected error: {str(e)}", icon="❌")
        return None

def get_report_content_from_api(autopsy_data: dict) -> str:
    """Extract report content from API response"""
    try:
        result_data = autopsy_data.get("result", {})
        report_data = autopsy_data.get("report", {})
        
        if not result_data and not report_data:
            return None
        
        # Build markdown report from API response
        report_sections = []
    
    # Add header with basic info
        trace_id = result_data.get("trace_id", "Unknown")
        status = result_data.get("status", "unknown")
        severity = result_data.get("overall_severity", "unknown")
        confidence = result_data.get("confidence", 0)
        
        status_icon = "✅" if status == "pass" else "❌"
        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
        
        report_sections.append(f"# Agent Autopsy Report")
        report_sections.append(f"\n**Trace ID:** `{trace_id}`")
        report_sections.append(f"**Status:** {status_icon} {status.upper()}")
        report_sections.append(f"**Severity:** {severity_icon} {severity.upper()}")
        report_sections.append(f"**Confidence:** {confidence * 100:.0f}%")
        
        # Add summary from report
        summary = report_data.get("summary", "")
        if summary:
            report_sections.append(f"\n## 📋 Executive Summary\n\n{summary}")
        
        # Add detected failures
        primary_failures = result_data.get("primary_failures", [])
        if primary_failures:
            report_sections.append(f"\n## 🚨 Primary Failures")
            for i, failure in enumerate(primary_failures, 1):
                failure_type = failure.get("failure_type", "Unknown")
                failure_severity = failure.get("severity", "unknown")
                failure_desc = failure.get("description", "No description")
                failure_confidence = failure.get("confidence", 0)
                
                severity_badge = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(failure_severity, "⚪")
                
                failure_title = failure.get("title", failure_type)
                report_sections.append(f"\n### {i}. {failure_title} - {severity_badge} {failure_severity.upper()}")
                report_sections.append(f"**Confidence:** {failure_confidence * 100:.0f}%")
                
                failure_explanation = failure.get("explanation", "")
                if failure_explanation:
                    report_sections.append(f"**Explanation:** {failure_explanation}")
                
                # Add evidence if available
                evidence = failure.get("evidence", [])
                if evidence:
                    report_sections.append(f"**Evidence:**")
                    if isinstance(evidence, list):
                        for item in evidence:
                            if isinstance(item, dict):
                                desc = item.get("description", "")
                                if desc:
                                    report_sections.append(f"- {desc}")
                                details = item.get("details", {})
                                if isinstance(details, dict):
                                    for dk, dv in details.items():
                                        report_sections.append(f"  - **{dk}:** {dv}")
                            else:
                                report_sections.append(f"- {item}")
                    elif isinstance(evidence, dict):
                        for key, value in evidence.items():
                            report_sections.append(f"- **{key}:** {value}")
                    else:
                        report_sections.append(f"- {evidence}")
        
        # Add secondary failures
        secondary_failures = result_data.get("secondary_failures", [])
        if secondary_failures:
            report_sections.append(f"\n## ⚠️ Secondary Failures")
            for i, failure in enumerate(secondary_failures, 1):
                failure_type = failure.get("failure_type", "Unknown")
                failure_severity = failure.get("severity", "unknown")
                failure_desc = failure.get("description", "No description")
                
                severity_badge = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(failure_severity, "⚪")
                
                failure_title = failure.get("title", failure_type)
                report_sections.append(f"\n### {i}. {failure_title} - {severity_badge} {failure_severity.upper()}")
                failure_explanation = failure.get("explanation", "")
                if failure_explanation:
                    report_sections.append(f"**Explanation:** {failure_explanation}")
                
                # Add evidence
                evidence = failure.get("evidence", [])
                if evidence and isinstance(evidence, list):
                    report_sections.append(f"**Evidence:**")
                    for item in evidence:
                        if isinstance(item, dict):
                            desc = item.get("description", "")
                            if desc:
                                report_sections.append(f"- {desc}")
                        else:
                            report_sections.append(f"- {item}")
        
        # Add detailed explanations from report
        primary_explanation = report_data.get("primary_failure_explanation", "")
        if primary_explanation:
            report_sections.append(f"\n## 📊 Detailed Analysis\n\n{primary_explanation}")
        
        secondary_explanation = report_data.get("secondary_failure_explanations", "")
        if secondary_explanation:
            report_sections.append(f"\n## 📈 Additional Findings\n\n{secondary_explanation}")
        
        # Add root cause analysis
        root_cause = report_data.get("root_cause_analysis", "")
        if root_cause:
            report_sections.append(f"\n## 🔍 Root Cause Analysis\n\n{root_cause}")
        
        # Add suggested fixes
        fixes = report_data.get("suggested_fixes", "")
        if fixes:
            report_sections.append(f"\n## 🛠️ Recommended Actions\n\n{fixes}")
    
    # Add execution details
        total_spans = result_data.get("total_spans_analyzed", 0)
        detectors_run = result_data.get("detectors_run", [])
        
        report_sections.append(f"\n## 📈 Execution Details")
        report_sections.append(f"**Spans Analyzed:** {total_spans}")
        report_sections.append(f"**Detectors Run:** {', '.join(detectors_run) if detectors_run else 'None'}")
        
        # Add LLM explanation if available
        llm_explanation = autopsy_data.get("llm_explanation")
        if llm_explanation:
            report_sections.append(f"\n## 🤖 AI Explanation\n\n{llm_explanation}")
        
        return "\n".join(report_sections) if report_sections else None
        
    except Exception as e:
        # Fallback to basic report if there's an error
        return f"# Error Generating Report\n\nAn error occurred while generating the report: {str(e)}"


def markdown_to_pdf_html(markdown_content: str) -> str:
    """Convert markdown to HTML with styling for PDF"""
    # Convert markdown to HTML
    html_content = markdown.markdown(markdown_content, extensions=['tables', 'fenced_code'])
    
    # Add CSS styling for PDF
    pdf_css = """
    <style>
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #1f2937;
            margin-top: 1.5em;
            margin-bottom: 0.8em;
            font-weight: 600;
        }
        h1 {
            font-size: 24pt;
            text-align: center;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 0.5em;
            margin-bottom: 1em;
        }
        h2 {
            font-size: 18pt;
            border-bottom: 1px solid #e5e7eb;
            padding-bottom: 0.3em;
        }
        h3 {
            font-size: 14pt;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
        }
        th, td {
            border: 1px solid #d1d5db;
            padding: 8px 12px;
            text-align: left;
        }
        th {
            background-color: #f3f4f6;
            font-weight: 600;
        }
        code {
            background-color: #f3f4f6;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 10pt;
        }
        pre {
            background-color: #f9fafb;
            border: 1px solid #e5e7eb;
            padding: 1em;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 9pt;
        }
        blockquote {
            border-left: 4px solid #3b82f6;
            margin: 1em 0;
            padding-left: 1em;
            color: #6b7280;
            font-style: italic;
        }
        .metadata {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 1em;
            border-radius: 4px;
            margin: 1em 0;
        }
        .severity-critical { color: #dc2626; font-weight: bold; }
        .severity-high { color: #f59e0b; font-weight: bold; }
        .severity-medium { color: #3b82f6; font-weight: bold; }
        .severity-low { color: #8b5cf6; font-weight: bold; }
        .status-pass { color: #10b981; font-weight: bold; }
        .status-fail { color: #ef4444; font-weight: bold; }
    </style>
    """
    
    # Create complete HTML document
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Agent Autopsy Report</title>
        {pdf_css}
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    return full_html

def create_pdf_from_markdown(markdown_content: str, trace_id: str) -> bytes:
    """Convert markdown content to PDF using ReportLab"""
    try:
        # Create PDF buffer
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Create custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor('#1f2937')
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=HexColor('#374151')
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            leading=16,
            textColor=HexColor('#4b5563')
        )
        
        # Build PDF content
        story = []
        
        # Add title
        story.append(Paragraph("Agent Autopsy Report", title_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Trace ID: {trace_id}", heading_style))
        story.append(Spacer(1, 20))
        
        # Process markdown content
        lines = markdown_content.split('\n')
        current_section = []
        code_block = False
        
        for line in lines:
            line = line.rstrip()
            
            # Handle code blocks
            if line.startswith('```'):
                if code_block:
                    # End code block - add as preformatted text
                    if current_section:
                        code_text = '\n'.join(current_section)
                        # Add code block with monospace font
                        code_style = ParagraphStyle(
                            'Code',
                            parent=styles['Normal'],
                            fontSize=9,
                            fontName='Courier',
                            leftIndent=20,
                            rightIndent=20,
                            backColor=HexColor('#f3f4f6'),
                            borderColor=HexColor('#d1d5db'),
                            borderWidth=1,
                            spaceAfter=12,
                            spaceBefore=12
                        )
                        story.append(Paragraph(code_text, code_style))
                    current_section = []
                    code_block = False
                else:
                    # Start code block
                    code_block = True
                continue
            
            if code_block:
                current_section.append(line)
                continue
            
            # Handle headers
            if line.startswith('# '):
                if current_section:
                    story.append(Paragraph(' '.join(current_section), body_style))
                    current_section = []
                story.append(Paragraph(line[2:], heading_style))
            elif line.startswith('## '):
                if current_section:
                    story.append(Paragraph(' '.join(current_section), body_style))
                    current_section = []
                story.append(Paragraph(line[3:], heading_style))
            elif line.startswith('### '):
                if current_section:
                    story.append(Paragraph(' '.join(current_section), body_style))
                    current_section = []
                story.append(Paragraph(line[4:], heading_style))
            # Handle horizontal rules
            elif line.strip() == '---':
                if current_section:
                    story.append(Paragraph(' '.join(current_section), body_style))
                    current_section = []
                story.append(Spacer(1, 20))
            # Handle empty lines
            elif not line.strip():
                if current_section:
                    story.append(Paragraph(' '.join(current_section), body_style))
                    current_section = []
                story.append(Spacer(1, 6))
            # Regular text
            else:
                # Clean up markdown formatting
                clean_line = line.replace('**', '').replace('*', '').replace('`', '')
                current_section.append(clean_line)
        
        # Add any remaining content
        if current_section:
            story.append(Paragraph(' '.join(current_section), body_style))
        
        # Build PDF
        doc.build(story)
        
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    except Exception as e:
        st.toast(f"Error generating PDF: {str(e)}", icon="⚠️")
        return None


def display_autopsy_summary(autopsy_data: dict, trace_id: str):
    """Display a summary of the autopsy results with enhanced styling"""
    # Extract data from the nested result structure
    result_data = autopsy_data.get("result", {})
    status = result_data.get("status", "unknown")
    severity = result_data.get("overall_severity", "unknown")
    confidence = result_data.get("confidence", 0)
    
    # Create styled metric cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_class = "status-pass" if status == "pass" else "status-fail"
        status_icon = "✓" if status == "pass" else "✗"
        st.markdown(f"""
        <div class="metric-card {status_class}">
            <div style="font-size: 1.5rem; margin-bottom: 0.25rem;">{status_icon}</div>
            <div style="font-size: 0.75rem; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">Status</div>
            <div style="font-size: 1.25rem; font-weight: 700; margin-top: 0.125rem;">{status.upper()}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        severity_class = f"severity-{severity}" if severity in ["critical", "high", "medium", "low"] else "severity-medium"
        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
        st.markdown(f"""
        <div class="metric-card {severity_class}">
            <div style="font-size: 1.5rem; margin-bottom: 0.25rem;">{severity_icon}</div>
            <div style="font-size: 0.75rem; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">Severity</div>
            <div style="font-size: 1.25rem; font-weight: 700; margin-top: 0.125rem;">{severity.upper()}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        confidence_icon = "📊" if confidence > 0.8 else "📈" if confidence > 0.5 else "📉"
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 1.5rem; margin-bottom: 0.25rem;">{confidence_icon}</div>
            <div style="font-size: 0.75rem; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;">Confidence</div>
            <div style="font-size: 1.25rem; font-weight: 700; margin-top: 0.125rem;">{confidence * 100:.0f}%</div>
        </div>
        """, unsafe_allow_html=True)


def _calculate_max_depth(spans: list) -> int:
    """Calculate the maximum depth of the span hierarchy."""
    if not spans:
        return 0
    
    # Build parent-child map
    children_map = {}
    root_spans = []
    
    for span in spans:
        span_id = span.get("span_id")
        parent_id = span.get("parent_span_id")
        
        if parent_id:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(span_id)
        else:
            root_spans.append(span_id)
    
    # Recursive depth calculation
    def get_depth(span_id):
        children = children_map.get(span_id, [])
        if not children:
            return 1
        return 1 + max(get_depth(child_id) for child_id in children)
    
    if not root_spans:
        return 0
    
    return max(get_depth(root_id) for root_id in root_spans)


def _extract_workflow_steps_from_autopsy(autopsy_data: dict) -> list[dict]:
    """Extract workflow steps from autopsy data."""
    steps = []
    
    # Try to extract from enhanced data trace
    if autopsy_data.get("enhanced_data") and autopsy_data["enhanced_data"].get("trace"):
        trace = autopsy_data["enhanced_data"]["trace"]
        if "spans" in trace:
            all_spans = trace.get("spans", [])
            # Find root chain spans
            root_chains = [s for s in all_spans if s.get("span_type") == "chain" and not s.get("parent_span_id")]
            
            # If there's a single root chain, show its children as the workflow steps
            if len(root_chains) == 1:
                root_id = root_chains[0].get("span_id")
                child_chains = [
                    s for s in all_spans
                    if s.get("parent_span_id") == root_id and s.get("span_type") == "chain"
                ]
                # Sort by start_time
                child_chains.sort(key=lambda s: s.get("start_time", ""))
                target_spans = child_chains if child_chains else root_chains
            else:
                target_spans = root_chains
            
            for span in target_spans:
                has_error = span.get("error") or span.get("level") == "ERROR"
                status = "Error" if has_error else "Success"
                status_icon = "❌" if has_error else "✅"
                steps.append({
                    "Step": len(steps) + 1,
                    "Name": span.get("name", "Unknown"),
                    "Type": span.get("span_type", "chain"),
                    "Duration": f"{span.get('duration_ms', 0):.0f}ms" if span.get("duration_ms") else "N/A",
                    "Status": f"{status_icon} {status}",
                    "Children": len([s for s in all_spans if s.get("parent_span_id") == span.get("span_id")])
                })
    
    return steps


def _extract_detailed_tool_calls(autopsy_data: dict) -> list[dict]:
    """Extract detailed tool call information from enhanced_data.tool_calls.

    The backend now extracts, deduplicates, and returns tool calls directly
    in enhanced_data.tool_calls, so we use that as the primary source.
    """
    ed = autopsy_data.get("enhanced_data") or {}
    tool_calls = ed.get("tool_calls", [])
    if isinstance(tool_calls, list) and tool_calls:
        return tool_calls
    return []


def _extract_detailed_planner_info(autopsy_data: dict) -> dict:
    """Extract detailed planner information from enhanced_data.planner_decision.

    The backend now extracts the full plan, decisions, analysis, model info,
    and query directly in enhanced_data.planner_decision.
    """
    ed = autopsy_data.get("enhanced_data") or {}
    pd = ed.get("planner_decision") or {}
    if isinstance(pd, dict) and any(pd.values()):
        return pd
    return {}


def _build_execution_tree_from_autopsy(autopsy_data: dict) -> dict:
    """Build execution tree from autopsy data."""
    # Try to get from the enhanced report data
    if autopsy_data.get("enhanced_data") and autopsy_data["enhanced_data"].get("execution_tree"):
        return autopsy_data["enhanced_data"]["execution_tree"]
    
    # If not available, return empty
    return {}


def display_execution_tree(tree: dict, level: int = 0):
    """Display execution tree recursively."""
    if not tree:
        return
    
    # Indent based on level
    indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * level
    
    # Display current node
    with st.container():
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"{indent}🔗 {tree.get('name', 'Unknown')}")
        
        with col2:
            st.markdown(f"{tree.get('type', '').upper()}")
        
        with col3:
            st.markdown(f"{tree.get('duration', 'N/A')}")
    
    # Recursively display children
    for child in tree.get('children', []):
        display_execution_tree(child, level + 1)


def display_workflow_visualization(autopsy_data: dict):
    """Display enhanced workflow visualization with tabs."""
    if not autopsy_data:
        st.toast("No autopsy data available for visualization", icon="⚠️")
        return
    
    # Check if enhanced_data exists
    if "enhanced_data" not in autopsy_data:
        st.toast("Enhanced visualization data not available", icon="⚠️")
        return
    
    enhanced_data = autopsy_data.get("enhanced_data", {})
    
    if not enhanced_data:
        st.toast("Enhanced data is empty", icon="⚠️")
        return
    
    st.markdown("---")
    st.markdown("### 📊 Workflow Execution Visualization")
    
    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["📋 Overview", "⚡ Workflow Execution", "🌳 Execution Tree"])
    
    with tab1:
        st.markdown("#### Execution Overview")
        
        # Extract basic info
        result_data = autopsy_data.get("result", {})
        trace_data = autopsy_data.get("trace", {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Trace Information:**")
            st.json({
                "Trace ID": result_data.get("trace_id", "Unknown"),
                "Status": result_data.get("status", "unknown").upper(),
                "Severity": result_data.get("overall_severity", "unknown").upper(),
                "Confidence": f"{result_data.get('confidence', 0) * 100:.0f}%",
                "Total Spans": result_data.get("total_spans_analyzed", 0)
            })
        
        with col2:
            st.markdown("**Workflow Steps:**")
            # Extract actual steps from trace
            steps = _extract_workflow_steps_from_autopsy(autopsy_data)
            if steps:
                df_steps = pd.DataFrame(steps)
                st.dataframe(df_steps, use_container_width=True, hide_index=True)
            else:
                st.markdown("*No step data available*")
        
        # Show trace structure summary
        if autopsy_data.get("enhanced_data") and autopsy_data["enhanced_data"].get("trace"):
            trace = autopsy_data["enhanced_data"]["trace"]
            spans = trace.get("spans", [])
            
            st.markdown("#### Trace Structure Analysis")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Count span types
                span_types = {}
                for span in spans:
                    span_type = span.get("span_type", "unknown")
                    span_types[span_type] = span_types.get(span_type, 0) + 1
                
                st.markdown("**Span Types:**")
                for span_type, count in span_types.items():
                    st.markdown(f"- {span_type}: {count}")
            
            with col2:
                # Find unique operations
                operations = set()
                for span in spans:
                    name = span.get("name", "")
                    if name and name != "LangGraph":
                        operations.add(name)
                
                st.markdown("**Operations:**")
                for op in sorted(list(operations))[:10]:  # Show first 10
                    st.markdown(f"- {op}")
                if len(operations) > 10:
                    st.markdown(f"- ... and {len(operations) - 10} more")
            
            with col3:
                # Execution pattern
                total_duration = sum(s.get("duration_ms", 0) for s in spans if s.get("duration_ms"))
                avg_duration = total_duration / len(spans) if spans else 0
                
                st.markdown("**Execution Pattern:**")
                st.markdown(f"- Total Duration: {total_duration:.0f}ms")
                st.markdown(f"- Average/Step: {avg_duration:.0f}ms")
                st.markdown(f"- Max Depth: {_calculate_max_depth(spans)}")
    
    with tab2:
        # Display unified workflow execution view
        display_unified_workflow_execution(autopsy_data)
    
    with tab3:
        # Execution tree view
        display_execution_tree_view(autopsy_data)


def display_unified_workflow_execution(autopsy_data: dict):
    """Display unified sequential workflow execution with comprehensive chain details."""
    if not autopsy_data or "enhanced_data" not in autopsy_data:
        st.markdown("*No workflow execution data available*")
        return
    
    enhanced_data = autopsy_data.get("enhanced_data", {})
    trace_data = enhanced_data.get("trace", {})
    spans = trace_data.get("spans", [])
    
    if not spans:
        st.markdown("*No execution spans found in trace*")
        return
    
    st.markdown("### Sequential Workflow Execution")
    st.markdown("*Complete execution chain showing each step with inputs, processing, and outputs*")
    st.markdown("---")
    
    # Build sequential chain view
    chains = _build_sequential_chains(spans)
    
    if not chains:
        st.markdown("*No chain data available*")
        return
    
    # Display each chain in sequence
    for idx, chain in enumerate(chains, 1):
        display_chain_card(chain, idx, len(chains))


def _build_sequential_chains(spans: list) -> list:
    """Build sequential chain data from spans - only main CHAIN type spans."""
    chains = []
    
    # Group spans by parent to build chain hierarchy
    span_map = {s.get("span_id"): s for s in spans}
    
    # Only get CHAIN type spans (main workflow chains)
    chain_spans = [s for s in spans if s.get("span_type") == "chain"]
    
    # Process each chain span and its children
    for chain_span in chain_spans:
        chain = _process_chain_span(chain_span, span_map, spans)
        if chain:
            chains.append(chain)
    
    # Sort by start time
    chains.sort(key=lambda c: c.get("start_time", ""))
    
    return chains


def _process_chain_span(span: dict, span_map: dict, all_spans: list) -> dict:
    """Process a chain span into a comprehensive data structure with nested children."""
    span_id = span.get("span_id", "")
    span_type = span.get("span_type", "unknown")
    name = span.get("name", "Unknown")
    
    # Get direct children of this chain
    children = [s for s in all_spans if s.get("parent_span_id") == span_id]
    
    # Extract tool calls from children
    tool_calls = []
    for child in children:
        if child.get("span_type") == "tool":
            tool_calls.append({
                "name": child.get("name", "Unknown Tool"),
                "input": child.get("input", {}),
                "output": child.get("output", {}),
                "duration": child.get("duration_ms", 0),
                "error": child.get("error"),
                "status": "Error" if child.get("error") else "Success",
                "start_time": child.get("start_time", ""),
                "metadata": child.get("metadata", {})
            })
    
    # Extract generation info from children
    generations = []
    for child in children:
        if child.get("span_type") == "generation":
            generations.append({
                "name": child.get("name", "Unknown Generation"),
                "model": child.get("model", "Unknown"),
                "usage": child.get("usage", {}),
                "input": child.get("input", {}),
                "output": child.get("output", {}),
                "duration": child.get("duration_ms", 0),
                "start_time": child.get("start_time", ""),
                "error": child.get("error"),
                "metadata": child.get("metadata", {})
            })
    
    # Get model info from first generation if available
    model_info = {}
    if generations:
        gen = generations[0]
        model_info = {
            "model": gen.get("model", "Unknown"),
            "usage": gen.get("usage", {})
        }
    
    return {
        "span_id": span_id,
        "name": name,
        "type": span_type,
        "start_time": span.get("start_time", ""),
        "end_time": span.get("end_time", ""),
        "duration_ms": span.get("duration_ms", 0),
        "input": span.get("input", {}),
        "output": span.get("output", {}),
        "metadata": span.get("metadata", {}),
        "level": span.get("level", "DEFAULT"),
        "error": span.get("error"),
        "tool_calls": tool_calls,
        "generations": generations,
        "model_info": model_info,
        "children_count": len(children)
    }


def display_chain_card(chain: dict, index: int, total: int):
    """Display a comprehensive chain execution card."""
    name = chain.get("name", "Unknown")
    chain_type = chain.get("type", "unknown")
    duration_ms = chain.get("duration_ms", 0)
    duration_str = f"{duration_ms:.0f}ms" if duration_ms else "—"
    level = chain.get("level", "DEFAULT")
    error = chain.get("error")
    
    # Determine icon and color based on type
    type_icons = {
        "chain": "🔗",
        "generation": "🤖",
        "tool": "🔧",
        "event": "📌",
        "span": "📊"
    }
    icon = type_icons.get(chain_type, "📦")
    
    # Status indicator
    status_color = "#ef4444" if error else "#10b981"
    status_text = "ERROR" if error else level
    
    # Create collapsible expander for each chain
    with st.expander(f"{icon} **{index}/{total}** — {name} ({chain_type.upper()}) — {duration_str}", expanded=(index <= 3)):
        # Header row with metadata
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.markdown(f"**Status:** <span style='color:{status_color}; font-weight:600;'>{status_text}</span>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"**Duration:** {duration_str}")
        with col3:
            children_count = chain.get("children_count", 0)
            st.markdown(f"**Children:** {children_count}")
        
        if error:
            st.error(f"⚠️ Error: {error}")
        
        st.markdown("---")
        
        # Input Section
        st.markdown("#### 📥 Input")
        chain_input = chain.get("input", {})
        if chain_input:
            if isinstance(chain_input, dict):
                # Extract meaningful input
                input_display = chain_input
                if "messages" in chain_input:
                    input_display = {"messages": chain_input["messages"]}
                elif "query" in chain_input:
                    input_display = {"query": chain_input["query"]}
                st.json(input_display)
            else:
                st.code(str(chain_input)[:500], language="text")
        else:
            st.markdown("*No input data*")
        
        # Model/Configuration Section
        model_info = chain.get("model_info", {})
        if model_info and model_info.get("model"):
            st.markdown("#### ⚙️ Configuration")
            config_col1, config_col2 = st.columns(2)
            
            with config_col1:
                st.markdown(f"**Model:** {model_info.get('model', 'Unknown')}")
                usage = model_info.get("usage", {})
                if usage:
                    st.markdown(f"**Tokens:** {usage.get('total_tokens', 0)} (prompt: {usage.get('prompt_tokens', 0)}, completion: {usage.get('completion_tokens', 0)})")
            
            with config_col2:
                metadata = chain.get("metadata", {})
                if metadata:
                    st.markdown("**Metadata:**")
                    st.json(metadata)
        
        # Tool Calls Section
        tool_calls = chain.get("tool_calls", [])
        if tool_calls:
            st.markdown(f"#### 🔧 Tool Calls ({len(tool_calls)})")
            
            for i, tool in enumerate(tool_calls, 1):
                tool_name = tool.get("name", "Unknown")
                tool_status = tool.get("status", "Success")
                tool_duration = tool.get("duration", 0)
                tool_error = tool.get("error")
                
                status_badge = "🔴" if tool_status == "Error" else "🟢"
                
                with st.container():
                    st.markdown(f"**{status_badge} Tool {i}: {tool_name}** — {tool_duration:.0f}ms")
                    
                    if tool_error:
                        st.error(f"Error: {tool_error}")
                    
                    tool_col1, tool_col2 = st.columns(2)
                    
                    with tool_col1:
                        st.markdown("*Input:*")
                        tool_input = tool.get("input", {})
                        if tool_input:
                            st.json(tool_input)
                        else:
                            st.markdown("*Empty*")
                    
                    with tool_col2:
                        st.markdown("*Output:*")
                        tool_output = tool.get("output", {})
                        if tool_output:
                            if isinstance(tool_output, dict):
                                st.json(tool_output)
                            else:
                                st.code(str(tool_output)[:300], language="text")
                        else:
                            st.markdown("*Empty*")
                    
                    if i < len(tool_calls):
                        st.markdown("---")
        
        # LLM Generations Section
        generations = chain.get("generations", [])
        if generations:
            st.markdown(f"#### 🤖 LLM Generations ({len(generations)})")
            
            for i, gen in enumerate(generations, 1):
                gen_name = gen.get("name", "Unknown Generation")
                gen_model = gen.get("model", "Unknown")
                gen_duration = gen.get("duration", 0)
                gen_error = gen.get("error")
                gen_usage = gen.get("usage", {})
                
                status_badge = "🔴" if gen_error else "🟢"
                
                with st.container():
                    st.markdown(f"**{status_badge} Generation {i}: {gen_name}** — {gen_duration:.0f}ms")
                    st.markdown(f"*Model: {gen_model}*")
                    
                    if gen_error:
                        st.error(f"Error: {gen_error}")
                    
                    # Display token usage if available
                    if gen_usage:
                        usage_str = f"Tokens: {gen_usage.get('total_tokens', 0)} (prompt: {gen_usage.get('prompt_tokens', 0)}, completion: {gen_usage.get('completion_tokens', 0)})"
                        st.markdown(f"*{usage_str}*")
                    
                    gen_col1, gen_col2 = st.columns(2)
                    
                    with gen_col1:
                        st.markdown("*Input:*")
                        gen_input = gen.get("input", {})
                        if gen_input:
                            # Extract messages if available
                            if isinstance(gen_input, dict) and "messages" in gen_input:
                                messages = gen_input["messages"]
                                if isinstance(messages, list) and messages:
                                    # Show last message or summary
                                    st.json({"messages": messages[-3:] if len(messages) > 3 else messages})
                                else:
                                    st.json(gen_input)
                            else:
                                st.json(gen_input)
                        else:
                            st.markdown("*Empty*")
                    
                    with gen_col2:
                        st.markdown("*Output:*")
                        gen_output = gen.get("output", {})
                        if gen_output:
                            if isinstance(gen_output, dict):
                                # Extract content if available
                                if "content" in gen_output:
                                    content = gen_output["content"]
                                    if isinstance(content, str):
                                        st.code(content[:500], language="text")
                                    else:
                                        st.json({"content": content})
                                else:
                                    st.json(gen_output)
                            else:
                                st.code(str(gen_output)[:500], language="text")
                        else:
                            st.markdown("*Empty*")
                    
                    # Show metadata if available
                    gen_metadata = gen.get("metadata", {})
                    if gen_metadata:
                        with st.expander("View Metadata"):
                            st.json(gen_metadata)
                    
                    if i < len(generations):
                        st.markdown("---")
        
        # Output Section
        st.markdown("#### 📤 Output")
        chain_output = chain.get("output", {})
        if chain_output:
            if isinstance(chain_output, dict):
                # Try to extract meaningful output
                if "content" in chain_output:
                    st.markdown("**Response:**")
                    st.code(str(chain_output["content"])[:1000], language="text")
                elif "messages" in chain_output:
                    st.markdown("**Messages:**")
                    st.json(chain_output["messages"])
                else:
                    st.json(chain_output)
            else:
                st.code(str(chain_output)[:500], language="text")
        else:
            st.markdown("*No output data*")
        
        # Timing Information
        start_time = chain.get("start_time", "")
        end_time = chain.get("end_time", "")
        if start_time or end_time:
            st.markdown("#### ⏱️ Timing")
            timing_col1, timing_col2 = st.columns(2)
            with timing_col1:
                if start_time:
                    st.markdown(f"**Start:** {start_time}")
            with timing_col2:
                if end_time:
                    st.markdown(f"**End:** {end_time}")


def display_execution_tree_view(autopsy_data: dict):
    """Display execution tree view."""
    if not autopsy_data or "enhanced_data" not in autopsy_data:
        st.markdown("*No execution tree data available*")
        return
    
    enhanced_data = autopsy_data.get("enhanced_data", {})
    trace_data = enhanced_data.get("trace", {})
    spans = trace_data.get("spans", [])
    
    if not spans:
        st.markdown("*No spans found*")
        return
    
    st.markdown("### Execution Tree View")
    st.markdown("*Hierarchical view of all execution spans*")
    st.markdown("---")
    
    # Build tree structure
    span_map = {s.get("span_id"): s for s in spans}
    root_spans = [s for s in spans if not s.get("parent_span_id")]
    
    # Display tree
    for root in root_spans:
        display_execution_tree(root, span_map, 0)


def display_execution_tree(span: dict, span_map: dict, level: int):
    """Recursively display execution tree."""
    indent = "  " * level
    name = span.get("name", "Unknown")
    span_type = span.get("span_type", "unknown")
    duration = span.get("duration_ms", 0)
    duration_str = f"{duration:.0f}ms" if duration else "—"
    
    # Type icons
    type_icons = {
        "chain": "🔗",
        "generation": "🤖",
        "tool": "🔧",
        "event": "📌",
        "span": "📊"
    }
    icon = type_icons.get(span_type, "📦")
    
    st.markdown(f"{indent}{icon} **{name}** ({span_type.upper()}) — {duration_str}")
    
    # Find and display children
    span_id = span.get("span_id")
    children = [s for s in span_map.values() if s.get("parent_span_id") == span_id]
    
    for child in children:
        display_execution_tree(child, span_map, level + 1)


def _old_tab2_content():
    """Old tab2 content - keeping for reference."""
    with st.container():
        # Extract detailed tool calls from autopsy data
        tool_calls = _extract_detailed_tool_calls(autopsy_data)
        
        if not tool_calls:
            st.markdown("*No tool calls detected in this trace*")
        else:
            # Header row
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.25rem;">
                <h4 style="margin:0;">Tool Call Analysis</h4>
                <span class="total-calls-badge">{len(tool_calls)} total calls</span>
            </div>
            """, unsafe_allow_html=True)
            
            for i, tc in enumerate(tool_calls, 1):
                tool_name = tc.get("tool_name", "Unknown")
                parent_step = tc.get("parent_step", "")
                duration = tc.get("duration", "—")
                status = tc.get("status", "Success")
                duration_cls = "error" if status == "Error" else ""
                
                # Format input/output as JSON-like strings
                inp = tc.get("input", "")
                out = tc.get("output", "")
                inp_json = json.dumps({"input": inp}, indent=2) if inp else '{}'
                out_json = json.dumps({"output": out}, indent=2) if out else '{}'
                
                # Escape HTML
                inp_display = inp_json.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                out_display = out_json.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                
                out_block_cls = "output"
                if status == "Error":
                    out_block_cls = "output error-block"
                
                # Build analysis metadata rows (only non-None values)
                meta_fields = [
                    ("Relevant to Query", tc.get("relevant_to_query")),
                    ("Actual Relevance", tc.get("actual_relevance")),
                    ("Misinterpretation", tc.get("misinterpretation")),
                    ("Correct Interpretation", tc.get("correct_interpretation")),
                    ("Relevance", tc.get("relevance")),
                    ("Agent Belief", tc.get("agent_belief")),
                    ("Reality", tc.get("reality")),
                    ("Calculation", tc.get("calculation")),
                    ("Misapplication", tc.get("misapplication")),
                    ("Result", tc.get("result")),
                    ("Basis", tc.get("basis")),
                ]
                meta_rows = ""
                for label, val in meta_fields:
                    if val is None or val == "":
                        continue
                    val_escaped = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    meta_rows += f"""
                    <div style="display:flex; gap:0.75rem; padding:0.25rem 0; border-bottom:1px solid #f3f4f6;">
                        <span style="min-width:140px; font-weight:600; color:#6b7280; font-size:0.8rem;">{label}</span>
                        <span style="color:#1f2937; font-size:0.8rem;">{val_escaped}</span>
                    </div>"""

                meta_section = ""
                if meta_rows:
                    meta_section = f"""
                    <div style="margin-top:0.75rem; padding:0.75rem; background:#fafafa; border-radius:0.5rem; border:1px solid #e5e7eb;">
                        <div style="font-weight:600; font-size:0.8rem; color:#4b5563; margin-bottom:0.375rem;">🔍 Analysis Insights</div>
                        {meta_rows}
                    </div>"""

                card_html = f"""
                <div class="tool-card">
                    <div class="tool-card-header">
                        <div class="tool-card-title">
                            <span class="tool-card-number">#{i}</span>
                            <div>
                                <span class="tool-card-name">{tool_name}</span>
                                <span class="tool-badge">TOOL</span>
                                <div class="tool-card-parent">◇ {parent_step}</div>
                            </div>
                        </div>
                        <span class="tool-card-duration {duration_cls}">{duration}</span>
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem;">
                        <div>
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span class="tool-io-label">Input Arguments</span>
                            </div>
                            <div class="tool-io-block">{inp_display}</div>
                        </div>
                        <div>
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span class="tool-io-label">Output Response</span>
                            </div>
                            <div class="tool-io-block {out_block_cls}">{out_display}</div>
                        </div>
                    </div>
                    {meta_section}
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)


def _old_tab3_content():
    """Old tab3 content - keeping for reference."""
    with st.container():
        # Extract detailed planner information
        planner_data = _extract_detailed_planner_info(autopsy_data)
        
        if not planner_data or (not planner_data.get("steps") and not planner_data.get("query")):
            st.markdown("*No planner decision data found in this trace*")
        else:
            # Header with active badge
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.25rem;">
                <h4 style="margin:0;">Planner Decision</h4>
                <span class="active-badge">ACTIVE STRATEGY</span>
            </div>
            """, unsafe_allow_html=True)
            
            col_left, col_right = st.columns([3, 2])
            
            with col_left:
                # Input Payload
                query = planner_data.get("query", "")
                if query:
                    st.markdown('<div class="planner-section-label">Input Payload</div>', unsafe_allow_html=True)
                    # Truncate very long queries for display
                    display_query = query[:500] + "..." if len(query) > 500 else query
                    st.markdown(f'<div class="planner-input-box">"{display_query}"</div>', unsafe_allow_html=True)
                
                # Planner Reasoning
                reasoning = planner_data.get("reasoning", "")
                active_processor = planner_data.get("active_processor", "planning")
                if reasoning:
                    st.markdown('<div class="planner-section-label">Planner Reasoning</div>', unsafe_allow_html=True)
                    reasoning_escaped = reasoning.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    st.markdown(f"""
                    <div class="planner-reasoning-box">
                        <div class="planner-reasoning-label">ACTIVE PROCESSOR:</div>
                        <span class="planner-reasoning-agent">{active_processor}</span>
                        <div class="planner-reasoning-text">{reasoning_escaped}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col_right:
                # Model Information
                model_name = planner_data.get("model_name", "Unknown")
                domain = planner_data.get("domain", "")
                category = planner_data.get("category", "")
                confidence = planner_data.get("confidence", 0)
                
                st.markdown('<div class="planner-section-label">Model Information</div>', unsafe_allow_html=True)
                st.markdown(f"""
                <div class="model-info-box">
                    <div class="model-info-row">
                        <span class="model-info-key">LLM Provider</span>
                        <span class="model-info-value">LangGraph</span>
                    </div>
                    <div class="model-info-row">
                        <span class="model-info-key">Model ID</span>
                        <span class="model-info-value highlight">{model_name}</span>
                    </div>
                    <div class="model-info-row">
                        <span class="model-info-key">Domain</span>
                        <span class="model-info-value">{domain or '—'}</span>
                    </div>
                    <div class="model-info-row">
                        <span class="model-info-key">Category</span>
                        <span class="model-info-value">{category or '—'}</span>
                    </div>
                    <div class="model-info-row">
                        <span class="model-info-key">Confidence</span>
                        <span class="model-info-value highlight">{confidence * 100:.0f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Capabilities (tools needed)
                tools_needed = planner_data.get("tools_needed", [])
                if tools_needed:
                    tools_count = len(tools_needed)
                    chips_html = "".join(
                        f'<span class="capability-chip">{t}</span>' for t in tools_needed
                    )
                    st.markdown(f"""
                    <div style="margin-top:1rem;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                            <div class="planner-section-label" style="margin-bottom:0;">Capabilities</div>
                            <span class="tools-count-badge">{tools_count} TOOLS</span>
                        </div>
                        <div>{chips_html}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Plan Steps
            steps = planner_data.get("steps", [])
            if steps:
                st.markdown("---")
                plan_name = planner_data.get("plan_name", "Execution Plan")
                st.markdown(f"""
                <div class="planner-section-label">Execution Plan: {plan_name}</div>
                """, unsafe_allow_html=True)
                
                for step in steps:
                    step_num = step.get("step", "")
                    action = step.get("action", "")
                    tools = step.get("tools", [])
                    tools_chips = "".join(
                        f'<span class="step-tool-chip">{t}</span>' for t in tools
                    ) if tools else '<span style="color:#9ca3af; font-size:0.8rem;">No tools</span>'
                    
                    st.markdown(f"""
                    <div class="step-card">
                        <div class="step-card-header">
                            <span class="step-number">{step_num}</span>
                            <span class="step-action">{action}</span>
                        </div>
                        <div class="step-tools">{tools_chips}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Decision Branches
            branches = planner_data.get("decision_branches", [])
            if branches:
                st.markdown("---")
                st.markdown('<div class="planner-section-label">Decision Branches</div>', unsafe_allow_html=True)
                for branch in branches:
                    condition = branch.get("condition", "")
                    next_step = branch.get("next_step", "")
                    threshold = branch.get("threshold", "")
                    st.markdown(f"""
                    <div class="decision-branch">
                        <strong>IF</strong> {condition} (threshold: {threshold}) <strong>→</strong> {next_step}
                    </div>
                    """, unsafe_allow_html=True)
            
            # Key Decisions Made
            decisions = planner_data.get("decisions", [])
            if decisions:
                st.markdown("---")
                st.markdown('<div class="planner-section-label">Key Decisions</div>', unsafe_allow_html=True)
                for d in decisions:
                    if not isinstance(d, dict):
                        continue
                    node = d.get("node", "")
                    decision = d.get("decision", "")
                    reasoning_d = d.get("reasoning", "")
                    impact = d.get("impact", "")
                    st.markdown(f"""
                    <div class="step-card">
                        <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.375rem;">
                            <span class="tool-badge">{node}</span>
                            <span style="font-weight:600; color:#1f2937;">{decision}</span>
                        </div>
                        <div style="font-size:0.85rem; color:#6b7280; margin-bottom:0.25rem;">{reasoning_d}</div>
                        <div style="font-size:0.8rem; color:#dc2626;">Impact: {impact}</div>
                    </div>
                    """, unsafe_allow_html=True)
        st.markdown("#### Execution Tree View")
        
        # Build execution tree from actual trace data
        execution_tree = _build_execution_tree_from_autopsy(autopsy_data)
        
        if not execution_tree:
            st.markdown("*No execution tree data available*")
        else:
            display_execution_tree(execution_tree)


def display_enhanced_report(autopsy_data: dict, trace_id: str):
    """Display the full report with enhanced visualizations."""
    # Get report content
    report_content = get_report_content_from_api(autopsy_data)
    
    if not report_content:
        st.toast("No report content available", icon="⚠️")
        return
    
    # Create tabs for report and workflow execution
    report_tab, workflow_tab = st.tabs(["📄 Report", "⚡ Workflow Execution"])
    
    with report_tab:
        st.markdown(report_content)
        
        # Download options
        col1, col2 = st.columns([4, 1])
        with col2:
            pdf_content = create_pdf_from_markdown(report_content, trace_id)
            if pdf_content:
                b64_pdf = base64.b64encode(pdf_content).decode()
                href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{trace_id}_agent_autopsy_report.pdf" class="download-button">Download Report</a>'
                st.markdown(href, unsafe_allow_html=True)
    
    with workflow_tab:
        # Display unified workflow execution view
        display_unified_workflow_execution(autopsy_data)


def main():
    # Enhanced header with styling
    st.markdown('<h1 class="main-header">🔍 Agent Autopsy</h1>', unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align: center; color: #6b7280; margin-bottom: 2rem;">'
        'Detect silent failures in agent workflows'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Sidebar for input with enhanced styling
    with st.sidebar:
        st.markdown('<div class="sidebar-header"><h3>📊 Agent Autopsy</h3></div>', unsafe_allow_html=True)
        
        # Trace ID input - single trace at a time
        trace_id_input = st.text_input(
            "Trace ID",
            placeholder="Enter a trace ID",
            help="Enter trace ID",
            max_chars=100
        )
        
        # Provider selection
        provider = st.selectbox(
            "Provider",
            ["langfuse", "other"],
            index=0,
            help="Select the trace provider"
        )
        
        # Process button with enhanced styling
        process_button = st.button("🚀 Analyze Trace", type="primary", use_container_width=True)
    
    # Main content area
    if process_button and trace_id_input:
        # Clean and validate trace ID
        trace_id = trace_id_input.strip()
        
        if not trace_id:
            st.toast("Please enter a trace ID", icon="⚠️")
            return
        
        # Fetch autopsy data
        autopsy_data = fetch_autopsy(trace_id, provider)
        
        if autopsy_data:
            # Display summary
            display_autopsy_summary(autopsy_data, trace_id)
            
            # Display enhanced report with visualizations
            display_enhanced_report(autopsy_data, trace_id)
    
    else:
        # Simple homescreen with new content
        homescreen_content = (
            "## 🔍 What is Agent Autopsy?\n\n"
            "Agent Autopsy diagnoses why AI agent workflows fail - even when they appear successful.\n\n"
            "It analyzes execution traces to pinpoint where correctness stopped being enforced, uncovering silent failures, false success states, and structural gaps in multi-agent workflows.\n"
            "Every finding is backed by trace-derived evidence and presented as a concise, actionable report.\n\n"
            "### 🎯 What Agent Autopsy Detects\n\n"
            "**Silent & Structural Failures**\n\n"
            "- False terminal success (successful runs with invalid or empty output)\n"
            "- Missing validation between agent handoffs\n"
            "- Execution paths where errors never surfaced\n\n"
            "**Trace-Derived Diagnosis**\n\n"
            "- Analyzes execution spans, decisions, and terminal states\n"
            "- Identifies the exact boundary where correctness broke\n"
            "- Assigns severity and confidence based on observed evidence\n\n"
            "**Actionable Outcomes**\n\n"
            "- Clear root-cause explanations (not just symptoms)\n"
            "- Concrete prevention invariants and detection signals\n"
            "- Reports designed for engineers, not dashboards\n\n"
            "### 📄 What You Get\n\n"
            "- **Concise Autopsy Report** with a clear failure boundary\n"
            "- **Status, Severity & Confidence** at a glance\n"
            "- **Primary Failure Classification** with evidence\n"
            "- **Actionable Prevention & Detection** guidance\n"
            "- **Exportable Markdown / PDF** for sharing and postmortems\n\n"
            "### 🚀 How to Get Started\n\n"
            "1. **Enter a Trace ID** in the sidebar\n"
            "2. **Select your Provider** (default: Langfuse)\n"
            "3. **Click Generate Agent Autopsy Report**\n\n\nAgent Autopsy will fetch the trace, analyze execution behavior, and present a structured diagnostic report - ready to review, share, or act on."
        )
        st.markdown(homescreen_content)

if __name__ == "__main__":
    main()
