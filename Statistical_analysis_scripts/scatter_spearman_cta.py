#!/usr/bin/env python3

"""
scatter_spearman_cta.py

Author: Nikolaos Samperis, 2025

Purpose:
    - Calculate the Spearman correlation (with bootstrapped 95% CI) between machine-learning predicted 
      calcification probabilities and manual CTA status (0 = non-calcified, 1 = mixed, 2 = calcified).
    - Generate a scatter/regression plot annotated with correlation statistics.
    - Save the plot (PNG) and the main metrics (TSV).

Inputs:
    - pred_file: Excel file with columns [PatientID, P(calcified)]
    - ct_file: Excel file with columns [PatientID, Calcified]

Outputs:
    - PNG scatter plot showing predicted probability vs. CTA status
    - TSV file with Spearman correlation and bootstrapped confidence intervals

Usage:
    python scatter_spearman_cta.py <Calcification_pred_EXTRACT.xlsx> <Liste_CTA_vienna.xlsx>
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns
from scipy.stats import spearmanr
import numpy as np
import sys
import os

def bootstrap_spearman(x, y, n_boot=5000, seed=42):
    """
    Bootstraps the Spearman correlation between two variables to estimate 95% confidence intervals.

    Args:
        x (pd.Series): First variable
        y (pd.Series): Second variable
        n_boot (int): Number of bootstrap samples
        seed (int): Random seed

    Returns:
        tuple: (rho_ci, pval_ci, rhos, pvals)
            - rho_ci (np.ndarray): [lower, upper] CI for Spearman's rho
            - pval_ci (np.ndarray): [lower, upper] CI for p-value
            - rhos (np.ndarray): All bootstrapped rho values
            - pvals (np.ndarray): All bootstrapped p-values
    """
    rng = np.random.default_rng(seed)
    rhos = []
    pvals = []
    n = len(x)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        x_s = x.iloc[idx].reset_index(drop=True)
        y_s = y.iloc[idx].reset_index(drop=True)
        rho, pval = spearmanr(x_s, y_s)
        rhos.append(rho)
        pvals.append(pval)
    # Compute 95% CI
    rhos = np.array(rhos)
    pvals = np.array(pvals)
    rho_ci = np.percentile(rhos, [2.5, 97.5])
    pval_ci = np.percentile(pvals, [2.5, 97.5])
    return rho_ci, pval_ci, rhos, pvals

def main(pred_file, ct_file):
    """
    Main function to load data, merge, compute correlation, plot, and save outputs.
    """
    # Output base directory
    outdir = os.path.dirname(os.path.abspath(__file__))
    basename = os.path.splitext(os.path.basename(pred_file))[0]

    # Load data
    pred = pd.read_excel(pred_file)
    ct   = pd.read_excel(ct_file)

    # Ensure P(calcified) is numeric
    pred['P(calcified)'] = pd.to_numeric(pred['P(calcified)'], errors='coerce')

    # Merge on PatientID; keep only the columns we need
    merged = pd.merge(pred, ct[['PatientID', 'Calcified']], on='PatientID')

    # Drop any rows with missing in P(calcified) or Calcified
    subset = merged[['P(calcified)', 'Calcified']].dropna()
    prob   = subset['P(calcified)'] * 100     # convert to percentage
    cta    = subset['Calcified']              # 0,1,2

    # Spearman’s correlation
    rho, pval = spearmanr(prob, cta)
    print(f"Spearman’s ρ = {rho:.4f}, p-value = {pval:.2e}, N = {len(subset)}")

    # ==== Bootstrapping ====
    rho_ci, pval_ci, rhos, pvals = bootstrap_spearman(prob, cta, n_boot=2000)
    print(f"95% CI for rho: [{rho_ci[0]:.3f}, {rho_ci[1]:.3f}]")
    print(f"95% CI for p-value: [{pval_ci[0]:.3g}, {pval_ci[1]:.3g}]")

    # ========== Plot ==========
    plt.figure(figsize=(5, 4))
    ax = plt.gca()

    # Use seaborn.regplot with x=CTA status (0,1,2) and y=predicted probability (%)
    #   • jitter the x‐values so discrete values don’t overlap
    #   • draw the regression line first (lower zorder), then scatter points on top (higher zorder)
    sns.regplot(
        x=cta,
        y=prob,
        scatter_kws={
            's': 50,
            'color': '#226699',
            'edgecolor': 'white',
            'alpha': 0.85,
            'zorder': 5          # ensure points draw on top
        },
        line_kws={
            'color': '#BB3333',
            'lw': 2,
            'zorder': 3          # regression line underneath points
        },
        ci=None,
        x_jitter=0.12,            # small horizontal jitter for discrete CTA=0/1/2
        y_jitter=0.0,            # no need to jitter y since it’s continuous
        ax=ax
    )

    # Axes limits & ticks
    ax.set_ylim(0, 100)                      # 0%–100%
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_yticklabels([f"{v:.2f}" for v in [0,20,40,60,80,100]])
    ax.tick_params(axis='y', labelsize=8)

    ax.set_xlim(-0.3, 2.3)                   # leave a bit of room left/right of 0–2
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(['0', '1', '2'])
    ax.tick_params(axis='x', labelsize=8)

    # X and Y labels, with explanatory sub-labels
    ax.set_xlabel("CTA status", fontsize=8, labelpad=8)
    ax.text(
        0.5,                      
        -0.24,                        
        "(0 = non-calcified, 1 = mixed, 2 = calcified)",
        ha='center',
        va='top',
        fontsize=6,
        transform=ax.transAxes
    )
    # Y‐axis label
    ax.set_ylabel("Predicted probability of calcified (%)", fontsize=8, labelpad=8)

    # Main title with Spearman’s ρ and 95% CI
    ax.text(
        0.100, 1.05,    # 0.20 = x (from left), 1.05 = y (just above plot)
        f"Spearman’s ρ = {rho:.2f}",
        fontsize=8, ha='left', va='bottom', transform=ax.transAxes
    )
    ax.text(
        0.454, 1.0547,
        f"[95% CI: {rho_ci[0]:.2f}, {rho_ci[1]:.2f}], p = {pval:.2g}",
        fontsize=7, ha='left', va='bottom', color="#444444",
        transform=ax.transAxes
    )

    # Remove grid and spines if desired
    plt.grid(False)
    sns.despine(trim=True, offset=4)

    # Tweak layout so labels aren’t cut off
    plt.tight_layout(rect=(0.05, 0, 0.95, 0.90))   # leave a bit of top margin for title and bottom for x‐label

    # Save plot to PNG
    outpath = os.path.join(outdir, f"{basename}_flipped_axes.png")
    plt.savefig(outpath, dpi=300)
    plt.close()

    print(f"Saved plot to: {outpath}")

    # Save metrics with bootstrapped intervals to TSV
    metrics = pd.DataFrame([{
        'N': len(subset),
        'Spearman_rho': round(rho, 4),
        'rho_CI_lower': round(rho_ci[0], 4),
        'rho_CI_upper': round(rho_ci[1], 4),
        'p_value': "{:.2e}".format(pval),
        'p_CI_lower': "{:.2e}".format(pval_ci[0]),
        'p_CI_upper': "{:.2e}".format(pval_ci[1])
    }])
    out_metrics = os.path.join(outdir, f"{basename}_vs_CT_calcification_status_metrics.tsv")
    metrics.to_csv(out_metrics, sep='\t', index=False)
    print(f"Saved metrics to: {out_metrics}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python scatter_spearman_cta.py <Calcification_pred_EXTRACT.xlsx> <Liste_CTA_vienna.xlsx>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
