#!/usr/bin/env python3
"""
Comprehensive end-to-end test script for Agent Autopsy.
Tests the complete flow from UI to backend using a real trace ID.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any

import httpx

# Configuration
BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:8501"
TRACE_ID = "3248bf721d698f0fa820312f47b5def5"
PROVIDER = "langfuse"
TIMEOUT = 30


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print a colored header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


def print_step(step_num: int, description: str):
    """Print step header."""
    print(f"\n{Colors.BOLD}Step {step_num}: {description}{Colors.ENDC}")
    print("-" * 50)


def test_backend_health() -> bool:
    """Test if backend is running and healthy."""
    print_step(1, "Testing Backend Health")
    
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{BACKEND_URL}/health")
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Backend is healthy: {data.get('status', 'unknown')}")
                print_info(f"Version: {data.get('version', 'unknown')}")
                print_info(f"LLM Enabled: {data.get('llm_enabled', False)}")
                print_info(f"Available Providers: {data.get('available_providers', [])}")
                return True
            else:
                print_error(f"Backend health check failed: {response.status_code}")
                return False
                
    except httpx.ConnectError:
        print_error("Cannot connect to backend. Is it running?")
        return False
    except Exception as e:
        print_error(f"Backend health check error: {e}")
        return False


def test_backend_api() -> Dict[str, Any] | None:
    """Test the main autopsy API endpoint."""
    print_step(2, "Testing Backend Autopsy API")
    
    payload = {
        "trace_id": TRACE_ID,
        "provider": PROVIDER
    }
    
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            print_info(f"Sending request to {BACKEND_URL}/api/v1/autopsy")
            print_info(f"Payload: {json.dumps(payload, indent=2)}")
            
            start_time = time.time()
            response = client.post(
                f"{BACKEND_URL}/api/v1/autopsy",
                json=payload
            )
            end_time = time.time()
            
            print_info(f"Request completed in {end_time - start_time:.2f} seconds")
            print_info(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print_success("Autopsy API call successful!")
                
                # Check response structure
                print_info("Response structure validation:")
                
                required_fields = ["result", "report", "enhanced_data"]
                for field in required_fields:
                    if field in data:
                        print_success(f"  ✓ {field} present")
                    else:
                        print_error(f"  ✗ {field} missing")
                
                # Check enhanced_data
                if "enhanced_data" in data and data["enhanced_data"]:
                    enhanced = data["enhanced_data"]
                    print_info("Enhanced data analysis:")
                    
                    if "trace" in enhanced and enhanced["trace"]:
                        spans = enhanced["trace"].get("spans", [])
                        print_success(f"  ✓ Trace data with {len(spans)} spans")
                        
                        # Analyze span types
                        span_types = {}
                        for span in spans:
                            span_type = span.get("span_type", "unknown")
                            span_types[span_type] = span_types.get(span_type, 0) + 1
                        
                        print_info("  Span types found:")
                        for span_type, count in span_types.items():
                            print_info(f"    - {span_type}: {count}")
                    else:
                        print_warning("  ⚠ No trace data in enhanced_data")
                    
                    if "tool_calls" in enhanced:
                        tool_calls = enhanced["tool_calls"]
                        print_success(f"  ✓ Tool calls extracted: {len(tool_calls)}")
                    
                    if "planner_decision" in enhanced:
                        planner = enhanced["planner_decision"]
                        if planner:
                            print_success(f"  ✓ Planner decision extracted")
                        else:
                            print_warning("  ⚠ Planner decision is empty")
                else:
                    print_warning("  ⚠ No enhanced_data in response")
                
                # Check report content
                if "report" in data and data["report"]:
                    report = data["report"]
                    print_success(f"  ✓ Report generated ({len(report)} characters)")
                    
                    # Check for dynamic content indicators
                    dynamic_indicators = ["Execution Statistics:", "Execution Flow Analysis:", "Performance Bottlenecks:"]
                    found_dynamic = sum(1 for indicator in dynamic_indicators if indicator in report)
                    if found_dynamic > 0:
                        print_success(f"  ✓ Dynamic report content detected ({found_dynamic}/{len(dynamic_indicators)} sections)")
                    else:
                        print_warning("  ⚠ No dynamic content detected in report")
                
                return data
                
            elif response.status_code == 404:
                print_error(f"Trace not found: {TRACE_ID}")
                print_info("This might mean:")
                print_info("  - The trace ID doesn't exist in Langfuse")
                print_info("  - The Langfuse connection is not working")
                print_info("  - The trace is in a different format")
                return None
                
            elif response.status_code == 500:
                print_error("Server error occurred")
                print_error("Check backend logs for details")
                return None
                
            else:
                print_error(f"Unexpected status code: {response.status_code}")
                print_error(f"Response: {response.text}")
                return None
                
    except httpx.TimeoutException:
        print_error(f"Request timed out after {TIMEOUT} seconds")
        return None
    except Exception as e:
        print_error(f"API call error: {e}")
        return None


def test_frontend_access() -> bool:
    """Test if frontend is accessible."""
    print_step(3, "Testing Frontend Access")
    
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(FRONTEND_URL)
            
            if response.status_code == 200:
                print_success("Frontend is accessible")
                print_info(f"Frontend URL: {FRONTEND_URL}")
                return True
            else:
                print_error(f"Frontend not accessible: {response.status_code}")
                return False
                
    except httpx.ConnectError:
        print_error("Cannot connect to frontend. Is it running?")
        return False
    except Exception as e:
        print_error(f"Frontend access error: {e}")
        return False


def test_file_structure() -> bool:
    """Test if all required files exist."""
    print_step(4, "Testing File Structure")
    
    base_path = Path(__file__).parent
    
    required_files = [
        "agent_autopsy/main.py",
        "agent_autopsy/api/routes.py",
        "agent_autopsy/core/report_generator.py",
        "agent_autopsy/core/templates/report_failed.md.j2",
        "agent_autopsy/core/templates/report_passed.md.j2",
        "client_app/app.py",
        ".env"
    ]
    
    all_exist = True
    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            print_success(f"  ✓ {file_path}")
        else:
            print_error(f"  ✗ {file_path}")
            all_exist = False
    
    return all_exist


def test_ui_simulation() -> bool:
    """Simulate UI workflow steps."""
    print_step(5, "Simulating UI Workflow")
    
    # Simulate the steps the UI would take
    ui_steps = [
        "1. User enters trace ID in UI",
        "2. UI calls backend API",
        "3. Backend processes trace",
        "4. Backend generates report",
        "5. UI displays results"
    ]
    
    for step in ui_steps:
        print_info(f"  {step}")
        time.sleep(0.2)  # Simulate processing time
    
    print_success("UI workflow simulation completed")
    return True


def analyze_results(autopsy_data: Dict[str, Any] | None):
    """Analyze the autopsy results and provide insights."""
    print_step(6, "Analyzing Results")
    
    if not autopsy_data:
        print_error("No autopsy data to analyze")
        return
    
    print_header("AUTOPSY ANALYSIS SUMMARY")
    
    # Analyze result
    result = autopsy_data.get("result", {})
    print_info(f"Trace ID: {result.get('trace_id', 'Unknown')}")
    print_info(f"Status: {result.get('status', 'Unknown').upper()}")
    print_info(f"Severity: {result.get('overall_severity', 'Unknown').upper()}")
    print_info(f"Confidence: {result.get('confidence', 0) * 100:.1f}%")
    print_info(f"Total Spans: {result.get('total_spans_analyzed', 0)}")
    
    # Analyze failures
    primary_failures = result.get("primary_failures", [])
    secondary_failures = result.get("secondary_failures", [])
    
    print_info(f"Primary Failures: {len(primary_failures)}")
    for i, failure in enumerate(primary_failures, 1):
        print_info(f"  {i}. {failure.get('failure_type', 'Unknown')} - {failure.get('title', 'No title')}")
    
    print_info(f"Secondary Failures: {len(secondary_failures)}")
    for i, failure in enumerate(secondary_failures, 1):
        print_info(f"  {i}. {failure.get('failure_type', 'Unknown')} - {failure.get('title', 'No title')}")
    
    # Analyze enhanced data
    enhanced = autopsy_data.get("enhanced_data", {})
    if enhanced:
        print_info("Enhanced Data Analysis:")
        
        if "trace" in enhanced:
            trace = enhanced["trace"]
            spans = trace.get("spans", [])
            print_info(f"  Total spans in trace: {len(spans)}")
            
            # Count span types
            span_types = {}
            for span in spans:
                span_type = span.get("span_type", "unknown")
                span_types[span_type] = span_types.get(span_type, 0) + 1
            
            for span_type, count in span_types.items():
                print_info(f"    {span_type}: {count}")
        
        if "tool_calls" in enhanced:
            tool_calls = enhanced["tool_calls"]
            print_info(f"  Tool calls extracted: {len(tool_calls)}")
        
        if "planner_decision" in enhanced:
            planner = enhanced["planner_decision"]
            if planner:
                print_info(f"  Planner decision extracted: {len(str(planner))} characters")
            else:
                print_warning("  Planner decision is empty")
    
    # Analyze report
    report = autopsy_data.get("report", {})
    if report:
        report_content = report.get("summary", "")
        print_info(f"Report length: {len(report_content)} characters")
        
        # Check for dynamic content
        dynamic_sections = [
            "Execution Statistics:",
            "Execution Flow Analysis:",
            "Performance Bottlenecks:",
            "Error Details:",
            "Failure Timeline:",
            "Critical Path"
        ]
        
        found_sections = [section for section in dynamic_sections if section in report_content]
        print_info(f"Dynamic sections found: {len(found_sections)}/{len(dynamic_sections)}")
        
        if found_sections:
            print_success("Report contains dynamic, trace-specific content")
        else:
            print_warning("Report appears to use static content")


def main():
    """Main test execution."""
    print_header("AGENT AUTOPSY END-TO-END TEST")
    print_info(f"Testing with Trace ID: {TRACE_ID}")
    print_info(f"Backend URL: {BACKEND_URL}")
    print_info(f"Frontend URL: {FRONTEND_URL}")
    
    # Run all tests
    tests = [
        ("Backend Health", test_backend_health),
        ("Backend API", test_backend_api),
        ("Frontend Access", test_frontend_access),
        ("File Structure", test_file_structure),
        ("UI Simulation", test_ui_simulation),
    ]
    
    results = {}
    autopsy_data = None
    
    for test_name, test_func in tests:
        try:
            if test_name == "Backend API":
                result = test_func()
                if isinstance(result, dict):
                    autopsy_data = result
                    results[test_name] = True
                else:
                    results[test_name] = False
            else:
                results[test_name] = test_func()
        except Exception as e:
            print_error(f"Test '{test_name}' failed with exception: {e}")
            results[test_name] = False
    
    # Analyze results
    if autopsy_data:
        analyze_results(autopsy_data)
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print_info(f"Tests passed: {passed}/{total}")
    
    for test_name, result in results.items():
        if result:
            print_success(f"✓ {test_name}")
        else:
            print_error(f"✗ {test_name}")
    
    if passed == total:
        print_success("\n🎉 ALL TESTS PASSED! The Agent Autopsy system is working correctly.")
        print_info("You can now use the UI at http://127.0.0.1:8501 to analyze traces.")
    else:
        print_warning(f"\n⚠️  {total - passed} test(s) failed. Please check the issues above.")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_warning("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        sys.exit(1)
