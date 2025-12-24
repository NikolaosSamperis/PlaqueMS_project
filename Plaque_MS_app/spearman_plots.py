import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import spearmanr
import sys
import os

def main(pred_file, ct_file):
    # Output base directory
    outdir = os.path.dirname(os.path.abspath(__file__))
    basename = os.path.splitext(os.path.basename(pred_file))[0]

    # Load data
    pred = pd.read_excel(pred_file)
    ct = pd.read_excel(ct_file)

    # Prepare predicted probabilities
    pred['P(calcified)'] = pd.to_numeric(pred['P(calcified)'], errors='coerce')

    # Merge dataframes on PatientID
    merged = pd.merge(pred, ct, on='PatientID')

    # Which CT score columns to analyze
    score_cols = ['Score', 'EQ_Mass_[mg]', 'Volume_[mm3]']

    # For saving metrics
    metrics = []

    for score in score_cols:
        subset = merged[['P(calcified)', score]].dropna()
        x = subset['P(calcified)']
        y = subset[score]

        rho, pval = spearmanr(x, y)
        metrics.append({
            'Score': score,
            "Spearman_rho": round(rho, 4),
            "p_value": "{:.2e}".format(pval),
            "N": len(subset)
        })

        # Plot
        plt.figure(figsize=(4.5, 4))
        sns.regplot(x=x, y=y, scatter_kws={'s':55, 'color':'#226699', 'edgecolor':'w', 'alpha':0.8}, line_kws={'color':'#BB3333', 'lw':2}, ci=None)
        plt.xlabel('Predicted probability of calcified', fontsize=12)
        plt.ylabel(score, fontsize=12)
        plt.title(f"Spearman’s ρ = {rho:.2f}, p = {pval:.1g}", fontsize=13)
        plt.tight_layout()
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
        print("Usage: python scriptname.py <Calcification_pred_EXTRACT.xlsx> <CT_calcification_scores_merged_prot.xlsx>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
