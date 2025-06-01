from __future__ import annotations
import warnings
import io, os, math, joblib, re, numpy as np, pandas as pd
from scipy.special import expit
from functools import lru_cache
from django.conf import settings
from django.http import (
    JsonResponse,
    HttpResponseBadRequest,
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from neo4j import GraphDatabase, basic_auth

# ── helper: canonicalise protein names ────────────────────────────────────
def _clean(text: str) -> str:
    return (
        str(text)
        .replace("\ufeff", "")      # strip UTF-8 BOM
        .strip()                    # spaces / tabs / CR-LF
        .strip('"\'')               # surrounding quotes
        .upper()                    # case-insensitive match
    )

# ── regexes for numeric format detection ─────────────────────────────────
_re_amer = re.compile(r'^\d{1,3}(?:,\d{3})*(?:\.\d+)?$')
_re_euro = re.compile(r'^\d+(?:\.\d{3})*(?:,\d+)?$')

def clean_numeric_series(s: pd.Series) -> pd.Series:
    """
    Detect American vs European formatting in a text series and return floats.
    """
    s_str = s.astype(str).str.strip()
    sample = s_str.dropna().head(50)

    # American: commas for thousands, dot for decimal
    if sample.map(lambda x: bool(_re_amer.match(x))).all():
        cleaned = s_str.str.replace(",", "", regex=False)

    # European: dots for thousands, comma for decimal
    elif sample.map(lambda x: bool(_re_euro.match(x))).all():
        cleaned = (
            s_str
            .str.replace(r"[\. ]", "", regex=True)
            .str.replace(",", ".", regex=False)
        )
    else:
        # fallback: let float() parse or error
        cleaned = s_str

    return cleaned.astype(float)

# ── hard-coded GA models (feature order matters!) ───────────────────────
MODEL_SPECS: dict[str, dict] = {
    "cellular": {
        "label"   : "Cellular Proteome",
        "dir"     : "Cellular_Proteome",
        "features": [
            "OSTP", "FHL2", "CFAD", "PCBP2",
            "SPRL1", "PROZ", "VAPB", "AN32B",
        ],
    },
    "core": {
        "label"   : "Core Matrisome",
        "dir"     : "Core_Matrisome",
        "features": [
            "AHSG", "APOC1", "APOC2", "CD109", "COL2A1", "COL18A1", "CFHR1",
            "FTL", "SERPINE2", "IGHG1", "IGFBP3", "TIMP3", "PRDX2", "SERPINF1",
        ],
    },
    "soluble": {
        "label"   : "Soluble Matrisome",
        "dir"     : "Soluble_Matrisome",
        "features": [
            "APOC2", "BCAM", "SULF1", "KNG1",
            "LTBP2", "SERPINA5", "NOV",
        ],
    },
}


# ── cached artefact loader ──────────────────────────────────────────────
@lru_cache(maxsize=None)
def _load(model_key: str = "cellular"):
    """
    Load model + scaler for the given key and return them together with the
    (hard-coded) feature list in canonical upper-case order.
    """
    spec = MODEL_SPECS[model_key]
    sub  = settings.MODEL_ARTIFACT_DIR / spec["dir"]

    model   = joblib.load(sub / "0finalSingleModel.pkl")
    scaler  = joblib.load(sub / "minmax_scaler.pkl")
    feats   = [_clean(f) for f in spec["features"]]

    return model, scaler, feats


# ── read upload (matrix OR two-column) ───────────────────────────────────
def _read_file(f) -> tuple[pd.DataFrame, str]:
    name       = f.name.lower()
    is_excel   = name.endswith((".xlsx", ".xls"))

    if is_excel:
        df = pd.read_excel(f, header=0, index_col=0)
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = clean_numeric_series(df[col])

        # ensure all columns numeric
        if not all(np.issubdtype(dt, np.number) for dt in df.dtypes):
            bad = [c for c, dt in df.dtypes.items() if not np.issubdtype(dt, np.number)]
            raise ValueError(f"Columns {bad!r} could not be converted to numbers.")
    else:
        raw = f.read().decode("utf-8", errors="replace")
        raw = "\n".join(line.strip("\t,") for line in raw.splitlines())
        first_line = raw.lstrip().splitlines()[0]

        # ── pick explicit sep by extension ───────────────────────────
        if name.endswith((".tsv", ".txt")):
            sep = "\t"
        elif name.endswith(".csv"):
            sep = ","
        else:
            # fallback: count tabs vs commas
            sep = "\t" if first_line.count("\t") > first_line.count(",") else ","

        # reject any line that has two separators in a row
        for i, line in enumerate(raw.splitlines(), start=1):
            if sep * 2 in line:
                raise ValueError(
                    f"Invalid input at line {i}: "
                    f"found two consecutive separators {sep!r}{sep!r}"
                )

        df = pd.read_csv(
            io.StringIO(raw),
            sep=sep,
            header=0,
            index_col=0,
            engine="python",
        )

    # Replace any blank or whitespace-only cell with NaN
    df = df.replace(r'^\s*$', np.nan, regex=True)

    # helper
    def _looks_numeric(x):
        try:
            float(str(x))
            return True
        except ValueError:
            return False

    # 2) header-less **two-column** fallback ------------------------------
    if (
        df.shape[1] == 1
        and (
            _looks_numeric(df.columns[0])
            or str(df.columns[0]).strip() == ""
            or str(df.columns[0]).startswith("Unnamed")
        )
    ):
        # reload without header
        if is_excel:
            f.seek(0)
            df = pd.read_excel(f, header=None)          # index_col later
        else:
            df = pd.read_csv(io.StringIO(raw), header=None,
                             sep=None, engine="python")
        df.columns = ["Protein", "Abundance"]
        df["Protein"] = df["Protein"].apply(_clean)
        return df, "long"

    # 3) header-less **matrix** fallback (all column labels ints) ---------
    if all(isinstance(c, (int, np.integer)) for c in df.columns):
        if is_excel:
            f.seek(0)
            df = pd.read_excel(f, header=None, index_col=0)
        else:
            df = pd.read_csv(io.StringIO(raw), header=None, index_col=0,
                             sep=sep, engine="python")
        # give numeric IDs 1,2,3,…
        df.columns = [str(i + 1) for i in range(df.shape[1])]

    # 4) if header row existed but is blank ('' or Unnamed) ---------------
    if df.columns.str.match(r"^\s*$|^Unnamed").all():
        df.columns = [str(i + 1) for i in range(df.shape[1])]

    # 5) normalise protein names & decide layout --------------------------
    df.index = df.index.map(_clean)
    # discard columns that are completely empty
    df = df.dropna(axis=1, how='all')
    # rename anonymous columns that still contain data
    rename_map = {}
    for idx, col in enumerate(df.columns, start=1):
        col_str = str(col).strip()
        if col_str == "" or col_str.startswith("Unnamed"):
            rename_map[col] = f"Subject_{idx}"
    if rename_map:
        df = df.rename(columns=rename_map)

    # decide layout and return
    layout   = "wide" if df.index.nunique() > 1 else "long"
    return df, layout

# ── build feature matrix ─────────────────────────────────────────────────
def _vectors(df: pd.DataFrame, feats: list[str], layout: str):
    if layout == "long":                # two-column upload
        s = df.set_index("Protein")["Abundance"]

        # compute how many required features are absent or zero
        missing = []
        for p in feats:
            if p not in s.index:
                missing.append(p)
            else:
                val = s[p]
                if pd.isna(val) or (val == 0):
                    missing.append(p)

        missing_frac = len(missing) / len(feats)
        if missing_frac > 0.50:
            raise ValueError("More than 50% of required proteins are missing")
        elif missing_frac > 0.25:
            warnings.warn("")

        row = s.reindex(feats).to_frame().T
        row.index = ["Subject_1"]                       # Subject ID
        row = row.replace(0, np.nan)
        return row.index.tolist(), row                  # ← DataFrame

    else:
        # wide matrix upload
        missing = []
        for p in feats:
            if p not in df.index:
                missing.append(p)
            else:
                row_vals = df.loc[p]
                if row_vals.isna().all() or (row_vals.fillna(0) == 0).all():
                    missing.append(p)

        missing_frac = len(missing) / len(feats)
        if missing_frac > 0.50:
            raise ValueError("More than 50% of required proteins are missing")
        elif missing_frac > 0.25:
            warnings.warn("")

        mat = df.reindex(feats).astype(float).T   # rows = subjects
        mat = mat.replace(0, np.nan)
        return mat.index.tolist(), mat            # DataFrame (n × n_feats)


# ── Neo4j helper (from plaquery_views.py) ───────────────────────────────
def get_neo4j_db():
    uri      = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    return GraphDatabase.driver(uri, auth=basic_auth(username, password))

# ── 1) GET: render both forms ─────────────────────────────────────────────────────────────────
@require_http_methods(["GET"])
def calc_prediction_view(request: HttpRequest) -> HttpResponse:
    # model dropdown
    models = MODEL_SPECS
    # pull filter lists from Neo4j
    driver = get_neo4j_db()
    with driver.session(database="plaquems") as session:
        histologies = [
            r["histology"] for r in session.run(
                "MATCH (p:Patient) RETURN DISTINCT p.Histology AS histology"
            ) if r["histology"] is not None
        ]
        ultrasounds = [
            r["ultrasound"] for r in session.run(
                "MATCH (p:Patient) RETURN DISTINCT p.Ultrasound AS ultrasound"
            ) if r["ultrasound"] is not None
        ]
        sexes = [
            r["sex"] for r in session.run(
                "MATCH (p:Patient) RETURN DISTINCT p.Sex AS sex"
            ) if r["sex"] is not None
        ]
        symptoms = [
            r["symptoms"] for r in session.run(
                "MATCH (p:Patient) RETURN DISTINCT p.Symptoms AS symptoms"
            ) if r["symptoms"] is not None
        ]
        ages_raw = [
            r["age"] for r in session.run(
                "MATCH (p:Patient) RETURN DISTINCT p.Age AS age"
            ) if r["age"] is not None
        ]
        calcs = [
            r["calcification"] for r in session.run(
                "MATCH (p:Patient) RETURN DISTINCT p.`Calcified by description` AS calcification"
            ) if r["calcification"] is not None
        ]
    driver.close()

    # derive age groups
    age_groups = []
    for a in ages_raw:
        try:
            v = float(a)
            age_groups.append(
                "under40"  if v < 40 else
                "40to60"   if v <= 60 else
                "over60"
            )
        except:
            continue
    age_groups = [g for g in ("under40", "40to60", "over60") if g in age_groups]

    smoker_status = ["Active smoker", "Past smoker", "Never smoker"]
    bmi_ranges = [
        {"label": "Underweight(<18.5)", "value": "underweight"},
        {"label": "Normal(18.5–24.9)",  "value": "normal"},
        {"label": "Overweight(25–29.9)", "value": "overweight"},
        {"label": "Obese(30+)",          "value": "obese"},
    ]
    pack_years_ranges = [
        {"label": "Light smoker(1–20)", "value": "light"},
        {"label": "Moderate smoker(20.1–40)", "value": "moderate"},
        {"label": "Heavy smoker(>40)", "value": "heavy"},
    ]

    return render(request, "calc_pred.html", {
        "models":            models,
        "histologies":       histologies,
        "ultrasounds":       ultrasounds,
        "sexes":             sexes,
        "symptoms":          symptoms,
        "age_groups":        age_groups,
        "calcifications":    calcs,
        "smoker_status":     smoker_status,
        "bmi_ranges":        bmi_ranges,
        "pack_years_ranges": pack_years_ranges,
    })

    # ─── POST: file-upload + prediction (warn, then impute everything) ───
@csrf_exempt
@require_http_methods(["POST"])
def calc_prediction_upload_view(request: HttpRequest) -> JsonResponse:
    file_obj = request.FILES.get("sample_file")
    if not file_obj:
        return HttpResponseBadRequest("Expected file field ‘sample_file’")

    log2 = bool(request.POST.get("log2"))
    model_key = request.POST.get("model_key", "cellular")  # default

    try:
        model, scaler, feats = _load(model_key)

        # load KNN imputer (same dir as model & scaler)
        imputer_path = settings.MODEL_ARTIFACT_DIR / MODEL_SPECS[model_key]["dir"] / "knn_imputer.pkl"
        imputer = joblib.load(imputer_path)

        df, layout      = _read_file(file_obj)
        subjects, Xdf   = _vectors(df, feats, layout)      # DataFrame

        if log2:
            if (Xdf <= 0).any().any():
                raise ValueError("Log₂ transform needs all abundances > 0")
            Xdf = np.log2(Xdf)
        
        filtered_subjects = []
        warnings_list = []

        for sid in Xdf.index:
            # Identify missing_names as those features that are NaN or zero
            missing_names = [
                f for f in feats
                if (pd.isna(Xdf.at[sid, f])) or (Xdf.at[sid, f] == 0)
            ]
            missing_frac = len(missing_names) / len(feats)

            # Skip if >50% missing
            if missing_frac > 0.50:
                warnings_list.append({
                    "subject_id":       str(sid),
                    "missing_fraction": float(missing_frac),
                    "skipped":          True
                })
                continue

            # Warn if >25% and ≤50% missing
            if missing_frac > 0.25:
                warnings_list.append({
                    "subject_id": str(sid),
                    "missing_fraction": float(missing_frac),
                })

            # Otherwise (≤25%) → proceed silently
            filtered_subjects.append(sid)

        # Subset Xdf to only include subjects that passed the >50% check
        Xdf = Xdf.loc[filtered_subjects]

        # impute ALL missing → scale → predict
        X_imp_arr = imputer.transform(Xdf)

        # Re-wrap into a DataFrame
        X_imp = pd.DataFrame(
            X_imp_arr,
            index=Xdf.index,
            columns=Xdf.columns
        )

        X_scaled = scaler.transform(X_imp)

        preds = model.predict(X_scaled).astype(int)
        # if the model supports predict_proba, use it…
        if hasattr(model, "predict_proba"):
            probas = model.predict_proba(X_scaled)

        # …otherwise (e.g. linear SVM) use decision_function + sigmoid
        else:
            # decision_function gives signed distance to the hyperplane
            dec = model.decision_function(X_scaled)

            # convert to “probability” of the positive class
            prob_pos = expit(dec)

            # build a (n_samples × 2) array like predict_proba would
            probas = np.vstack([1 - prob_pos, prob_pos]).T

        results = [
            {
                "subject_id": str(sid),
                "class_name": "calcified" if p else "non-calcified",
                "probability_calcified": float(pr[1]),
                "probability_noncalc": float(pr[0]),
            }
            for sid, p, pr in zip(Xdf.index, preds, probas)
        ]

        return JsonResponse({
            "results":      results,
            "warnings": warnings_list,
            "log2_applied": log2,
        })

    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

# ── 3) POST: Neo4j filters + batch prediction ────────────────────────────
@csrf_exempt
@require_http_methods(["POST"])
def calc_prediction_filter_view(request: HttpRequest) -> JsonResponse:
    model_key = request.POST.get("model_key", "cellular")

    # Gather raw filter inputs
    sex                 = request.POST.getlist("sex")
    age                 = request.POST.getlist("age_group")
    symptoms            = request.POST.getlist("symptoms")
    histology           = request.POST.getlist("histology")
    ultrasound          = request.POST.getlist("ultrasound")
    calcified           = request.POST.getlist("calcification")
    clinical_conditions = request.POST.getlist("clinical_condition")
    clinical_outcomes   = request.POST.getlist("clinical_outcomes")
    medications         = request.POST.getlist("medications")
    smoker_status       = request.POST.getlist("smoker_status")
    bmi_range           = request.POST.getlist("bmi_range")
    pack_years_range    = request.POST.getlist("pack_years_range")
    cv_biomarkers       = request.POST.getlist("cvbiomarker")

    # Build additional_columns for metadata
    additional_columns = []
    if not (sex or age or symptoms or histology or ultrasound or calcified
            or clinical_conditions or clinical_outcomes or medications
            or smoker_status or bmi_range or pack_years_range or cv_biomarkers):
        additional_columns.extend([
            "pt.Sex AS Sex",
            "pt.Age AS Age",
            "pt.Symptoms AS Symptoms",
            "pt.Histology AS Histology",
            "pt.Ultrasound AS Ultrasound",
            "pt.`Calcified by description` AS `Calcification (clinical)`",
            # clinical conditions
            "pt.`Acute infection` AS `Acute infection`",
            "pt.`Acute myocardial infarction` AS `Acute myocardial infarction`",
            "pt.`Adipositas(BMI>30)` AS `Adipositas(BMI>30)`",
            "pt.`Auto-immune disease` AS `Auto-immune disease`",
            "pt.`Cancer` AS `Cancer`",
            "pt.`Chronic infection` AS `Chronic infection`",
            "pt.`Chronic obstructive pulmonary disease` AS `COPD`",
            "pt.`Coronary artery disease` AS `Coronary artery disease`",
            "pt.`Diabetes mellitus type 2` AS `Diabetes mellitus type 2`",
            "pt.`High Stenosis(≥90%)` AS `High stenosis(≥90%)`",
            "pt.`Hyperlipidemia` AS `Hyperlipidemia`",
            "pt.`Hypertension` AS `Hypertension`",
            "pt.`Peripheral artery disease` AS `Peripheral artery disease`",
            "pt.`Stroke history` AS `Stroke history`",
            # clinical outcomes
            "pt.`Stroke` AS `Stroke`",
            "pt.`Transient ischemic attack` AS `Transient ischemic attack`",
            "pt.`Cardiovascular mortality` AS `Cardiovascular mortality`",
            "pt.`Primary endpoint` AS `Primary endpoint`",
            # medications
            "pt.`ACE inhibitors` AS `ACE inhibitors`",
            "pt.`ARB therapy` AS `ARB therapy`",
            "pt.`Antiplatelet` AS `Antiplatelet`",
            "pt.`Aspirin` AS `Aspirin`",
            "pt.`Beta blockers` AS `Beta blockers`",
            "pt.`Statins` AS `Statins`",
            "pt.`Clopidogrel` AS `Clopidogrel`",
            "pt.`Diuretics` AS `Diuretics`",
            # lifestyle & pack-years
            "pt.`Active smoker` AS `Active smoker`",
            "pt.`Past smoker` AS `Past smoker`",
            "pt.`Never smoker` AS `Never smoker`",
            "pt.BMI AS BMI",
            "CASE WHEN pt.`Never smoker` = 'yes' THEN 0 ELSE pt.`Pack-years` END AS `Pack-years`",
            # cardiovascular biomarkers
            "toFloat(pt.`Cholesterol(total)`) AS `Total cholesterol (mg/dL)`",
            "toFloat(pt.`HDL`) AS `HDL (mg/dL)`",
            "toFloat(pt.`LDL`) AS `LDL (mg/dL)`",
            "toFloat(pt.`Triglycerides`) AS `Triglycerides (mg/dL)`",
            "toFloat(pt.`High-sensitivity CRP`) AS `High-sensitivity CRP (mg/dL)`",
            "toFloat(pt.`Ultrasensitive CRP`) AS `Ultrasensitive CRP (mg/dL)`",
            "toFloat(pt.`Pre-surgery BP(diastolic)`) AS `Pre-surgery BP(diastolic)`",
            "toFloat(pt.`Pre-surgery BP(systolic)`) AS `Pre-surgery BP(systolic)`",
            "pt.`Contralateral stenosis(≥60%)` AS `Contralateral stenosis(≥60%)`",
            "toFloat(pt.`Stenosis grade(%)`) AS `Stenosis grade(%)`",
        ])
    else:
        if sex and sex[0] != 'Filter by Sex':
            additional_columns.append("pt.Sex AS Sex")
        if age and age[0] != 'Filter by Age':
            additional_columns.append("pt.Age AS Age")
        if symptoms and symptoms[0] != 'Filter by Symptoms':
            additional_columns.append("pt.Symptoms AS Symptoms")
        if histology and histology[0] != 'Select Plaque Histology':
            additional_columns.append("pt.Histology AS Histology")
        if ultrasound and ultrasound[0] != 'Select Plaque Ultrasound':
            additional_columns.append("pt.Ultrasound AS Ultrasound")
        if calcified and calcified[0] != 'Filter by Calcification':
            additional_columns.append("pt.`Calcified by description` AS `Calcification (clinical)`")
        for c in clinical_conditions:
            alias = c.replace(" ", "_")
            additional_columns.append(f"pt.`{c}` AS `{alias}`")
        for o in clinical_outcomes:
            alias = o.replace(" ", "_")
            additional_columns.append(f"pt.`{o}` AS `{alias}`")
        for m in medications:
            alias = m.replace(" ", "_")
            additional_columns.append(f"pt.`{m}` AS `{alias}`")
        if smoker_status:
            if "Active smoker" in smoker_status:
                additional_columns.append("pt.`Active smoker` AS `Active smoker`")
            if "Past smoker" in smoker_status:
                additional_columns.append("pt.`Past smoker` AS `Past smoker`")
            if "Never smoker" in smoker_status:
                additional_columns.append("pt.`Never smoker` AS `Never smoker`")
        if bmi_range:
            additional_columns.append("pt.BMI AS BMI")
        if pack_years_range:
            additional_columns.append("CASE WHEN pt.`Never smoker` = 'yes' THEN 0 ELSE pt.`Pack-years` END AS `Pack-years`")
        for marker in cv_biomarkers:
            if marker == "Contralateral stenosis(≥60%)":
                additional_columns.append(f"pt.`{marker}` AS `{marker}`")
            else:
                additional_columns.append(f"toFloat(pt.`{marker}`) AS `{marker}`")

    seen = set()
    unique_cols = []
    for col in additional_columns:
        alias = col.split(" AS ")[-1].strip("`")
        if alias not in seen:
            seen.add(alias)
            unique_cols.append(col)
    return_cols = ",\n      ".join(unique_cols)

    meta_q = f"""
    MATCH (pt:Patient {{id:$pid}})
    RETURN
      pt.id AS patient_id,
      {return_cols}
    """

    # Build Cypher WHERE clauses from filters
    clauses, params = [], {}
    if sex:
        clauses.append("pt.Sex IN $sex")
        params["sex"] = sex
    if age:
        age_sub = []
        for g in age:
            if g == "under40":
                age_sub.append("pt.Age < 40")
            elif g == "40to60":
                age_sub.append("(pt.Age >= 40 AND pt.Age <= 60)")
            elif g == "over60":
                age_sub.append("pt.Age > 60")
        clauses.append("(" + " OR ".join(age_sub) + ")")
    if symptoms:
        clauses.append("pt.Symptoms IN $symptoms")
        params["symptoms"] = symptoms
    if histology:
        clauses.append("pt.Histology IN $histology")
        params["histology"] = histology
    if ultrasound:
        clauses.append("pt.Ultrasound IN $ultrasound")
        params["ultrasound"] = ultrasound
    if calcified:
        clauses.append("pt.`Calcified by description` IN $calcification")
        params["calcification"] = calcified
    if bmi_range:
        bmi_sub = []
        if "underweight" in bmi_range:
            bmi_sub.append("pt.BMI < 18.5")
        if "normal" in bmi_range:
            bmi_sub.append("(pt.BMI >= 18.5 AND pt.BMI < 25)")
        if "overweight" in bmi_range:
            bmi_sub.append("(pt.BMI >= 25 AND pt.BMI < 30)")
        if "obese" in bmi_range:
            bmi_sub.append("pt.BMI >= 30")
        clauses.append("(" + " OR ".join(bmi_sub) + ")")
        params["bmi_range"] = bmi_range
    if smoker_status:
        smoker_sub = []
        if "Active smoker" in smoker_status:
            smoker_sub.append("pt.`Active smoker` = 'yes'")
        if "Past smoker" in smoker_status:
            smoker_sub.append("pt.`Past smoker` = 'yes'")
        if "Never smoker" in smoker_status:
            smoker_sub.append("pt.`Never smoker` = 'yes'")
        clauses.append("(" + " OR ".join(smoker_sub) + ")")
        params["smoker_status"] = smoker_status
    if pack_years_range:
        pack_sub = []
        if "light" in pack_years_range:
            pack_sub.append("(pt.`Pack-years` >= 1 AND pt.`Pack-years` <= 20)")
        if "moderate" in pack_years_range:
            pack_sub.append("(pt.`Pack-years` > 20 AND pt.`Pack-years` <= 40)")
        if "heavy" in pack_years_range:
            pack_sub.append("pt.`Pack-years` > 40")
        clauses.append("(" + " OR ".join(pack_sub) + ")")
        params["pack_years_range"] = pack_years_range
    if clinical_conditions:
        sub = [f"pt.`{c}` = 'yes'" for c in clinical_conditions]
        clauses.append("(" + " AND ".join(sub) + ")")
        params["clinical_condition"] = clinical_conditions
    if medications:
        sub = [f"pt.`{m}` = 'yes'" for m in medications]
        clauses.append("(" + " AND ".join(sub) + ")")
        params["medications"] = medications
    if cv_biomarkers:
        # special case
        if "Contralateral stenosis(≥60%)" in cv_biomarkers:
            clauses.append("pt.`Contralateral stenosis(≥60%)` = 'yes'")
        for bm in cv_biomarkers:
            if bm != "Contralateral stenosis(≥60%)":
                clauses.append(f"toFloat(pt.`{bm}`) IS NOT NULL")
        params["cvbiomarker"] = cv_biomarkers
    if clinical_outcomes:
        sub = []
        for o in clinical_outcomes:
            if o.lower() == "primary endpoint":
                sub.append("pt.`Primary endpoint` = 'event'")
            else:
                sub.append(f"pt.`{o}` = 'yes'")
        clauses.append("(" + " AND ".join(sub) + ")")
        params["clinical_outcomes"] = clinical_outcomes

    where = "WHERE " + " AND ".join(clauses) if clauses else ""

    # Load model artifacts
    model, scaler, feats = _load(model_key)
    imputer = joblib.load(
        settings.MODEL_ARTIFACT_DIR / MODEL_SPECS[model_key]["dir"] / "knn_imputer.pkl"
    )
    exp_map = {
        "cellular": "Cellular Proteome Carotid Plaques (Vienna)",
        "core":     "Core Matrisome Carotid Plaques (Vienna)",
        "soluble":  "Soluble Matrisome Carotid Plaques (Vienna)",
    }
    exp_name = exp_map[model_key]

    # Fetch filtered patient IDs
    driver = get_neo4j_db()
    with driver.session(database="plaquems") as session:
        pat_q = f"MATCH (pt:Patient) {where} RETURN pt.id AS id"
        patient_ids = [rec["id"] for rec in session.run(pat_q, **params)]

    if not patient_ids:
        driver.close()
        return JsonResponse({"results": [], "warnings": []})

    # Batch‐get core abundances for all patients
    core_batch_q = """
    UNWIND $patientIds AS pid
    MATCH (s:Sample {patientID:pid, area:'core', experiment:$exp})
    MATCH (s)-[r:ABUNDANCE]->(pr:Protein)
    UNWIND [ nm IN pr.name WHERE toUpper(trim(nm)) IN $feats ] AS name
    RETURN pid, collect(DISTINCT {name:name, abundance:r.abundance}) AS coreAbunds
    """
    with driver.session(database="plaquems") as session:
        core_records = list(session.run(
            core_batch_q,
            patientIds=patient_ids,
            exp=exp_name,
            feats=feats
        ))
    # Build a map: pid → { feat:abundance, … }
    core_map = {}
    for rec in core_records:
        cm = { entry["name"]: entry["abundance"] for entry in rec["coreAbunds"] }
        core_map[rec["pid"]] = cm

    # Batch‐get periphery abundances
    peri_batch_q = """
    UNWIND $patientIds AS pid
    MATCH (s:Sample {patientID:pid, area:'periphery', experiment:$exp})
    MATCH (s)-[r:ABUNDANCE]->(pr:Protein)
    UNWIND [ nm IN pr.name WHERE toUpper(trim(nm)) IN $feats ] AS name
    RETURN pid, collect(DISTINCT {name:name, abundance:r.abundance}) AS periAbunds
    """
    with driver.session(database="plaquems") as session:
        peri_records = list(session.run(
            peri_batch_q,
            patientIds=patient_ids,
            exp=exp_name,
            feats=feats
        ))
    peri_map = {}
    for rec in peri_records:
        pm = { entry["name"]: entry["abundance"] for entry in rec["periAbunds"] }
        peri_map[rec["pid"]] = pm

    # Loop locally: enforce thresholds, fetch metadata, impute & predict
    results, warnings_list = [], []
    with driver.session(database="plaquems") as session:
        for pid in patient_ids:
            # Metadata
            meta_rec = session.run(meta_q, pid=pid).single().data()
            meta_rec["experiment"] = exp_name 

            # Merge core + periphery for missing names
            abund = dict(core_map.get(pid, {}))
            pm    = peri_map.get(pid, {})
            # First, find which features are missing in core (absent, None, or zero)
            missing_names = [
                f for f in feats
                if (f not in abund) or (abund.get(f) is None) or (abund.get(f) == 0)
            ]
            # Immediately fill those from periphery (if available and non-zero)
            for f in list(missing_names):
                if (f in pm) and (pm[f] is not None) and (pm[f] != 0):
                    abund[f] = pm[f]
            # Now re-compute what's still missing (after having tried periphery)
            missing_names = [
                f for f in feats
                if (f not in abund) or (abund.get(f) is None) or (abund.get(f) == 0)
            ]

            # Compute missing_fraction, then skip or warn as needed
            total_feats  = len(feats)
            missing_frac = len(missing_names) / total_feats

            # SKIP if more than 50% features are missing
            if missing_frac > 0.50:
                warnings_list.append({
                    "patient_id":      pid,
                    "missing_fraction": float(missing_frac)
                })
                continue

            # WARN (but do not skip) if more than 25% and up to 50% missing
            if missing_frac > 0.25:
                warnings_list.append({
                    "patient_id":      pid,
                    "missing_fraction": float(missing_frac)
                })

            # Build DataFrame & check missing‐value fraction
            row = pd.DataFrame(
                [[
                    abund[f] if (f in abund and abund.get(f) not in (None, 0)) else np.nan
                    for f in feats
                ]],
                index=[pid],
                columns=feats,
                dtype=float
            )

            # Impute, scale, predict
            X_imp_arr = imputer.transform(row)
            X_imp     = pd.DataFrame(X_imp_arr, index=row.index, columns=feats)
            X_scaled  = scaler.transform(X_imp)

            if hasattr(model, "predict_proba"):
                probas = model.predict_proba(X_scaled)
            else:
                dec      = model.decision_function(X_scaled)
                prob_pos = expit(dec)
                probas   = np.vstack([1 - prob_pos, prob_pos]).T

            pred = model.predict(X_scaled).astype(int)[0]

            results.append({
                **meta_rec,
                "class_name":            "calcified" if pred else "non-calcified",
                "probability_calcified": float(probas[0][1]),
                "probability_noncalc":   float(probas[0][0]),
                "missing_fraction":      float(missing_frac)
            })

    driver.close()
    return JsonResponse({
        "results": results,
        "warnings": warnings_list
    })
