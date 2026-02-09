"""End-to-end verification: confirm all visualization tabs have data."""
import httpx
import json
import sys

API_BASE = "http://127.0.0.1:8000"
TRACE_ID = "33533c94ed65294a077f2f53482d0945"

def main():
    trace_id = sys.argv[1] if len(sys.argv) > 1 else TRACE_ID
    print(f"E2E Verification for trace: {trace_id}\n")

    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{API_BASE}/api/v1/autopsy", json={"provider": "langfuse", "trace_id": trace_id})
        resp.raise_for_status()
        data = resp.json()

    ed = data.get("enhanced_data", {})
    errors = []

    # Tab 1: Overview - needs trace spans
    spans = ed.get("trace", {}).get("spans", [])
    if not spans:
        errors.append("FAIL: Overview - no trace spans")
    else:
        print(f"✓ Overview: {len(spans)} spans available")

    # Tab 2: Tool Calls
    tc = ed.get("tool_calls", [])
    if not tc:
        errors.append("FAIL: Tool Calls - empty")
    else:
        print(f"✓ Tool Calls: {len(tc)} unique calls")
        # Verify no duplicates
        keys = set()
        dupes = 0
        for t in tc:
            k = (t["tool_name"], str(t.get("input", "")))
            if k in keys:
                dupes += 1
            keys.add(k)
        if dupes:
            errors.append(f"FAIL: Tool Calls - {dupes} duplicates found")
        else:
            print(f"  ✓ No duplicates")
        # Verify required fields
        required = ["tool_name", "input", "output", "parent_step", "status", "duration"]
        for field in required:
            missing = [i for i, t in enumerate(tc) if field not in t]
            if missing:
                errors.append(f"FAIL: Tool Calls - field '{field}' missing in items {missing}")
            else:
                print(f"  ✓ Field '{field}' present in all items")

    # Tab 3: Planner Decision
    pd = ed.get("planner_decision", {})
    if not pd or not any(pd.values()):
        errors.append("FAIL: Planner Decision - empty or all null")
    else:
        print(f"✓ Planner Decision: {len([k for k,v in pd.items() if v])} non-empty fields")
        key_fields = ["query", "plan_name", "steps", "decisions", "model_name", "tools_needed"]
        for field in key_fields:
            val = pd.get(field)
            if val:
                print(f"  ✓ {field}: {str(val)[:80]}")
            else:
                print(f"  ⚠ {field}: empty")

    # Tab 4: Execution Tree
    tree = ed.get("execution_tree", {})
    if not tree or not tree.get("children"):
        errors.append("FAIL: Execution Tree - empty or no children")
    else:
        child_count = len(tree.get("children", []))
        print(f"✓ Execution Tree: root='{tree.get('name')}' with {child_count} children")

    print("\n" + "=" * 60)
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print("ALL TABS VERIFIED ✓")

if __name__ == "__main__":
    main()
