#!/bin/bash

echo "Compiling Poneglyph-Reduce Documentation..."

# First pass
echo "First LaTeX pass..."
pdflatex main.tex

# Bibliography
echo "Processing bibliography..."
bibtex main

# Second pass (for references)
echo "Second LaTeX pass..."
pdflatex main.tex

# Third pass (for cross-references)
echo "Third LaTeX pass..."
pdflatex main.tex

echo "Documentation compiled successfully!"
echo "Output: main.pdf"

# Clean up auxiliary files (optional)
# rm -f *.aux *.bbl *.blg *.log *.out *.toc
