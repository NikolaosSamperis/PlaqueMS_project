from __future__ import annotations
import warnings
import io, os, math, joblib, re, numpy as np, pandas as pd
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

@lru_cache(maxsize=None)
def _load_pipeline():
    """
    Return the scikit-learn Pipeline that already bundles:
    scaler  ➜  KNNImputer  ➜  ElasticNet (regressor)
    """
    pkl_path = (
        settings.MODEL_ARTIFACT_DIR
        / "GUHCL_syntax_score"
        / "syntax_pipeline.pkl"
    )
    return joblib.load(pkl_path)


# ── read upload (matrix OR two-column) ───────────────────────────────────
def _read_file(f) -> tuple[pd.DataFrame, str]:
    try:
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
        
    except Exception as e:
        # If this is an explicit ValueError raised above, re-raise it untouched
        if isinstance(e, ValueError):
            raise

        # Otherwise, raise a unified “unsupported format” message
        raise ValueError(
            "Unsupported file format or structure. Please upload a CSV/TSV/XLS(X) with either:\n"
            "  • A two-column table (Protein, Abundance) OR\n"
            "  • A Proteins×Subjects matrix (protein names in column 1, numeric abundances in the body)."
        )

# ── constants ───────────────────────────────────────────────────────────
PANEL = ["HRG", "CP", "C4B", "F13A1", "VCAN"]

# ── build feature matrix for the Syntax pipeline ────────────────────────
def _matrix_for_pipeline(df: pd.DataFrame, layout: str):
    """
    Return a DataFrame whose **index are the 5 proteins** (PANEL) and whose
    **columns are patients / subjects**.

    The pipeline’s first transformer will transpose this to the usual
    (patients × proteins) shape.
    """
    feats = [p.upper() for p in PANEL]

    # ── SINGLE-PATIENT, “long” layout ────────────────────────────────────
    if layout == "long":
        # df = Protein, Abundance
        col = df.set_index("Protein")["Abundance"]
        col = col.reindex(feats)                       # proteins on index
        col.name = "Subject_1"                         # ← single column
        mat = col.to_frame()                           # shape (5 × 1)

    # ── MULTI-PATIENT, “wide” layout ────────────────────────────────────
    else:
        # df already has proteins on the index, patients as columns
        mat = df.reindex(feats).astype(float)

    # evaluate missingness before zero→NaN, so zeros count as missing
    missing = [
        p for p in feats
        if p not in mat.index
        or mat.loc[p].isna().all()
        or (mat.loc[p].fillna(0) == 0).all()
    ]
    frac = len(missing) / len(feats)
    if frac > 0.50:
        raise ValueError(
            "More than 50 % of the required proteins are missing. "
            "Prediction cannot be performed."
        )
    elif frac > 0.25:
        warnings.warn(
            "More than 25 % of the required proteins are missing. "
            "Prediction may be unreliable.",
            UserWarning,
            stacklevel=2,
        )

    # zeros → NaN so the KNNImputer can step in
    mat = mat.replace(0, np.nan)

    # Return (patient_ids, matrix)
    return mat.columns.tolist(), mat


# ── Neo4j helper (from plaquery_views.py) ───────────────────────────────
def get_neo4j_db():
    uri      = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    return GraphDatabase.driver(uri, auth=basic_auth(username, password))

# ── 1) GET: render both forms ─────────────────────────────────────────────────────────────────
@require_http_methods(["GET"])
def syntax_prediction_view(request: HttpRequest) -> HttpResponse:
    # pull filter lists from Neo4j
    driver = get_neo4j_db()
    with driver.session(database="plaquems") as session:
        experiments = [
            r["experiment"] for r in session.run(
                "MATCH (s:Sample) RETURN DISTINCT s.experiment AS experiment"
            ) if r["experiment"] is not None
        ]
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

    return render(request, "syntax_pred.html", {
        "experiments":       experiments,
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
def syntax_prediction_upload_view(request: HttpRequest) -> JsonResponse:
    """Handle CSV / XLSX upload, apply optional log₂ transform, and return
    Syntax-score predictions together with per-subject missing-data warnings."""
    file_obj = request.FILES.get("sample_file")
    if not file_obj:
        return HttpResponseBadRequest("Expected file field ‘sample_file’")

    log2 = bool(request.POST.get("log2"))

    try:
        # ── 1) load artefacts -------------------------------------------------
        pipe = _load_pipeline()                       # cached sklearn Pipeline

        # ── 2) parse the upload ---------------------------------------------
        df, layout          = _read_file(file_obj)
        subjects, prot_mat  = _matrix_for_pipeline(df, layout)  # 5×N matrix
        # prot_mat.index   → proteins
        # prot_mat.columns → patient IDs

        # ── 3) optional log₂ transform --------------------------------------
        if log2:
            if (prot_mat <= 0).any().any():
                raise ValueError("Log₂ transform needs all abundances > 0")
            prot_mat = np.log2(prot_mat)

        # ── 4) per-subject missing-protein checks ---------------------------
        filtered_subjects: list[str] = []
        warnings_list:      list[dict] = []

        for sid in subjects:
            col = prot_mat[sid]
            missing_names = [p for p in PANEL if pd.isna(col[p])]
            missing_frac  = len(missing_names) / len(PANEL)

            # Skip if > 50 % missing
            if missing_frac > 0.50:
                warnings_list.append({
                    "subject_id":       str(sid),
                    "missing_fraction": float(missing_frac),
                    "skipped":          True,
                })
                continue

            # Warn if 25–50 % missing
            if missing_frac > 0.25:
                warnings_list.append({
                    "subject_id":       str(sid),
                    "missing_fraction": float(missing_frac),
                })

            filtered_subjects.append(sid)

        # keep only columns that passed the >50 % check
        prot_mat = prot_mat[filtered_subjects]

        # ── 5) run the pipeline ---------------------------------------------
        # (Pipeline: transpose → select PANEL → scale → KNN-impute → regress)
        preds = pipe.predict(prot_mat).astype(float)   # ndarray (n_patients,)

        # ── 6) pack the JSON response ---------------------------------------
        results = [
            {"subject_id": sid, "syntax_score": float(sc)}
            for sid, sc in zip(filtered_subjects, preds)
        ]

        return JsonResponse({
            "results":       results,
            "warnings":      warnings_list,
            "log2_applied":  log2,
        })

    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

# ── 3) POST: Neo4j filters + batch prediction ────────────────────────────
@csrf_exempt
@require_http_methods(["POST"])
def syntax_prediction_filter_view(request: HttpRequest) -> JsonResponse:

    # Gather raw filter inputs
    experiments          = request.POST.getlist("experiment")
    if not experiments:
        experiments = [
            "Cellular Proteome Carotid Plaques (Vienna)",
            "Core Matrisome Carotid Plaques (Vienna)",
            "Soluble Matrisome Carotid Plaques (Vienna)",
            "Soluble Matrisome OLINK Carotid Plaques (Vienna)",
        ]     
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
            "toFloat(pt.`Cholesterol(total)`) AS `Total cholesterol(mg/dL)`",
            "toFloat(pt.`HDL`) AS `HDL(mg/dL)`",
            "toFloat(pt.`LDL`) AS `LDL(mg/dL)`",
            "toFloat(pt.`Triglycerides`) AS `Triglycerides(mg/dL)`",
            "toFloat(pt.`High-sensitivity CRP`) AS `High-sensitivity CRP(mg/dL)`",
            "toFloat(pt.`Ultrasensitive CRP`) AS `Ultrasensitive CRP(mg/dL)`",
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

    # load the single pipeline & constants
    pipe  = _load_pipeline()  # cached scikit-learn Pipeline
    feats = PANEL             # ["HRG", "CP", "C4B", "F13A1", "VCAN"]

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
    MATCH (s:Sample {patientID:pid, area:'core'})
    WHERE s.experiment IN $exps
    MATCH (s)-[r:ABUNDANCE]->(pr:Protein)
    UNWIND [ nm IN pr.name WHERE toUpper(trim(nm)) IN $feats ] AS name
    RETURN pid, collect(DISTINCT {name:name, abundance:r.abundance}) AS coreAbunds
    """
    with driver.session(database="plaquems") as session:
        core_records = list(session.run(
            core_batch_q,
            patientIds=patient_ids,
            exps=experiments,
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
    MATCH (s:Sample {patientID:pid, area:'periphery'})
    WHERE s.experiment IN $exps
    MATCH (s)-[r:ABUNDANCE]->(pr:Protein)
    UNWIND [ nm IN pr.name WHERE toUpper(trim(nm)) IN $feats ] AS name
    RETURN pid, collect(DISTINCT {name:name, abundance:r.abundance}) AS periAbunds
    """
    with driver.session(database="plaquems") as session:
        peri_records = list(session.run(
            peri_batch_q,
            patientIds=patient_ids,
            exps=experiments,
            feats=feats
        ))
    peri_map = {}
    for rec in peri_records:
        pm = { entry["name"]: entry["abundance"] for entry in rec["periAbunds"] }
        peri_map[rec["pid"]] = pm

    # loop locally, build 5×1 matrices, run pipeline
    results, warnings_list = [], []
    with driver.session(database="plaquems") as session:
        for pid in patient_ids:
            # Metadata
            meta_rec = session.run(meta_q, pid=pid).single().data()
            meta_rec["experiment"] = "; ".join(experiments) 

            # merge core + periphery
            abund = dict(core_map.get(pid, {}))
            for f, v in peri_map.get(pid, {}).items():
                if f not in abund or abund[f] in (None, 0):
                    abund[f] = v

            # missing-data check
            missing_names = [
                f for f in feats
                if f not in abund or abund[f] in (None, 0)
            ]
            missing_frac = len(missing_names) / len(feats)

            # skip & warn if > 50 % missing
            if missing_frac > 0.50:
                warnings_list.append({
                    "patient_id":       pid,
                    "missing_fraction": float(missing_frac),
                    "skipped":          True,
                })
                continue

            # build 5 × 1 DataFrame with proteins on the index
            col_df = pd.DataFrame(
                {pid: [
                    abund.get(f) if abund.get(f) not in (None, 0) else np.nan
                    for f in feats
                ]},
                index=feats,
                dtype=float,
            )

            # run the pipeline (transpose happens inside FunctionTransformer)
            score = float(pipe.predict(col_df)[0])

            results.append({
                **meta_rec,
                "syntax_score":    score,
                "missing_fraction": float(missing_frac),
            })

    driver.close()
    return JsonResponse({
        "results":  results,
        "warnings": warnings_list      # only rows skipped for >50 % missing
    })
