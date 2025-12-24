# insert_views.py
from django.shortcuts import HttpResponse
from django.conf import settings
from Plaque_MS_app.models import Proteins, Datasets, Statistics, ExperimentsTypes, DocAndExperiment, Networks, \
    NetworkAndExperiment, DiffResult
from django.db import transaction
import os
import pandas as pd
import csv
import numpy as np
import uuid
from pathlib import Path


@transaction.atomic
def insert_protein_data(request):
    file_path = os.path.join(settings.BASE_DIR, "static", "HUMAN_9606_idmapping.dat")

    # Load CSV
    df = pd.read_csv(file_path, header=None, encoding='utf-8', delimiter="\t", quoting=csv.QUOTE_NONE)
    print(f"✅ CSV Loaded - Total Rows: {len(df)}")

    # Select the relevant columns
    df_selected = df[[0, 1, 2]].fillna("NA")
    df_selected.columns = ['Uniprot_Accession_ID', 'UniProtKB_ID', 'Gene_Name']

    print(f"📊 Sample Data:\n{df_selected.head()}")
    print(f"🔍 Unique values in UniProtKB_ID: {df_selected['UniProtKB_ID'].nunique()}")
    print(f"🔍 Unique values in Gene_Name: {df_selected['Gene_Name'].nunique()}")

    # Convert dataframe to list
    protein_list = []
    for _, row in df_selected.iterrows():
        protein = Proteins(
            protein_id=str(uuid.uuid4()),
            uniprot_accession_id=row["Uniprot_Accession_ID"],
            uniprotkb_id=row["UniProtKB_ID"],
            gene_name=row["Gene_Name"]
        )
        protein_list.append(protein)

    print(f"📝 Total proteins prepared for insertion: {len(protein_list)}")

    # Bulk insert into database
    if protein_list:
        try:
            Proteins.objects.bulk_create(protein_list)
            print(f"✅ Inserted {len(protein_list)} records into the Proteins table.")
        except Exception as e:
            print(f"❌ Error inserting records: {e}")

    # Verify if data was inserted
    inserted_count = Proteins.objects.count()
    print(f"📂 Total records in Proteins table after insertion: {inserted_count}")

    return HttpResponse(f'Inserted {len(protein_list)} proteins successfully')


@transaction.atomic
def insert_dataset(request):
    folder = os.path.join("static", "PlaqueMS")
    abs_folder = os.path.join(settings.BASE_DIR, folder)
    if not os.path.exists(abs_folder):
        return HttpResponse("Error: Folder does not exist", status=400)

    filenames = os.listdir(abs_folder)
    for filename in filenames:
        if filename != ".DS_Store":
            dataset = Datasets(
                dataset_id=str(uuid.uuid4()),
                name=filename.replace("_", " "),
                position="",
                description=""
            )
            dataset.save()
    return HttpResponse('Insert dataset complete')


@transaction.atomic
def insert_one(request):
    dataset_name = "Carotid Plaques Athero-Express"
    try:
        dataset = Datasets.objects.get(name=dataset_name)
    except Datasets.DoesNotExist:
        return HttpResponse(f"Error: Dataset '{dataset_name}' does not exist", status=400)

    folder = os.path.join("static", "PlaqueMS", "Carotid_Plaques_Athero-Express")
    abs_folder = os.path.join(settings.BASE_DIR, folder)
    if not os.path.exists(abs_folder):
        return HttpResponse("Error: Folder does not exist", status=400)

    filenames = os.listdir(abs_folder)
    for filename in filenames:
        if filename != ".DS_Store":
            experiments_types = ExperimentsTypes()
            first_id = str(uuid.uuid4())
            experiments_types.experiment_id = first_id
            experiments_types.pathname = filename.replace("_", " ")
            experiments_types.path_type = "00"
            # strip static/ out of the stored path
            rel = os.path.join(folder, filename).replace("\\", "/")
            if rel.startswith("static/"):
                rel = rel[len("static/"):]
            experiments_types.path = rel
            experiments_types.parent_id = ""
            experiments_types.dataset_id = dataset.dataset_id
            experiments_types.save()

            second_folder = os.path.join(abs_folder, filename, "statistics")
            if os.path.exists(second_folder):
                second_files = os.listdir(second_folder)
                for sec_filename in second_files:
                    if "vs" in sec_filename:
                        if not ExperimentsTypes.objects.filter(
                                pathname=sec_filename.replace("_", " "),
                                parent_id=first_id
                        ).exists():
                            second = ExperimentsTypes()
                            second_id = str(uuid.uuid4())
                            second.experiment_id = second_id
                            second.pathname = sec_filename.replace("_", " ")
                            second.path_type = "01"
                            rel2 = os.path.join(folder, filename, "statistics", sec_filename).replace("\\", "/")
                            if rel2.startswith("static/"):
                                rel2 = rel2[len("static/"):]
                            second.path = rel2
                            second.parent_id = first_id
                            second.dataset_id = dataset.dataset_id
                            second.save()

                            current_stat_folder = os.path.join(abs_folder, filename, "statistics", sec_filename)
                            insert_bplot(current_stat_folder, second_id)
                            insert_statistics(current_stat_folder, second_id)
    return HttpResponse('Insert complete')


def insert_two_logic():
    """
    Exact logic from the original insert_two view.
    """
    dataset_name = "Carotid Plaques Vienna Cohort"
    dataset = Datasets.objects.get(name=dataset_name)

    folder = os.path.join("static", "PlaqueMS", "Carotid_Plaques_Vienna_Cohort")
    abs_folder = os.path.join(settings.BASE_DIR, folder)
    filenames = os.listdir(abs_folder)
    for filename in filenames:
        if filename not in (".DS_Store", ".ipynb_checkpoints"):
            experiments_types = ExperimentsTypes()
            first_id = str(uuid.uuid4())
            experiments_types.experiment_id = first_id
            experiments_types.pathname = filename.replace("_", " ")
            experiments_types.path_type = "00"
            rel = os.path.join(folder, filename).replace("\\", "/")
            if rel.startswith("static/"):
                rel = rel[len("static/"):]
            experiments_types.path = rel
            experiments_types.parent_id = ""
            experiments_types.dataset_id = dataset.dataset_id
            experiments_types.save()

            second_folder = os.path.join(folder, filename, "statistics")
            abs_second_folder = os.path.join(settings.BASE_DIR, second_folder)
            second_files = os.listdir(abs_second_folder)
            for sec_filename in second_files:
                if sec_filename not in (".DS_Store", ".ipynb_checkpoints") and "vs" in sec_filename:
                    if not ExperimentsTypes.objects.filter(
                            pathname=sec_filename.replace("_", " "),
                            parent_id=first_id
                    ).exists():
                        second = ExperimentsTypes()
                        second_id = str(uuid.uuid4())
                        second.experiment_id = second_id
                        second.pathname = sec_filename.replace("_", " ")
                        second.path_type = "01"
                        rel2 = os.path.join(second_folder, sec_filename).replace("\\", "/")
                        if rel2.startswith("static/"):
                            rel2 = rel2[len("static/"):]
                        second.path = rel2
                        second.parent_id = first_id
                        second.dataset_id = dataset.dataset_id
                        second.save()

                        current_stat_folder = os.path.join(abs_second_folder, sec_filename)
                        insert_bplot(current_stat_folder, second_id)
                        insert_statistics(current_stat_folder, second_id)
                elif sec_filename not in (".DS_Store", ".ipynb_checkpoints"):
                    second = ExperimentsTypes()
                    second_id = str(uuid.uuid4())
                    second.experiment_id = second_id
                    second.pathname = sec_filename.replace("_", " ")
                    second.path_type = "00"
                    rel3 = os.path.join(second_folder, sec_filename).replace("\\", "/")
                    if rel3.startswith("static/"):
                        rel3 = rel3[len("static/"):]
                    second.path = rel3
                    second.parent_id = first_id
                    second.dataset_id = dataset.dataset_id
                    second.save()

                    third_folder = os.path.join(second_folder, sec_filename)
                    abs_third_folder = os.path.join(settings.BASE_DIR, third_folder)
                    third_files = os.listdir(abs_third_folder)
                    for thr_filename in third_files:
                        if thr_filename not in (".DS_Store", ".ipynb_checkpoints"):
                            if "network" in thr_filename:
                                insert_network(os.path.join(abs_third_folder), thr_filename, second_id)
                            elif "yes or no" in thr_filename:
                                third = ExperimentsTypes()
                                third_id = str(uuid.uuid4())
                                third.experiment_id = third_id
                                third.pathname = thr_filename.replace("_", " ")
                                third.path_type = "00"
                                rel4 = os.path.join(third_folder, thr_filename).replace("\\", "/")
                                if rel4.startswith("static/"):
                                    rel4 = rel4[len("static/"):]
                                third.path = rel4
                                third.parent_id = second_id
                                third.dataset_id = dataset.dataset_id
                                third.save()

                                fourth_folder = os.path.join(third_folder, thr_filename)
                                abs_fourth_folder = os.path.join(settings.BASE_DIR, fourth_folder)
                                fourth_files = os.listdir(abs_fourth_folder)
                                for four_filename in fourth_files:
                                    if four_filename not in (".DS_Store", ".ipynb_checkpoints"):
                                        fourth = ExperimentsTypes()
                                        fourth_id = str(uuid.uuid4())
                                        fourth.experiment_id = fourth_id
                                        fourth.pathname = four_filename.replace("_", " ")
                                        fourth.path_type = "01"
                                        rel5 = os.path.join(fourth_folder, four_filename).replace("\\", "/")
                                        if rel5.startswith("static/"):
                                            rel5 = rel5[len("static/"):]
                                        fourth.path = rel5
                                        fourth.parent_id = third_id
                                        fourth.dataset_id = dataset.dataset_id
                                        fourth.save()
                                        insert_bplot(os.path.join(abs_fourth_folder, four_filename), fourth_id)
                                        insert_statistics(os.path.join(abs_fourth_folder, four_filename), fourth_id)
                            else:
                                third = ExperimentsTypes()
                                third_id = str(uuid.uuid4())
                                third.experiment_id = third_id
                                third.pathname = thr_filename.replace("_", " ")
                                third.path_type = "01"
                                rel6 = os.path.join(third_folder, thr_filename).replace("\\", "/")
                                if rel6.startswith("static/"):
                                    rel6 = rel6[len("static/"):]
                                third.path = rel6
                                third.parent_id = second_id
                                third.dataset_id = dataset.dataset_id
                                third.save()
                                insert_bplot(os.path.join(abs_third_folder, thr_filename), third_id)
                                insert_statistics(os.path.join(abs_third_folder, thr_filename), third_id)


def insert_three_logic():
    """
    Exact logic from the original insert_three view.
    """
    dataset_name = "Coronary Arteries University of Virginia Cohort"
    dataset = Datasets.objects.get(name=dataset_name)

    folder = os.path.join("static", "PlaqueMS", "Coronary_Arteries_University_of_Virginia_Cohort")
    abs_folder = os.path.join(settings.BASE_DIR, folder)
    if not os.path.exists(abs_folder):
        return

    processed_paths = set()
    filenames = os.listdir(abs_folder)
    for filename in filenames:
        if filename == ".DS_Store":
            continue
        first_path = os.path.join(folder, filename).replace("\\", "/")
        if first_path in processed_paths:
            continue

        experiments_types = ExperimentsTypes()
        first_id = str(uuid.uuid4())
        experiments_types.experiment_id = first_id
        experiments_types.pathname = filename.replace("_", " ")
        experiments_types.path_type = "00"
        fp1 = first_path
        if fp1.startswith("static/"):
            fp1 = fp1[len("static/"):]
        experiments_types.path = fp1
        experiments_types.parent_id = ""
        experiments_types.dataset_id = dataset.dataset_id
        experiments_types.save()
        processed_paths.add(first_path)

        second_folder = os.path.join(folder, filename, "statistics")
        abs_second_folder = os.path.join(settings.BASE_DIR, second_folder)
        if os.path.exists(abs_second_folder):
            second_files = os.listdir(abs_second_folder)
            for sec_filename in second_files:
                abs_sec_path = os.path.join(abs_second_folder, sec_filename)
                if not os.path.isdir(abs_sec_path) or sec_filename in (".DS_Store",) or sec_filename.startswith(
                        "_bplots"):
                    continue

                second_path = os.path.join(second_folder, sec_filename).replace("\\", "/")
                if second_path in processed_paths:
                    continue

                second = ExperimentsTypes()
                second_id = str(uuid.uuid4())
                second.experiment_id = second_id
                second.pathname = sec_filename.replace("_", " ")
                second.path_type = "00" if "in segments" in sec_filename else "01"
                rp = second_path
                if rp.startswith("static/"):
                    rp = rp[len("static/"):]
                second.path = rp
                second.parent_id = first_id
                second.dataset_id = dataset.dataset_id
                second.save()
                processed_paths.add(second_path)

                if second.path_type == "00":
                    third_folder = os.path.join(second_folder, sec_filename)
                    abs_third_folder = os.path.join(settings.BASE_DIR, third_folder)
                    if os.path.exists(abs_third_folder):
                        third_files = os.listdir(abs_third_folder)
                        for thr_filename in third_files:
                            abs_thr_path = os.path.join(abs_third_folder, thr_filename)
                            if not os.path.isdir(abs_thr_path) or thr_filename in (
                            ".DS_Store",) or thr_filename.startswith("_bplots"):
                                continue

                            third_path = os.path.join(third_folder, thr_filename).replace("\\", "/")
                            if third_path in processed_paths:
                                continue

                            third = ExperimentsTypes()
                            third_id = str(uuid.uuid4())
                            third.experiment_id = third_id
                            third.pathname = thr_filename.replace("_", " ")
                            third.path_type = "01"
                            tp = third_path
                            if tp.startswith("static/"):
                                tp = tp[len("static/"):]
                            third.path = tp
                            third.parent_id = second_id
                            third.dataset_id = dataset.dataset_id
                            third.save()
                            processed_paths.add(third_path)

                            insert_bplot(abs_thr_path, third_id)
                            insert_statistics(abs_thr_path, third_id)
                else:
                    insert_bplot(abs_sec_path, second_id)
                    insert_statistics(abs_sec_path, second_id)


@transaction.atomic
def insert_two(request):
    try:
        insert_two_logic()
    except Datasets.DoesNotExist:
        return HttpResponse(
            "Error: Dataset 'Carotid Plaques Vienna Cohort' does not exist",
            status=400
        )
    return HttpResponse('Insert two complete')


@transaction.atomic
def insert_three(request):
    try:
        insert_three_logic()
    except Datasets.DoesNotExist:
        return HttpResponse(
            "Error: Dataset 'Coronary Arteries University of Virginia Cohort' does not exist",
            status=400
        )
    return HttpResponse('Insert three complete')


def insert_bplot(folder, experiment_id):
    bplot_folder = os.path.join(folder, "_bplots")
    if os.path.exists(bplot_folder) and os.path.isdir(bplot_folder):
        filenames = os.listdir(bplot_folder)
        # compute relative path prefix
        filepath_prefix = os.path.relpath(bplot_folder, settings.BASE_DIR).replace("\\", "/") + "/"
        # strip leading static/
        if filepath_prefix.startswith("static/"):
            filepath_prefix = filepath_prefix[len("static/"):]
        if filenames:
            for filename in filenames:
                if filename != ".DS_Store":
                    base_name, ext = os.path.splitext(filename)
                    clean_name = base_name.replace("_", " ")
                    doc_id = str(uuid.uuid4())
                    doc = Statistics()
                    doc.doc_id = doc_id
                    doc.filename = clean_name
                    doc.filepath = filepath_prefix + filename
                    doc.doc_type = "00"
                    doc.save()
                    doc_and_experiment = DocAndExperiment()
                    doc_and_experiment.id = str(uuid.uuid4())
                    doc_and_experiment.doc_id = doc_id
                    doc_and_experiment.experiment_id = experiment_id
                    doc_and_experiment.save()


def insert_statistics(folder, experiment_id):
    folder = folder + '/'
    filenames = os.listdir(folder)
    # compute relative path prefix
    filepath_prefix = os.path.relpath(folder, settings.BASE_DIR).replace("\\", "/") + "/"
    # strip leading static/
    if filepath_prefix.startswith("static/"):
        filepath_prefix = filepath_prefix[len("static/"):]
    for filename in filenames:
        base_name, ext = os.path.splitext(filename)
        clean_name = base_name.replace("_", " ")

        if "heatmap" in filename:
            doc_id = str(uuid.uuid4())
            doc = Statistics()
            doc.doc_id = doc_id
            doc.filename = clean_name
            doc.filepath = filepath_prefix + filename
            doc.doc_type = "02"
            doc.save()

            doc_and_experiment = DocAndExperiment()
            doc_and_experiment.id = str(uuid.uuid4())
            doc_and_experiment.doc_id = doc_id
            doc_and_experiment.experiment_id = experiment_id
            doc_and_experiment.save()
        elif "volcano" in filename:
            doc_id = str(uuid.uuid4())
            doc = Statistics()
            doc.doc_id = doc_id
            doc.filename = clean_name
            doc.filepath = filepath_prefix + filename
            doc.doc_type = "01"
            doc.label = '00' if "unlabeled" in filename else '01'
            doc.save()
            doc_and_experiment = DocAndExperiment()
            doc_and_experiment.id = str(uuid.uuid4())
            doc_and_experiment.doc_id = doc_id
            doc_and_experiment.experiment_id = experiment_id
            doc_and_experiment.save()
        elif "diff_exp" in filename:
            doc_id = str(uuid.uuid4())
            doc = Statistics()
            doc.doc_id = doc_id
            doc.filename = clean_name
            doc.filepath = filepath_prefix + filename
            doc.doc_type = "03"
            doc.save()
            doc_and_experiment = DocAndExperiment()
            doc_and_experiment.id = str(uuid.uuid4())
            doc_and_experiment.doc_id = doc_id
            doc_and_experiment.experiment_id = experiment_id
            doc_and_experiment.save()
    return HttpResponse('insert complete')


def insert_network(folder, filename, experiment_id):
    id = str(uuid.uuid4())
    network = Networks()
    network.network_id = id
    base_name, ext = os.path.splitext(filename)
    clean_name = base_name.replace("_", " ")
    network.filename = clean_name
    # Compute the relative path regardless of whether 'folder' is absolute or relative
    relative_path = os.path.relpath(os.path.join(folder, filename), settings.BASE_DIR).replace("\\", "/")
    # strip leading static/
    if relative_path.startswith("static/"):
        relative_path = relative_path[len("static/"):]
    network.filepath = relative_path
    network_and_experiment = NetworkAndExperiment()
    network_and_experiment.id = str(uuid.uuid4())
    network_and_experiment.network_id = id
    network_and_experiment.experiment_id = experiment_id
    network.save()
    network_and_experiment.save()


@transaction.atomic
def insert_diff(request):
    diff_stats = Statistics.objects.filter(doc_type='03')

    total = 0
    for stat in diff_stats:
        doc_links = DocAndExperiment.objects.filter(doc_id=stat.doc_id)
        print(f"Found {len(doc_links)} DocAndExperiment links for doc_id: {stat.doc_id}")

        for link in doc_links:
            current_exp_id = link.experiment_id
            found_network = False

            while current_exp_id:
                net_link = NetworkAndExperiment.objects.filter(experiment_id=current_exp_id).first()

                if net_link:
                    print(f"Found network_id: {net_link.network_id} for experiment_id: {current_exp_id}")

                    # 🔑  ➜ use *stat.doc_id* (already exists in Statistics)
                    #     and skip if that network/doc pair is already present
                    if not DiffResult.objects.filter(
                        doc_id=stat.doc_id,
                        network_id=net_link.network_id
                    ).exists():
                        DiffResult.objects.create(
                            doc_id=stat.doc_id,           # FK → Statistics
                            filename=stat.filename,
                            filepath=stat.filepath,
                            network_id=net_link.network_id
                        )
                        total += 1

                    found_network = True
                    break

                experiment = ExperimentsTypes.objects.filter(experiment_id=current_exp_id).first()
                if not experiment or not experiment.parent_id:
                    break

                current_exp_id = experiment.parent_id

            if not found_network:
                print(f"No network found in the entire hierarchy for doc_id: {stat.doc_id}")

    return HttpResponse(f"Inserted {total} diff_exp_result files successfully.")
