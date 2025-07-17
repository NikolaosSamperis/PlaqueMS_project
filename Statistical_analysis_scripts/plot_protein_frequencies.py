#!/usr/bin/env python3
"""
plot_protein_frequencies.py

Author: Nikolaos Samperis, 2025

Purpose:
    - Generate a publication-quality bar plot visualizing the frequency (number of hits) for each protein,
      from the Pareto front 1 (multi-objective evolutionary algorithm feature selection in proteomics analysis).
    - Accepts input in .xlsx, .xls, or .csv format, with a single row where columns represent proteins and values are counts.
    - Saves the resulting bar plot as a PNG image.

Inputs:
    - <input_excel_or_csv>: Path to an Excel or CSV file with a single row of protein counts.
        • Each column should be a protein identifier (e.g., gene symbol, UniProt ID).
        • The row values should be integer counts or frequencies.
    - [<output_png>]: (Optional) Output file path for the PNG plot. If omitted, uses the input filename with .png extension.

Outputs:
    - PNG bar plot illustrating frequency (number of hits) for each protein.

Usage:
    python plot_protein_frequencies.py <input_excel_or_csv> [<output_png>]
"""

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt

def usage():
    """
    Print usage instructions for the script and exit.
    """
    print(f"Usage: {sys.argv[0]} <input_excel_or_csv> [<output_png>]")
    print("  <input_excel_or_csv>: an .xlsx/.xls or .csv file with exactly one row of protein counts")
    print("  [<output_png>]: (optional) path where the PNG plot will be saved. If omitted,")
    print("                  it will be <same basename as input> + '.png'.")
    sys.exit(1)

def main():
    """
    Main function to load protein count data, check validity, generate, and save a bar plot.
    """
    if not (2 <= len(sys.argv) <= 3):
        usage()

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        print(f"Error: input file '{input_path}' does not exist.")
        sys.exit(1)

    # Determine output PNG path: either provided or constructed from input
    if len(sys.argv) == 3:
        output_png = sys.argv[2]
    else:
        base, _ext = os.path.splitext(input_path)
        output_png = base + ".png"

    # Load the data (supporting Excel or CSV)
    ext = os.path.splitext(input_path)[1].lower()
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(input_path)
        elif ext == ".csv":
            df = pd.read_csv(input_path)
        else:
            print(f"Error: unrecognized file extension '{ext}'. Must be .xlsx, .xls, or .csv.")
            sys.exit(1)
    except Exception as e:
        print(f"Error reading '{input_path}': {e}")
        sys.exit(1)

    # Ensure the file contains at least one row
    if df.shape[0] < 1:
        print(f"Error: '{input_path}' must contain at least one row of data.")
        sys.exit(1)

    # Extract protein names and counts from the first row
    row = df.iloc[0]
    proteins = list(row.index)
    counts = list(row.values.astype(int))

    # Generate the bar plot
    plt.figure(figsize=(10, 6))
    plt.bar(proteins, counts)
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Number of Hits", fontsize=11, labelpad=14)
    plt.xlabel("Proteins", fontsize=11, labelpad=20)
    plt.title("Protein Hit Count in Final Pareto Front 1 (Cellular Proteome)", fontsize=12, pad=14)
    plt.tight_layout(rect=(0.05, 0.1, 0.95, 0.95))

    # Save the plot as PNG
    try:
        plt.savefig(output_png, dpi=300)
        print(f"Bar plot saved to '{output_png}'")
    except Exception as e:
        print(f"Error saving plot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
