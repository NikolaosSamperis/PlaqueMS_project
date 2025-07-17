#!/usr/bin/env python3
"""
spearman_plots.py

Author: Nikolaos Samperis, 2025

Purpose:
    - Assess the association between machine-learning predicted calcification probabilities
      and continuous CT-derived measures of calcification burden (e.g., Agatson score, mass, volume).
    - Compute Spearman’s rank correlation coefficient (ρ) and bootstrapped 95% confidence intervals for each CT metric.
    - Generate scatter/regression plots for each CT metric with correlation annotations.
    - Output summary statistics for each metric as a TSV file.

Inputs:
    - pred_file: Excel file containing [PatientID, P(calcified)]
    - ct_file:   Excel file containing [PatientID, Score, EQ_Mass_[mg], Volume_[mm3]]

Outputs:
    - PNG plot for each CT metric, showing regression and correlation annotation
    - TSV file summarizing correlation statistics for each metric

Usage:
    python spearman_plots.py <Calcification_pred_EXTRACT.xlsx> <CT_calcification_scores_merged_prot.xlsx>
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns
import numpy as np
from scipy.stats import spearmanr
import sys
import os

def bootstrap_spearman(x, y, n_boot=5000, seed=42):
    """
    Bootstraps the Spearman correlation coefficient between two variables
    to estimate its 95% confidence interval.

    Args:
        x (pd.Series): First variable
        y (pd.Series): Second variable
        n_boot (int): Number of bootstrap replicates
        seed (int): Random seed

    Returns:
        np.ndarray: [lower, upper] bounds of the bootstrapped CI for ρ
    """
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
    Main routine to load data, merge, compute correlations, and plot results.

    Args:
        pred_file (str): Path to predictions Excel file
        ct_file (str): Path to CT metrics Excel file
    """
    # Output base directory
    outdir = os.path.dirname(os.path.abspath(__file__))
    basename = os.path.splitext(os.path.basename(pred_file))[0]

    # Load data
    pred = pd.read_excel(pred_file)
    ct = pd.read_excel(ct_file)

    # Ensure probabilities are numeric
    pred['P(calcified)'] = pd.to_numeric(pred['P(calcified)'], errors='coerce')

    # Merge on PatientID; assume all CT metric columns are present
    merged = pd.merge(pred, ct, on='PatientID')

    # Which CT score columns to analyze
    score_cols = ['Score', 'EQ_Mass_[mg]', 'Volume_[mm3]']

    # For saving correlation metrics
    metrics = []

    # Custom y-axis labels mapping
    ylabels = {
        'Score': 'CT score (Agatson units)',
        'EQ_Mass_[mg]': 'EQ Mass (mg)',
        'Volume_[mm3]': 'Volume (mm³)'
    }

    # For each CT metric: compute correlation, save metrics, and plot
    for score in score_cols:
        subset = merged[['P(calcified)', score]].dropna()
        x = subset['P(calcified)']
        y = subset[score]

        # Bootstrapped CI for Spearman's rho
        rho_ci = bootstrap_spearman(x, y, n_boot=5000)
        
        # Compute Spearman's correlation and p-value
        rho, pval = spearmanr(x, y)
        metrics.append({
            'Score': score,
            "Spearman_rho": round(rho, 4),
            "rho_CI_lower": round(rho_ci[0], 4),
            "rho_CI_upper": round(rho_ci[1], 4),
            "p_value": "{:.2e}".format(pval),
            "N": len(subset)
        })

        # Generate scatter/regression plot
        plt.figure(figsize=(4.5, 4))
        sns.regplot(
            x=x * 100, y=y, # Convert probabilities to percentage for x-axis
            scatter_kws={'s':38, 'color':'#226699', 'edgecolor':'w', 'alpha':0.8},  # Smaller points
            line_kws={'color':'#BB3333', 'lw':2},
            ci=None
        )
        plt.xlabel('Predicted probability of calcified (%)', fontsize=7, labelpad=11)
        plt.ylabel(ylabels[score], fontsize=7, labelpad=9)
        plt.xticks(fontsize=7)
        plt.yticks(fontsize=7)
        plt.gca().xaxis.set_major_formatter(mtick.FormatStrFormatter('%.2f'))
        ax = plt.gca()

        # Main title with Spearman’s ρ and CI
        ax.text(
            0.043, 1.09,    # 0.096 = x (from left), 1.06 = y (just above plot)
            f"Spearman’s ρ = {rho:.2f}",
            fontsize=8, ha='left', va='bottom', transform=ax.transAxes
        )
        ax.text(
            0.461, 1.0948,
            f"[95% CI: {rho_ci[0]:.2f}, {rho_ci[1]:.2f}], p = {pval:.2g}",
            fontsize=7, ha='left', va='bottom', color="#444444",
            transform=ax.transAxes
        )
        plt.tight_layout(rect=(0.05, 0.05, 0.90, 0.90))
        plt.grid(False)
        sns.despine()
        plt.savefig(os.path.join(outdir, f"{basename}_vs_{score.replace(' ', '_').replace('[','').replace(']','')}.png"), dpi=300)
        plt.close()

    # Save correlation results as TSV
    out_metrics = os.path.join(outdir, f"{basename}_spearman_metrics.tsv")
    pd.DataFrame(metrics).to_csv(out_metrics, sep='\t', index=False)
    print(f"\nSaved correlation metrics to {out_metrics}")
    print(f"Saved PNG scatterplots to {outdir}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python spearman_plots.py <Calcification_pred_EXTRACT.xlsx> <CT_calcification_scores_merged_prot.xlsx>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
