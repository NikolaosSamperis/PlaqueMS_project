from django.shortcuts import render
from django.http import JsonResponse
from neo4j import GraphDatabase, basic_auth
from django.conf import settings
from django.contrib.auth.decorators import login_required
import os


def get_neo4j_db():
    uri = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    driver = GraphDatabase.driver(uri, auth=basic_auth(username, password))
    return driver

@login_required(login_url='login')
def plaquery_view(request):
    driver = get_neo4j_db()
    with driver.session(database="plaquems") as session:
        # 1. Get unique experiments from the Experiment node.
        experiments_query = "MATCH (e:Experiment) RETURN DISTINCT e.name AS experiment"
        experiments = [record["experiment"] for record in session.run(experiments_query)]

        # 2. Get unique Histology values from the Patient node.
        histology_query = "MATCH (p:Patient) RETURN DISTINCT p.Histology AS histology"
        histologies = [record["histology"] for record in session.run(histology_query) if
                       record["histology"] is not None]

        # 3. Get unique Ultrasound values from the Patient node.
        ultrasound_query = "MATCH (p:Patient) RETURN DISTINCT p.Ultrasound AS ultrasound"
        ultrasounds = [record["ultrasound"] for record in session.run(ultrasound_query) if
                       record["ultrasound"] is not None]

        # 4. Get unique Sex values from the Patient node.
        sex_query = "MATCH (p:Patient) RETURN DISTINCT p.Sex AS sex"
        sexes = [record["sex"] for record in session.run(sex_query) if record["sex"] is not None]

        # 5. Get unique Symptoms values from the Patient node.
        symptoms_query = "MATCH (p:Patient) RETURN DISTINCT p.Symptoms AS symptoms"
        symptoms = [record["symptoms"] for record in session.run(symptoms_query) if record["symptoms"] is not None]

        # 6. Get unique Age values from the Patient node and categorize them.
        age_query = "MATCH (p:Patient) RETURN DISTINCT p.Age AS age"
        ages = [record["age"] for record in session.run(age_query) if record["age"] is not None]

        # 7. Get unique Calcified by description values from the Patient node.
        calcification_query = "MATCH (p:Patient) RETURN DISTINCT p.`Calcified by description` AS calcification"
        calcifications = [record["calcification"] for record in session.run(calcification_query) if
                          record["calcification"] is not None]
        # 8. Get unique Tissue Area values from the Sample node.
        tissue_area_query = "MATCH (s:Sample) RETURN DISTINCT s.area AS area"
        tissue_areas = [record["area"] for record in session.run(tissue_area_query) if record["area"] is not None]

    driver.close()

    # Categorize ages into groups: under40 (<40), 40to60 (>=40 and <=60), and over60 (>60)
    age_groups_set = set()
    for age in ages:
        try:
            a = float(age)
            if a < 40:
                age_groups_set.add("under40")
            elif a <= 60:
                age_groups_set.add("40to60")
            else:
                age_groups_set.add("over60")
        except Exception as ex:
            continue
    # Ensure a consistent order for age groups.
    age_group_order = ["under40", "40to60", "over60"]
    age_groups = [group for group in age_group_order if group in age_groups_set]

    # Define BMI ranges using common thresholds.
    bmi_ranges = [
        {"label": "Underweight(<18.5)", "value": "underweight"},
        {"label": "Normal(18.5-24.9)", "value": "normal"},
        {"label": "Overweight(25-29.9)", "value": "overweight"},
        {"label": "Obese(30+)", "value": "obese"}
    ]

    # Define Pack‑years ranges.
    pack_years_ranges = [
        {"label": "Light smoker(1-20)", "value": "light"},
        {"label": "Moderate smoker(20.1-40)", "value": "moderate"},
        {"label": "Heavy smoker(>40)", "value": "heavy"}
    ]

    context = {
        'experiments': experiments,
        'histologies': histologies,
        'ultrasounds': ultrasounds,
        'sexes': sexes,
        'symptoms': symptoms,
        'age_groups': age_groups,
        'calcifications': calcifications,
        'tissue_areas': tissue_areas,
        'smoker_status': ['Active smoker', 'Past smoker', 'Never smoker'],
        'bmi_ranges': bmi_ranges,
        'pack_years_ranges': pack_years_ranges,
    }
    return render(request, 'plaquery.html', context)


def get_protein_ids(request):
    query = 'MATCH (p:Protein) RETURN p.name AS protein_name'
    driver = get_neo4j_db()
    with driver.session(database="plaquems") as session:
        results = session.run(query)
        proteins = [record['protein_name'] for record in results]
    driver.close()
    return JsonResponse({'proteins': proteins})


def get_abundance_data(request):
    # Get filter parameters (default to empty lists if not provided)
    protein_names = request.GET.getlist('protein_name')
    tissue_areas = request.GET.getlist('tissue_area')
    experiment = request.GET.getlist('experiment')
    histology = request.GET.getlist('histology')
    ultrasound = request.GET.getlist('ultrasound')
    sex = request.GET.getlist('sex')
    age = request.GET.getlist('age')
    symptoms = request.GET.getlist('symptoms')
    calcified = request.GET.getlist('calcification')
    clinical_conditions = request.GET.getlist('clinical_condition')
    medications = request.GET.getlist('medications')
    smoker_status = request.GET.getlist('smoker_status')
    bmi_range = request.GET.getlist('bmi_range')
    pack_years_range = request.GET.getlist('pack_years_range')
    cv_biomarkers = request.GET.getlist('cvbiomarker')
    clinical_outcomes = request.GET.getlist('clinical_outcomes')
    seen = set()
    protein_names = [x for x in protein_names if not (x in seen or seen.add(x))]

    params = {}
    base_filters = []
    if experiment and experiment[0] != 'Select Experiment':
        base_filters.append("s.experiment IN $experiment")
        params['experiment'] = experiment
    if tissue_areas:
        base_filters.append("s.area IN $tissue_area")
        params['tissue_area'] = tissue_areas
    if protein_names:
        params['protein_name'] = protein_names

    extra_filters = ""
    if base_filters:
        extra_filters = " AND " + " AND ".join(base_filters)

    # Aggregated stats query using CALL
    aggregated_query = f"""
    CALL () {{
      // 1) run once per alias 
      UNWIND $protein_name AS q

      // 2) find the matching Protein node by checking its name-list
      MATCH (s:Sample)-[r:ABUNDANCE]->(p:Protein)
      WHERE q IN p.name{extra_filters}

      // 3) unwind the full list back to rows but keep only the one we care about
      UNWIND p.name AS alias
      WITH s, r, q, alias
      WHERE alias = q

      // 4) return exactly that alias as Protein
      RETURN
        alias           AS Protein,
        s.area          AS SampleArea,
        s.experiment    AS Experiment,
        round(avg(r.abundance)*100)/100 AS AvgAbundance,
        round(min(r.abundance)*100)/100 AS MinAbundance,
        round(max(r.abundance)*100)/100 AS MaxAbundance,
        round(stdev(r.abundance)*100)/100 AS StdDeviation
    }}
    WITH Protein, SampleArea, Experiment, AvgAbundance, MinAbundance, MaxAbundance, StdDeviation
    MATCH (s:Sample)-[r:ABUNDANCE]->(p:Protein)
    WHERE Protein IN p.name
        AND s.area       = SampleArea
        AND s.experiment = Experiment
    """

    # Build non-clinical filters
    non_clinical_filters = []
    if sex and sex[0] != 'Filter by Sex':
        non_clinical_filters.append("pt.Sex IN $sex")
        params['sex'] = sex
    if histology and histology[0] != 'Select Plaque Histology':
        non_clinical_filters.append("pt.Histology IN $histology")
        params['histology'] = histology
    if ultrasound and ultrasound[0] != 'Select Plaque Ultrasound':
        non_clinical_filters.append("pt.Ultrasound IN $ultrasound")
        params['ultrasound'] = ultrasound
    if symptoms and symptoms[0] != 'Filter by Symptoms':
        non_clinical_filters.append("pt.Symptoms IN $symptoms")
        params['symptoms'] = symptoms
    if calcified and calcified[0] != 'Filter by Calcification':
        non_clinical_filters.append("pt.`Calcified by description` IN $calcified")
        params['calcified'] = calcified

    # Process age filters
    age_conditions = []
    if age and age[0] != 'Filter by Age':
        for a in age:
            if a == 'under40':
                age_conditions.append("pt.Age < 40")
            elif a == '40to60':
                age_conditions.append("(pt.Age >= 40 AND pt.Age <= 60)")
            elif a == 'over60':
                age_conditions.append("pt.Age > 60")
    if age_conditions:
        non_clinical_filters.append("(" + " OR ".join(age_conditions) + ")")

    # Process smoker filters
    smoker_conditions = []
    if smoker_status:
        if "Active smoker" in smoker_status:
            smoker_conditions.append("pt.`Active smoker` = 'yes'")
        if "Past smoker" in smoker_status:
            smoker_conditions.append("pt.`Past smoker` = 'yes'")
        if "Never smoker" in smoker_status:
            smoker_conditions.append("pt.`Never smoker` = 'yes'")
        if smoker_conditions:
            non_clinical_filters.append("(" + " OR ".join(smoker_conditions) + ")")

    # Process BMI ranges
    bmi_conditions = []
    if bmi_range:
        if "underweight" in bmi_range:
            bmi_conditions.append("pt.BMI < 18.5")
        if "normal" in bmi_range:
            bmi_conditions.append("(pt.BMI >= 18.5 AND pt.BMI < 25)")
        if "overweight" in bmi_range:
            bmi_conditions.append("(pt.BMI >= 25 AND pt.BMI < 30)")
        if "obese" in bmi_range:
            bmi_conditions.append("pt.BMI >= 30")
        if bmi_conditions:
            non_clinical_filters.append("(" + " OR ".join(bmi_conditions) + ")")

    # Process Pack‑years ranges
    pack_years_conditions = []
    if pack_years_range:
        if "light" in pack_years_range:
            pack_years_conditions.append("(pt.`Pack-years` >= 1 AND pt.`Pack-years` <= 20)")
        if "moderate" in pack_years_range:
            pack_years_conditions.append("(pt.`Pack-years` > 20 AND pt.`Pack-years` <= 40)")
        if "heavy" in pack_years_range:
            pack_years_conditions.append("pt.`Pack-years` > 40")
        if smoker_status and "Never smoker" in smoker_status:
            pack_years_conditions.append("pt.`Never smoker` = 'yes'")
        if pack_years_conditions:
            non_clinical_filters.append("(" + " OR ".join(pack_years_conditions) + ")")

    # Filter for Contralateral stenosis(≥60%) if selected in cv_biomarkers
    if "Contralateral stenosis(≥60%)" in cv_biomarkers:
        non_clinical_filters.append("pt.`Contralateral stenosis(≥60%)` = 'yes'")

    # Build clinical condition filters with AND (more strict)
    clinical_condition_filters = []
    for condition in clinical_conditions:
        clinical_condition_filters.append(f"pt.`{condition}` = 'yes'")

    # Build clinical outcomes filters with AND (more strict)
    clinical_outcomes_filters = []
    for outcome in clinical_outcomes:
        if outcome.lower() == 'primary endpoint':
            clinical_outcomes_filters.append("pt.`Primary endpoint` = 'event'")
        else:
            clinical_outcomes_filters.append(f"pt.`{outcome}` = 'yes'")

    # Build medication filters with AND (more strict)
    medication_filters = []
    for med in medications:
        medication_filters.append(f"pt.`{med}` = 'yes'")

    combined_clinical_filters = []
    if clinical_condition_filters:
        combined_clinical_filters.append("(" + " AND ".join(clinical_condition_filters) + ")")
    if medication_filters:
        combined_clinical_filters.append("(" + " AND ".join(medication_filters) + ")")

    # Combine non-clinical and clinical filters.
    combined_filters = []
    if non_clinical_filters:
        combined_filters.append(" AND ".join(non_clinical_filters))
    if combined_clinical_filters:
        combined_filters.append(" AND ".join(combined_clinical_filters))
    if clinical_outcomes_filters:
        combined_filters.append("(" + " AND ".join(clinical_outcomes_filters) + ")")

    if combined_filters:
        aggregated_query += "\nMATCH (pt:Patient {id: s.patientID})\nWHERE " + " AND ".join(combined_filters)
    else:
        aggregated_query += "\nMATCH (pt:Patient {id: s.patientID})"

    # Build RETURN clause: default columns always appear.
    return_columns = [
        "Protein",
        "s.patientID AS PatientID",
        "SampleArea",
        "Experiment",
        "round(r.abundance*100)/100 AS Abundance",
        "AvgAbundance",
        "MinAbundance",
        "MaxAbundance",
        "StdDeviation"
    ]

    # Build additional columns.
    additional_columns = []
    # If no additional filter has been selected, include all optional columns.
    if (not sex) and (not age) and (not symptoms) and (not histology) and (not ultrasound) and (not calcified) and (not clinical_conditions) and (not clinical_outcomes) and (not medications) and (not smoker_status) and (not bmi_range) and (not pack_years_range) and (not cv_biomarkers):
        # Demographics and basic clinical info
        additional_columns.extend([
            "pt.Sex AS Sex",
            "pt.Age AS Age",
            "pt.Symptoms AS Symptoms",
            "pt.Histology AS Histology",
            "pt.Ultrasound AS Ultrasound",
            "pt.`Calcified by description` AS `Calcification (description)`",
        ])
        # Include all clinical conditions by default (update these names if needed)
        additional_columns.extend([
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
            "pt.`Stroke history` AS `Stroke history`"
        ])
        # Include all clinical outcomes by default
        additional_columns.extend([
            "pt.`Stroke` AS `Stroke`",
            "pt.`Transient ischemic attack` AS `Transient ischemic attack`",
            "pt.`Cardiovascular mortality` AS `Cardiovascular mortality`",
            "pt.`Primary endpoint` AS `Primary endpoint`"
        ])
        # Include all medications by default
        additional_columns.extend([
            "pt.`ACE inhibitors` AS `ACE inhibitors`",
            "pt.`ARB therapy` AS `ARB therapy`",
            "pt.`Antiplatelet` AS `Antiplatelet`",
            "pt.`Aspirin` AS `Aspirin`",
            "pt.`Beta blockers` AS `Beta blockers`",
            "pt.`Statins` AS `Statins`",
            "pt.`Clopidogrel` AS `Clopidogrel`",
            "pt.`Diuretics` AS `Diuretics`"
        ])
        # Lifestyle filters
        additional_columns.append("pt.`Active smoker` AS `Active smoker`")
        additional_columns.append("pt.`Past smoker` AS `Past smoker`")
        additional_columns.append("pt.`Never smoker` AS `Never smoker`")
        additional_columns.append("pt.BMI AS BMI")
        additional_columns.append("CASE WHEN pt.`Never smoker` = 'yes' THEN 0 ELSE pt.`Pack-years` END AS `Pack-years`")
        # Default cardiovascular biomarkers.
        additional_columns.extend([
            "toFloat(pt.`Cholesterol(total)`) AS `Cholesterol(total)`",
            "toFloat(pt.`HDL`) AS `HDL`",
            "toFloat(pt.`High-sensitivity CRP`) AS `High-sensitivity CRP`",
            "toFloat(pt.`Ultrasensitive CRP`) AS `Ultrasensitive CRP`",
            "toFloat(pt.`LDL`) AS `LDL`",
            "toFloat(pt.`Triglycerides`) AS `Triglycerides`",
            "toFloat(pt.`Pre-surgery BP(diastolic)`) AS `Pre-surgery BP(diastolic)`",
            "toFloat(pt.`Pre-surgery BP(systolic)`) AS `Pre-surgery BP(systolic)`",
            "pt.`Contralateral stenosis(≥60%)` AS `Contralateral stenosis(≥60%)`",
            "toFloat(pt.`Stenosis grade(%)`) AS `Stenosis grade(%)`"
        ])
    else:
        # If additional filters are provided, only include columns corresponding to the selected filters.
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
            additional_columns.append("pt.`Calcified by description` AS `Calcification (description)`")
        for condition in clinical_conditions:
            alias = condition.replace(" ", "_")
            additional_columns.append(f"pt.`{condition}` AS `{alias}`")
        for outcome in clinical_outcomes:
            alias = outcome.replace(" ", "_")
            additional_columns.append(f"pt.`{outcome}` AS `{alias}`")
        for med in medications:
            alias = med.replace(" ", "_")
            additional_columns.append(f"pt.`{med}` AS `{alias}`")
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

    all_columns = return_columns + additional_columns
    return_clause = "RETURN " + ", ".join(all_columns) + "\nORDER BY Protein, SampleArea, PatientID"
    final_query = aggregated_query + "\n" + return_clause

    driver = get_neo4j_db()
    with driver.session(database="plaquems") as session:
        results = session.run(final_query, params)
        abundance_records = []
        for record in results:
            rec = {}
            for key in record.keys():
                value = record[key]
                if isinstance(value, float):
                    rec[key] = round(value, 2)
                else:
                    rec[key] = value
            abundance_records.append(rec)
    driver.close()
    return JsonResponse({'records': abundance_records})
