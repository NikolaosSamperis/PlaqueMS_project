#!/usr/bin/env python3
"""
group_stats.py

Author: Nikolaos Samperis, 2025

Purpose:
    - Compare predicted calcification probabilities across groups defined by CT-verified calcification status
      (0 = non-calcified, 1 = mixed, 2 = calcified).
    - Output descriptive group statistics (mean, median, N).
    - Perform one-way ANOVA (parametric) and Kruskal–Wallis (nonparametric) tests.
    - If global tests are significant, run post-hoc tests:
        • Tukey's HSD (after ANOVA)
        • Dunn's test with Bonferroni correction (after Kruskal–Wallis)
    - Save all results (per-group stats, global tests, post-hoc tests) in a human-readable TSV file.

Inputs:
    - pred_file: Excel file with predicted probabilities; must contain [PatientID, P(calcified)]
    - cta_file: Excel file with CT classification; must contain [PatientID, Calcified]

Outputs:
    - group-level .tsv file with [PatientID, Group, P(calcified)]
    - summary statistics and statistical test results .tsv file

Usage:
    python group_stats.py <Predictions.xlsx> <Liste_CTA_vienna.xlsx>
"""

import sys
import os
import pandas as pd
from scipy.stats import f_oneway, kruskal

def main(pred_file, cta_file):
    """
    Main function to merge data, compute group statistics, and perform group comparisons.

    Args:
        pred_file (str): Path to Excel file with predicted probabilities
        cta_file (str): Path to Excel file with CT-based group assignments
    """
    import warnings
    warnings.filterwarnings("ignore")  # Clean output for terminal
    # For post-hoc tests:
    from statsmodels.stats.multicomp import pairwise_tukeyhsd
    import scikit_posthocs as sp

    # Load files
    pred = pd.read_excel(pred_file)
    cta = pd.read_excel(cta_file)

    # Merge on PatientID
    merged = pd.merge(pred, cta[['PatientID', 'Calcified']], on='PatientID', how='inner')
    # Map group labels for clarity
    group_map = {0: 'Non-calcified', 1: 'Mixed', 2: 'Calcified'}
    merged['Group'] = merged['Calcified'].map(group_map)
    merged = merged[['PatientID', 'Group', 'P(calcified)']]

    # Save group-level data
    outdir = os.path.dirname(os.path.abspath(pred_file))
    base = os.path.splitext(os.path.basename(pred_file))[0]
    out_groups = os.path.join(outdir, f"{base}_groups.tsv")
    merged.to_csv(out_groups, sep='\t', index=False)
    print(f"Saved group-level data: {out_groups}")

    # Calculate per-group descriptive stats (N, mean, median)
    stats = []
    for group in ['Non-calcified', 'Mixed', 'Calcified']:
        vals = merged.loc[merged['Group'] == group, 'P(calcified)']
        stats.append({
            "Group": group,
            "N": len(vals),
            "Mean": round(vals.mean(), 4),
            "Median": round(vals.median(), 4)
        })
    stats_df = pd.DataFrame(stats)

    # Prepare group arrays for statistical testing
    group_noncalc = merged.loc[merged['Group'] == 'Non-calcified', 'P(calcified)']
    group_mixed   = merged.loc[merged['Group'] == 'Mixed', 'P(calcified)']
    group_calc    = merged.loc[merged['Group'] == 'Calcified', 'P(calcified)']

    # Run ANOVA
    F_stat, p_val = f_oneway(group_noncalc, group_mixed, group_calc)
    # Run Kruskal-Wallis
    H_stat, p_kruskal = kruskal(group_noncalc, group_mixed, group_calc)

    # Conditional post-hoc pairwise comparisons if global test is significant
    posthoc_blocks = []  # List of (header, DataFrame)

    # Tukey's HSD if ANOVA is significant
    if p_val < 0.05:
        print("\nANOVA is significant (p < 0.05): Running Tukey's HSD test...")
        tukey = pairwise_tukeyhsd(merged['P(calcified)'], merged['Group'])
        tukey_df = pd.DataFrame(data=tukey.summary().data[1:], columns=tukey.summary().data[0])
        posthoc_blocks.append(("# Tukey's HSD post-hoc results\n", tukey_df))
        print(tukey)

    # Dunn's test if Kruskal–Wallis is significant
    if p_kruskal < 0.05:
        print("\nKruskal–Wallis is significant (p < 0.05): Running Dunn's test (Bonferroni correction)...")
        dunn = sp.posthoc_dunn(
            merged, 
            val_col='P(calcified)', 
            group_col='Group', 
            p_adjust='bonferroni'
        )
        # Convert from matrix form to long-form DataFrame for easier reading
        dunn_long = dunn.stack().reset_index()
        dunn_long.columns = ['Group1', 'Group2', 'p-value']
        dunn_long = dunn_long[dunn_long['Group1'] != dunn_long['Group2']]
        posthoc_blocks.append(("# Dunn's test (Bonferroni) post-hoc results\n", dunn_long))
        print(dunn)

    # Save all results (stats, global tests, post-hoc) to a single TSV
    out_stats = os.path.join(outdir, f"{base}_summary_stats.tsv")
    with open(out_stats, 'w') as f:
        # Write group stats
        stats_df.to_csv(f, sep='\t', index=False)
        f.write('\n# ANOVA and Kruskal–Wallis results\n')
        f.write('Test\tStatistic\tp-value\n')
        f.write(f'ANOVA\t{F_stat:.4f}\t{p_val:.4g}\n')
        f.write(f'Kruskal\t{H_stat:.4f}\t{p_kruskal:.4g}\n')

    # Append post-hoc blocks if any were performed
    if posthoc_blocks:
        with open(out_stats, 'a') as f:
            for header, df in posthoc_blocks:
                f.write('\n' + header)
                df.to_csv(f, sep='\t', index=False)
                f.write('\n')

    print(f"Saved summary stats: {out_stats}")

if __name__ == "__main__":
    # Command-line interface for the script
    if len(sys.argv) != 3:
        print("Usage: python group_stats.py <Predictions.xlsx> <Liste_CTA_vienna.xlsx>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
