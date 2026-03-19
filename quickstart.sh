#!/bin/bash
# Quick start script for vending system

echo "=================================================="
echo "Vending System v2.0 - Quick Start"
echo "=================================================="
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Run setup verification
echo "Running setup verification..."
python3 test_setup.py

echo ""
echo "=================================================="
echo "Quick Commands:"
echo "=================================================="
echo ""
echo "1. Start Dashboard:"
echo "   python3 app.py"
echo "   Then visit: http://localhost:5000"
echo ""
echo "2. Collect Today's Data:"
echo "   python3 collect_data.py"
echo ""
echo "3. Send Test Email:"
echo "   python3 email_report.py"
echo ""
echo "4. Load Historical Data:"
echo "   python3 load_historical.py 2025-01-01 2025-12-31"
echo ""
echo "5. Run Daily Automation:"
echo "   python3 daily_automation.py"
echo ""
echo "=================================================="
