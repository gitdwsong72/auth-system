#!/bin/bash
# Quick Load Test Script
#
# Purpose: Run a quick 2-minute load test to verify everything works
# Requirements: Auth service running on localhost:8000

set -e

echo "======================================"
echo "Quick Load Test for Auth System"
echo "======================================"
echo ""

# Check if locust is installed
if ! command -v locust &> /dev/null; then
    echo "❌ Locust is not installed. Install with:"
    echo "   pip install locust"
    exit 1
fi

# Check if auth service is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️  Warning: Auth service may not be running on http://localhost:8000"
    echo "   Start it with: uvicorn src.main:app --reload --port 8000"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create reports directory
mkdir -p reports

# Determine script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPORT_FILE="$SCRIPT_DIR/reports/quick_test_$(date +%Y%m%d_%H%M%S).html"

echo "🚀 Starting load test..."
echo "   Users: 10"
echo "   Spawn rate: 2 users/sec"
echo "   Duration: 2 minutes"
echo "   Report: $REPORT_FILE"
echo ""

# Run locust in headless mode
locust \
    -f "$SCRIPT_DIR/locustfile.py" \
    --host=http://localhost:8000 \
    --users 10 \
    --spawn-rate 2 \
    --run-time 2m \
    --headless \
    --html "$REPORT_FILE" \
    --loglevel INFO

echo ""
echo "✅ Test completed!"
echo "📊 Report saved to: $REPORT_FILE"
echo ""
echo "Next steps:"
echo "  1. Open the HTML report in your browser"
echo "  2. Review response times and error rates"
echo "  3. Run larger tests: tests/load/README.md"
