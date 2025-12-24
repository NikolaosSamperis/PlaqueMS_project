# path tree
import os
import json
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.conf import settings
from Plaque_MS_app.models import Datasets, ExperimentsTypes, NetworkAndExperiment, Networks, DiffResult


class Node(dict):
    def __init__(self, id, text, tag=None, nodes=None):
        super().__init__()
        self.__dict__ = self  # allows dot-notation
        self.id = id
        self.text = text
        if tag:
            self.tag = tag
        self.nodes = list(nodes) if nodes is not None else []

    def add_child(self, child):
        self.nodes.append(child)


def build_valid_experiment_branch(exp):
    """
    Recursively builds a branch for an experiment only if the branch eventually ends with a network file
    whose filename ends with 'network.txt'. Once such a network file is found, the branch stops.
    Returns a Node if a valid branch exists, or None otherwise.
    """
    # Create the experiment node.
    exp_node = Node(exp.experiment_id, exp.pathname, tag="experiment")

    # Check if this experiment has an associated network file.
    try:
        net_relation = NetworkAndExperiment.objects.get(experiment_id=exp.experiment_id)
        network = Networks.objects.get(network_id=net_relation.network_id)
        if network.filename.endswith("network"):
            # Found a valid network file, so attach it and stop further recursion.
            network_node = Node(network.network_id, network.filename, tag="network_file")
            exp_node.add_child(network_node)
            return exp_node
    except NetworkAndExperiment.DoesNotExist:
        pass

    # If no valid network file is found here, check its child experiments.
    child_experiments = ExperimentsTypes.objects.filter(parent_id=exp.experiment_id)
    valid_children = []
    for child_exp in child_experiments:
        child_branch = build_valid_experiment_branch(child_exp)
        if child_branch is not None:
            valid_children.append(child_branch)

    # Only include this experiment node if at least one valid branch exists.
    if valid_children:
        exp_node.nodes = valid_children
        return exp_node

    # If no valid network file and no valid children, return None to exclude this branch.
    return None


def initialize_tree():
    """
    Build the tree for only the 'Carotid Plaques Vienna Cohort' dataset.
    Only include branches (experiment paths) that eventually end with a network file
    whose filename ends with 'network.txt'.
    """
    root_node = Node("root", "root", tag="root")

    # Filter for the specific cohort.
    datasets = Datasets.objects.filter(name="Carotid Plaques Vienna Cohort")
    for dataset in datasets:
        dataset_node = Node(dataset.dataset_id, dataset.name, tag="dataset")
        root_node.add_child(dataset_node)
        # Get top-level experiments (assuming top-level experiments have parent_id as an empty string)
        experiments = ExperimentsTypes.objects.filter(dataset_id=dataset.dataset_id, parent_id='')
        for exp in experiments:
            branch = build_valid_experiment_branch(exp)
            if branch is not None:
                dataset_node.add_child(branch)
    return root_node


def path_to_dict(request):
    """
    View to generate the JSON tree and save it to the base directory.
    """
    tree = initialize_tree()
    json_str = json.dumps(tree, indent=2)

    # Save the JSON file in the base directory
    json_file_path = os.path.join(str(settings.BASE_DIR), "network_tree.json")
    with open(json_file_path, "w", encoding="utf-8") as f:
        f.write(json_str)

    return HttpResponse("Network tree JSON generated successfully.")


@api_view(['GET'])
def get_json_file(request):
    """
    Return the generated 'network_tree.json' file from the base directory as JSON.
    """
    json_file_path = os.path.join(str(settings.BASE_DIR), "network_tree.json")
    with open(json_file_path, "r", encoding="utf-8") as f:
        content = json.load(f)
    return Response({'data': content})


@api_view(['GET'])
def get_diff(request):
    """
    Returns a list of diff results for a given network.
    Expects a GET parameter 'network_id'.
    """
    network_id = request.GET.get("network_id", "")
    try:
        network = Networks.objects.get(network_id=network_id)
    except Networks.DoesNotExist:
        return Response({'error': 'Network not found.'}, status=404)

    # Retrieve diff results that match the given network_id
    doc_list = DiffResult.objects.values('doc_id', 'filename', 'filepath').filter(network_id=network.network_id)
    return Response({'data': list(doc_list)})







