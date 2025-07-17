#!/usr/bin/env python3
"""
asymptomatic_compare_saveplot.py

Author: Nikolaos Samperis, 2025

Purpose:
    - Compare model-predicted calcification probabilities between 'Asymptomatic' and 'Symptomatic' patient groups.
    - Compute descriptive statistics, Mann–Whitney U test, AUC (and its 95% CI by bootstrapping), and Cliff’s delta effect size.
    - Save results to a human-readable TSV file.
    - Generate and save a violin plot (PNG) showing distributions per group, annotated with stats.

Inputs:
    - model_xlsx: Excel file with predicted probabilities, columns including 'Subject ID' and 'P(calcified)'
    - meta_xlsx: Excel file with patient metadata, including 'STUDY_NUMBER' and 'AsymptSympt2G' (status)

Outputs:
    - TSV file with summary statistics and test results (default: symptomatic_stats.tsv)
    - PNG violin plot (default: violin_symptomatic.png)

Usage:
    python asymptomatic_compare_saveplot.py <model_xlsx> <meta_xlsx> [--outplot PNG] [--outstats TSV]
"""

import argparse
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import mannwhitneyu

# ───── helper ────────────────────────────────────────────────────────────────
def clean_id(series):
    """
    Remove any 'AE'/'ae' prefix and convert IDs to integers.

    Args:
        series (pd.Series): Series of patient/sample IDs (possibly strings).

    Returns:
        pd.Series: Cleaned IDs as integers.
    """
    return (series.astype(str)
                 .str.replace(r'(?i)^ae', '', regex=True)
                 .astype(int))

def clean_prob(series):
    """
    Clean probability values: remove non-numeric characters, standardize decimal, ensure [0,1] range.

    Args:
        series (pd.Series): Predicted probabilities as strings/numbers.

    Returns:
        np.ndarray: Cleaned probabilities as floats, forced to [0,1] if needed.
    """
    s = (series.astype(str)
                 .str.replace('[^0-9,.-]', '', regex=True)
                 .str.replace(',', '.', regex=False))
    s = pd.to_numeric(s, errors='coerce')
    return np.where(s > 1.0, s/100.0, s)

def summarise(a):
    """
    Calculate summary statistics for a numeric array.

    Args:
        a (np.ndarray): 1D numeric array

    Returns:
        tuple: (N, mean, median, Q1, Q3)
    """
    q1, med, q3 = np.percentile(a, [25, 50, 75])
    return len(a), a.mean(), med, q1, q3

def auc_from_u(u, n1, n2):
    """
    Compute the AUC from Mann–Whitney U statistic (identical to ROC-AUC for binary group comparison).

    Args:
        u (float): Mann–Whitney U statistic
        n1 (int): size of group 1
        n2 (int): size of group 2

    Returns:
        float: Estimated AUC
    """
    return u / (n1*n2)

def bootstrap_auc(x, y, n_boot=10_000, seed=42):
    """
    Estimate 95% CI for AUC by bootstrapping.

    Args:
        x (np.ndarray): Predicted probabilities for group 1
        y (np.ndarray): Predicted probabilities for group 2
        n_boot (int): Number of bootstrap replicates
        seed (int): Random seed

    Returns:
        tuple: (low_CI, high_CI)
    """
    rng = np.random.default_rng(seed)
    n1, n2 = len(x), len(y)
    aucs = []
    for _ in range(n_boot):
        xb = rng.choice(x, n1, replace=True)
        yb = rng.choice(y, n2, replace=True)
        uu, _ = mannwhitneyu(xb, yb)
        aucs.append(auc_from_u(uu, n1, n2))
    return np.percentile(aucs, [2.5, 97.5])

# ────────────────────────────
#         MAIN ANALYSIS
# ────────────────────────────
def analyse(model_xlsx, meta_xlsx, outplot, outstats):
    """
    Main function to load, merge, clean, and compare asymptomatic vs symptomatic groups.

    Args:
        model_xlsx (str): Path to predictions Excel file
        meta_xlsx (str): Path to metadata Excel file
        outplot (str): Output path for PNG violin plot
        outstats (str): Output path for TSV summary
    """

    # 1. Load data ----------------------------------------------------------
    pred = pd.read_excel(model_xlsx)
    meta = pd.read_excel(meta_xlsx)

    # Clean and harmonize columns
    id_pred, prob = 'Subject ID', 'P(calcified)'
    id_meta, symptoms_col, asymptomatic_yes = 'STUDY_NUMBER', 'AsymptSympt2G', 'Asymptomatic'

    # 2. Clean & Merge -------------------------------------------------------
    pred[prob]    = clean_prob(pred[prob])
    pred[id_meta] = clean_id(pred[id_pred])

    # 3. Merge on common ID and drop any rows with missing data
    merged = (pred[[id_meta, prob]]
                .merge(meta[[id_meta, symptoms_col]], on=id_meta, how='inner')
                .dropna(subset=[prob, symptoms_col]))
    # Split into groups based on symptom status
    g_yes = merged[merged[symptoms_col] == asymptomatic_yes][prob].to_numpy()
    g_no  = merged[merged[symptoms_col] != asymptomatic_yes][prob].to_numpy()
    if not len(g_yes) or not len(g_no):
        sys.exit("Error: after merging, one AsymptSympt2G group is empty.")
    
    # 4. Compute summary statistics for both groups
    n_no,  mean_no,  med_no,  q1_no,  q3_no  = summarise(g_no)
    n_yes, mean_yes, med_yes, q1_yes, q3_yes = summarise(g_yes)

    # 5. Mann–Whitney U test, AUC, bootstrapped CI for AUC, Cliff's delta
    u, p   = mannwhitneyu(g_yes, g_no, alternative="two-sided")
    auc    = auc_from_u(u, len(g_yes), len(g_no))
    ci_low, ci_high = bootstrap_auc(g_yes, g_no)
    cliff  = 2*auc - 1

    # 6. Print summary results to console ---------------------------------------
    print("\n--- Descriptive summary (probabilities 0–1) ---")
    print(f"Symptomatic : n={n_no:3d}  mean={mean_no:.3f}  median={med_no:.3f}  "
          f"IQR=({q1_no:.3f}, {q3_no:.3f})")
    print(f"Asymptomatic    : n={n_yes:3d}  mean={mean_yes:.3f}  median={med_yes:.3f}  "
          f"IQR=({q1_yes:.3f}, {q3_yes:.3f})")
    print("\nU  =", int(u), " p =", f"{p:.4g}")
    print(f"AUC = {auc:.3f}  (95 % CI {ci_low:.3f}–{ci_high:.3f})  Cliff’s δ = {cliff:.3f}")

    # 7. Save summary statistics and test results to TSV ------------------------
    out_path = Path(outstats)
    with out_path.open("w", encoding="utf-8") as f:
        # Section 1 – per-group stats
        f.write("Group\tN\tMean\tMedian\tQ1\tQ3\n")
        f.write(f"Symptomatic\t{n_no}\t{mean_no:.3f}\t{med_no:.3f}\t{q1_no:.3f}\t{q3_no:.3f}\n")
        f.write(f"Asymptomatic\t{n_yes}\t{mean_yes:.3f}\t{med_yes:.3f}\t{q1_yes:.3f}\t{q3_yes:.3f}\n")

        # Section 2: statistical test results
        f.write("\n# Mann–Whitney U and effect-size results\n")
        f.write("Metric\tValue\n")
        f.write(f"U\t{int(u)}\n")
        f.write(f"p\t{p:.4g}\n")
        f.write(f"AUC\t{auc:.3f}\n")
        f.write(f"AUC_CI_low\t{ci_low:.3f}\n")
        f.write(f"AUC_CI_high\t{ci_high:.3f}\n")
        f.write(f"Cliffs_delta\t{cliff:.3f}\n")

    print(f"\nSaved readable summary: {out_path}")

    # 8. Create and save violin plot (if output path provided)--------------------
    if outplot:
        try:
            import seaborn as sns 
            import matplotlib.pyplot as plt
            from matplotlib.lines import Line2D
            from matplotlib.ticker import FuncFormatter

            plt.figure(figsize=(6,4))
            pal = ["#66C2A5", "#FC8D62"]   # Colour palette: Asymptomatic, Symptomatic

            # Build plotting DataFrame and category order
            plot_df = merged.assign(
                Symptoms = merged[symptoms_col].eq(asymptomatic_yes)
                                            .map({True:"Asymptomatic", False:"Symptomatic"}))
            order = ["Asymptomatic", "Symptomatic"]
            
            # Violin plot with quartile lines, coloured by group
            sns.violinplot(x="Symptoms", y=prob, hue="Symptoms",
                           data=plot_df, palette=pal,
                           order=order, hue_order=order,
                           inner='quartile', linewidth=1.2, cut=0, legend=False)

            # Overlay individual data points (jittered for visibility)
            x_positions = plot_df["Symptoms"].apply(order.index).to_numpy()
            x_jit = x_positions + np.random.uniform(-0.12, 0.12, len(plot_df))
            plt.scatter(x_jit, plot_df[prob],
                        s=22, color="#2166AC", edgecolor="white",
                        alpha=0.75, linewidth=0.4, zorder=5)

            # Custom legend for median/quartile lines
            handles = [Line2D([0],[0], color='black', ls='--', label='Median'),
                       Line2D([0],[0], color='black', ls=':',  label='Quartiles (25th & 75th)')]
            plt.legend(handles=handles, loc='center left',
                       bbox_to_anchor=(1.02,0.5), frameon=False, fontsize=7)

            ax = plt.gca()
            ax.tick_params(axis='both', which='major', labelsize=7)
            ax.set_ylim(0,1)
            ax.yaxis.set_major_formatter(FuncFormatter(lambda y,_: f"{y*100:.2f}"))
            ax.set_xlabel("Symptom status",  fontsize=8, labelpad=14)
            ax.set_ylabel("Predicted probability of calcified (%)", fontsize=8, labelpad=14)

            # Annotate with AUC, 95% CI, and p-value (two-line header style)
            ax.text(-0.073, 1.08,
                    f"AUC (Asymptomatic) = {auc:.2f}",
                    fontsize=8, ha='left', va='bottom', transform=ax.transAxes)
            ax.text(0.47, 1.086,
                    f"[95% CI: {ci_low:.2f}, {ci_high:.2f}], p(MWU) = {p:.4f}",
                    fontsize=7, ha='left', va='bottom', color="#444444",
                    transform=ax.transAxes)

            sns.despine(offset=4)
            plt.tight_layout(rect=(0.05,0.03,1.0,0.94))
            plt.savefig(outplot, dpi=300)
            plt.close()
            print(f"Saved violin plot to {outplot}")
        except ImportError:
            print("Plot skipped – install seaborn & matplotlib")

# ────────────────────────────
#         CLI WRAPPER
# ────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Compare symptomatic groups: statistics and violin plot"
    )
    ap.add_argument("model_xlsx", help="Path to predictions Excel file")
    ap.add_argument("meta_xlsx", help="Path to metadata Excel file")
    ap.add_argument("--outplot", default="violin_symptomatic.png", help="Output PNG file for plot")
    ap.add_argument("--outstats", default="symptomatic_stats.tsv", help="Output TSV file for stats")
    args = ap.parse_args()
    analyse(args.model_xlsx, args.meta_xlsx, args.outplot, args.outstats)
