#!/bin/bash
# Generate annotated coverage files in coverage/ directory

echo "Running tests with coverage..."
pytest --cov=multiclaude --cov-report=term-missing

echo -e "\nGenerating annotated coverage files..."
rm -rf coverage
mkdir -p coverage
coverage annotate -d coverage

echo -e "\nAnnotated coverage files created in coverage/"
echo "Example: cat coverage/z_*_tasks.py,cover"