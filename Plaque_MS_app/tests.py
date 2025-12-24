from django.test import TestCase
from Plaque_MS_app.models import Proteins, Datasets, Networks, ExperimentsTypes, NetworkAndExperiment, DocAndExperiment, \
    Statistics, DiffResult


# Create your tests here.
class ModelTest(TestCase):
    def setUp(self):
        Proteins.objects.create(protein_id="00001933-50f8-410e-93c9-010d457bcb47", uniprot_accession_id="B5LFX9",
                                uniprotkb_id="B5LFX9_HUMAN", gene_name="HLA-G")
        Datasets.objects.create(dataset_id="3542c8b3-224b-41ae-8598-a9eeed0f8eb0",
                                name="Coronary Arteries University of Virginia Cohort",
                                position="Coronary Arteries", description="")
        Networks.objects.create(network_id="6c770831-ee04-478a-bdc9-026a40f41d8c",
                                filename="gu_core_filtered_directed_network.txt",
                                filepath="static/PlaqueMS/Carotid_Plaques_Vienna_Cohort/GUHCL_TMT/Statistics/core/gu_core_filtered_directed_network.txt",
                                description="")
        ExperimentsTypes.objects.create(experiment_id="d715589f-ea04-4c1f-b78e-1b0573e57214",
                                        pathname="core", path_type="00",
                                        path="static/PlaqueMS/Carotid_Plaques_Vienna_Cohort/GUHCL_TMT/Statistics/core",
                                        parent_id="349ab7d5-0d64-4e0c-8b30-9c7e64588754",
                                        dataset_id="972d974a-e013-44a5-9e68-6e275f08765f")
        DocAndExperiment.objects.create(id="00003b6f-6dbd-428e-a570-3676bb6f71d4",
                                        experiment_id="ee7d7412-72dc-48e7-a2e5-d8815210fae5",
                                        doc_id="8e3affa0-283a-4045-8768-a5234e8e271a")
        NetworkAndExperiment.objects.create(id="ff1a12cf-63ce-425c-8b01-d130d79e2258",
                                            experiment_id="9e800f9b-fec6-44c2-a07a-ef38a4e1e9c4",
                                            network_id="131506a4-514f-4459-abb1-8fef43ca8fa2")
        DiffResult.objects.create(doc_id="85b542d4-8781-4465-939c-be76cf93acb4",
                                  filename="diff_exp_resultsCalcifiedVSNon-calcified_gu_core.txt",
                                  filepath="static/PlaqueMS/Carotid_Plaques_Vienna_Cohort/Statistics/diff_exp_resultsCalcifiedVSNon-calcified_gu_core.txt",
                                  network_id="6c770831-ee04-478a-bdc9-026a40f41d8c")
        Statistics.objects.create(doc_id="00003d8f-825a-4ef3-8780-0ac907234483", filename="ETFB_boxplot.png",
                                  filepath="../static/PlaqueMS/Carotid_Plaques_Athero_Express/statistics/hypertension_vs_no_hypertension/_bplots/ETFB_boxplot.png",
                                  doc_type="00", label="")

    def test_get_protein(self):
        res_one = Proteins.objects.get(uniprot_accession_id="B5LFX9")
        res_two = Proteins.objects.get(gene_name="HLA-G")

        self.assertEqual(res_one.protein_id, "00001933-50f8-410e-93c9-010d457bcb47")
        self.assertEqual(res_two.protein_id, "00001933-50f8-410e-93c9-010d457bcb47")

    def test_get_dataset(self):
        res = Datasets.objects.get(dataset_id="3542c8b3-224b-41ae-8598-a9eeed0f8eb0")
        self.assertEqual(res.name, "Coronary Arteries University of Virginia Cohort")

    def test_get_network(self):
        res = Networks.objects.get(network_id="6c770831-ee04-478a-bdc9-026a40f41d8c")
        self.assertEqual(res.filename,
                         "gu_core_filtered_directed_network.txt")
        self.assertEqual(res.filepath,
                         "static/PlaqueMS/Carotid_Plaques_Vienna_Cohort/GUHCL_TMT/Statistics/core/gu_core_filtered_directed_network.txt")

    def test_get_experiments_types(self):
        res = ExperimentsTypes.objects.get(experiment_id='d715589f-ea04-4c1f-b78e-1b0573e57214')
        self.assertEqual(res.path, "static/PlaqueMS/Carotid_Plaques_Vienna_Cohort/GUHCL_TMT/Statistics/core")

    def test_get_doc_and_experiment(self):
        res = DocAndExperiment.objects.get(id='00003b6f-6dbd-428e-a570-3676bb6f71d4')
        self.assertEqual(res.experiment_id, "ee7d7412-72dc-48e7-a2e5-d8815210fae5")

    def test_get_statistics(self):
        res = Statistics.objects.get(doc_id='00003d8f-825a-4ef3-8780-0ac907234483')
        self.assertEqual(res.filename, "ETFB_boxplot.png")
        self.assertEqual(res.filepath,
                         "../static/PlaqueMS/Carotid_Plaques_Athero_Express/statistics/hypertension_vs_no_hypertension/_bplots/ETFB_boxplot.png")
        self.assertEqual(res.doc_type, "00")

    def test_get_network_and_experiment(self):
        res = NetworkAndExperiment.objects.get(id='ff1a12cf-63ce-425c-8b01-d130d79e2258')
        self.assertEqual(res.network_id, "131506a4-514f-4459-abb1-8fef43ca8fa2")

    def test_get_diff_result(self):
        res = DiffResult.objects.get(doc_id='85b542d4-8781-4465-939c-be76cf93acb4')
        self.assertEqual(res.filepath,
                         "static/PlaqueMS/Carotid_Plaques_Vienna_Cohort/Statistics/diff_exp_resultsCalcifiedVSNon-calcified_gu_core.txt")
