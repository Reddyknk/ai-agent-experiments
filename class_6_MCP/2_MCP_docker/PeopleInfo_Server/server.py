import argparse
import csv
import difflib
import os
from pathlib import Path
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("PeopleInfo_Server")

CSV_FILE_PATH = Path(__file__).parent / "employee_data.csv"


def load_employee_data() -> list[dict[str, str]]:
    """Loads employee data from the CSV file."""
    if not CSV_FILE_PATH.exists():
        raise FileNotFoundError(f"Employee data file not found at {CSV_FILE_PATH}")

    employees = []
    with open(CSV_FILE_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            employees.append({
                "name": row.get("name", "").strip(),
                "city": row.get("city", "").strip(),
                "country": row.get("country", "").strip(),
                "position": row.get("position", "").strip(),
            })
    return employees


def is_fuzzy_match(query: str, target: str, threshold: float = 0.65) -> bool:
    """
    Checks if the query fuzzy-matches the target string using:
    1. Case-insensitive exact substring containment
    2. Overall SequenceMatcher similarity ratio
    3. Word-level SequenceMatcher similarity ratio
    """
    query_clean = query.strip().lower()
    target_clean = target.strip().lower()

    if not query_clean or not target_clean:
        return False

    # 1. Direct substring match
    if query_clean in target_clean:
        return True

    # 2. Overall ratio
    overall_ratio = difflib.SequenceMatcher(None, query_clean, target_clean).ratio()
    if overall_ratio >= threshold:
        return True

    # 3. Check individual tokens/words in target
    target_words = target_clean.split()
    for word in target_words:
        word_ratio = difflib.SequenceMatcher(None, query_clean, word).ratio()
        if word_ratio >= threshold:
            return True

    return False


@mcp.tool
def search_people(search_for: str, field_name: str) -> list[dict[str, str]]:
    """
    Searches employee records using fuzzy matching on the specified field.

    Parameters:
        search_for: The query string to search for.
        field_name: The column to search in (e.g. 'name', 'city', 'country', 'position').

    Returns:
        List of matching people records containing name, city, country, and position.
    """
    field = field_name.strip().lower()
    employees = load_employee_data()
    valid_fields = ["name", "city", "country", "position"]

    # Match field_name loosely if user entered something like 'positions' or 'job'
    matched_field = None
    for vf in valid_fields:
        if field == vf or field in vf or vf in field:
            matched_field = vf
            break

    if not matched_field:
        # If field not recognized, search across all valid fields
        results = []
        for emp in employees:
            if any(is_fuzzy_match(search_for, emp[f]) for f in valid_fields):
                results.append({
                    "name": emp["name"],
                    "city": emp["city"],
                    "country": emp["country"],
                    "position": emp["position"],
                })
        return results

    results = []
    for emp in employees:
        value = emp.get(matched_field, "")
        if is_fuzzy_match(search_for, value):
            results.append({
                "name": emp["name"],
                "city": emp["city"],
                "country": emp["country"],
                "position": emp["position"],
            })

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PeopleInfo MCP Server")
    parser.add_argument(
        "--transport",
        default=os.getenv("TRANSPORT", "stdio"),
        choices=["stdio", "sse", "http", "streamable-http"],
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind to for HTTP/SSE (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8001")),
        help="Port to bind to for HTTP/SSE (default: 8001)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port, show_banner=False)
