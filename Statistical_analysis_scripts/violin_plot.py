#!/usr/bin/env python3
"""
violin_plot.py

Author: Nikolaos Samperis, 2025

Purpose:
    - Create a publication-quality violin plot showing the distribution of predicted calcification probabilities 
      across groups defined by CT-verified status (0 = non-calcified, 1 = mixed, 2 = calcified).
    - Annotate the plot with Spearman’s correlation coefficient (ρ), bootstrapped 95% CI, and p-value.
    - Overlay quartile and median lines and include a custom legend.
    - Save the plot as a PNG file.

Inputs:
    - pred_file: Excel file with [PatientID, P(calcified)]
    - ct_file:   Excel file with [PatientID, Calcified] (CT status; 0, 1, 2)

Outputs:
    - PNG violin plot showing distributions by group and annotation with correlation statistics.

Usage:
    python violin_plot.py <Calcification_pred_EXTRACT.xlsx> <Liste_CTA_vienna.xlsx>
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import spearmanr
import sys
import os
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

def bootstrap_spearman(x, y, n_boot=5000, seed=42):
    rng = np.random.default_rng(seed)
    rhos = []
    n = len(x)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        x_s = x.iloc[idx].reset_index(drop=True)
        y_s = y.iloc[idx].reset_index(drop=True)
        rho, _ = spearmanr(x_s, y_s)
        rhos.append(rho)
    rhos = np.array(rhos)
    rho_ci = np.percentile(rhos, [2.5, 97.5])
    return rho_ci

def main(pred_file, ct_file):
    """
    Main function to load, clean, and merge data, calculate statistics, 
    and generate a violin plot with custom annotations.

    Args:
        pred_file (str): Path to Excel file with predicted probabilities
        ct_file (str): Path to Excel file with CT-based calcification groups
    """
    # 1. Load predicted probabilities and clean columns
    pred = pd.read_excel(pred_file)
    # Remove any pre-existing 'Calcified' column to avoid ambiguity
    if 'Calcified' in pred.columns:
        pred = pred.drop(columns=['Calcified'])
    # Ensure probability column is numeric
    pred['P(calcified)'] = pd.to_numeric(pred['P(calcified)'], errors='coerce')

    # Load the CTA reference file
    ct = pd.read_excel(ct_file)
    if 'Calcified' not in ct.columns:
        raise KeyError("Expected a column named 'Calcified' in the CTA file but did not find it.")
    # Rename for clarity in merged DataFrame
    ct = ct.rename(columns={'Calcified': 'Calcified_true'})[['PatientID', 'Calcified_true']]

    # Merge prediction and CT status on PatientID; drop rows with missing data
    merged = pd.merge(pred, ct, on='PatientID', how='inner')
    merged = merged[['P(calcified)', 'Calcified_true']].dropna()

    # Extract x (probabilities) and y (CTA labels)
    x = merged['P(calcified)']
    y = merged['Calcified_true']

    # Compute Spearman’s correlation (and p-value)
    rho, pval = spearmanr(x, y)
    print(f"Spearman’s ρ = {rho:.4f}, p-value = {pval:.2e}, N = {len(merged)}")

    # === Bootstrapped 95% CI for rho ===
    rho_ci = bootstrap_spearman(x, y, n_boot=5000)
    print(f"Bootstrapped 95% CI for rho: [{rho_ci[0]:.3f}, {rho_ci[1]:.3f}]")

    # Plot violin plots with custom settings
    plt.figure(figsize=(6, 4))

    custom_palette = [
        "#AEBEE3",  # CTA = 0 (light blue)
        "#66C2A5",  # CTA = 1 (teal)
        "#FC8D62"   # CTA = 2 (orange)
    ]

    # Create the violin plot for each group (0, 1, 2)
    sns.violinplot(
        x='Calcified_true',
        y='P(calcified)',
        hue='Calcified_true',
        data=merged,
        palette=custom_palette,
        inner='quartile',
        linewidth=1.2,
        cut=0,
        legend=False
    )

    # Overlay individual sample points (jittered for visual clarity)
    jitter_strength = 0.12
    xs = merged['Calcified_true'] + np.random.uniform(-jitter_strength, jitter_strength, size=len(merged))
    ys = merged['P(calcified)']
    plt.scatter(
        xs,
        ys,
        s=20,
        color='#2166AC',   # a dark blue for maximum contrast
        edgecolor='white',
        alpha=0.7,
        linewidth=0.5,
        zorder=5
    )

    # Custom legend: lines for median and quartiles
    legend_handles = [
        Line2D([0], [0], color='black', linestyle='--', linewidth=1.2,
               label='Median (50th percentile)'),
        Line2D([0], [0], color='black', linestyle=':', linewidth=1.2,
               label='Quartiles (25th & 75th)')
    ]

    # Place the legend outside the main plotting area on the right, centered vertically
    plt.legend(
        handles=legend_handles,
        loc='center left',
        bbox_to_anchor=(1.02, 0.5),
        fontsize=7,
        frameon=False
    )

    # Final plot formatting: axis labels, ticks, annotation, etc.
    ax = plt.gca()

    ax.set_ylim(0, 1)
    ax.margins(y=0.10)

    # Format the y‐axis tick labels as percentages with two decimals (e.g. “80.00%”)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x * 100:.2f}"))

    # X-axis: label and group names
    ax.set_xlabel("CTA status", fontsize=8, labelpad=13)
    ax.text(
        x=0.5, 
        y=-0.30, 
        s="(0 = non-calcified, 1 = mixed, 2 = calcified)",
        ha='center', 
        va='top',
        fontsize=7,
        transform=ax.transAxes
    )
    ax.xaxis.set_label_coords(0.5, -0.20)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(['0', '1', '2'])
    ax.tick_params(axis='x', labelsize=8)

    # Y-axis: label
    ax.set_ylabel("Predicted probability of calcified (%)", fontsize=8, labelpad=10)
    ax.tick_params(axis='y', labelsize=8)

    # Annotate with main correlation results (Main title)
    ax.text(
        0.040, 1.05,    # 0.20 = x (from left), 1.05 = y (just above plot)
        f"Spearman’s ρ = {rho:.2f}",
        fontsize=8, ha='left', va='bottom', transform=ax.transAxes
    )

    # CI and p-value (smaller font, just next to the title)
    ax.text(
        0.462, 1.0547,
        f"[95% CI: {rho_ci[0]:.2f}, {rho_ci[1]:.2f}], p = {pval:.2g}",
        fontsize=7, ha='left', va='bottom', color="#444444",
        transform=ax.transAxes
    )

    # Remove top/right spines, adjust layout, and save PNG
    sns.despine(offset=4, trim=True)
    plt.tight_layout(rect=(0.05, 0.03, 1.0, 0.94))

    # Save the figure as PNG
    try:
        outdir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        outdir = os.getcwd()
    basename = os.path.splitext(os.path.basename(pred_file))[0]
    out_png = os.path.join(outdir, f"{basename}_violin_custom.png")
    plt.savefig(out_png, dpi=300)
    plt.close()

    print(f"Saved violin plot (custom) to: {out_png}")


if __name__ == '__main__':
    # Command-line usage check
    if len(sys.argv) != 3:
        print("Usage: python violin_plot.py <Calcification_pred_EXTRACT.xlsx> <Liste_CTA_vienna.xlsx>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
