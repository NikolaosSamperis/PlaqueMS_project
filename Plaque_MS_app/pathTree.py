# path tree
import os
import json
from django.http import HttpResponse
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from Plaque_MS_app.models import Datasets, ExperimentsTypes


class Node(dict):
    # initialize a node
    def __init__(self, id, text, nodes=None):
        super().__init__()
        self.__dict__ = self
        self.id = id
        self.text = text
        self.nodes = list(nodes) if nodes is not None else []

    def add_child(self, *child):
        self.nodes += child

    def show(self, layer):
        print("--" * layer + self.text)
        for c in self.nodes:
            c.show(layer + 1)


def initialize_tree():
    rootNode = Node("root", "root")
    dataset_list = Datasets.objects.all()
    for dataset in dataset_list:
        first_node = Node(dataset.dataset_id, dataset.name)
        rootNode.add_child(first_node)
        # add second layer
        sql = (
            "select experiment_id, pathname, path_type from experiments_types "
            "where parent_id='' and dataset_id = '" + dataset.dataset_id + "'"
        )
        second_list = ExperimentsTypes.objects.raw(sql)
        add_child_node(second_list, first_node)
    return rootNode


# recursively add node
def add_child_node(node_list, node):
    for second in node_list:
        second_node = Node(second.experiment_id, second.pathname)
        node.add_child(second_node)
        if second.path_type == "00":
            sql = (
                "select experiment_id, pathname, path_type from experiments_types "
                "where parent_id='" + second_node.id + "'"
            )
            second_list = ExperimentsTypes.objects.raw(sql)
            add_child_node(second_list, second_node)


@staticmethod
def from_dict(dict_):
    """ Recursively (re)construct TreeNode-based tree from dictionary. """
    node = Node(dict_['id'], dict_['text'], dict_['nodes'])
    node.children = list(map(Node.from_dict, node.children))
    return node


def path_to_dict(request):
    tree = initialize_tree()
    json_str = json.dumps(tree, indent=2)
    # Build full path to the JSON file in your BASE_DIR
    json_file_path = os.path.join(str(settings.BASE_DIR), "json_tree.json")
    with open(json_file_path, "w", encoding="utf-8") as f:
        f.write(json_str)
    return HttpResponse("success")


@api_view(['GET'])
def get_json_file(request):
    json_file_path = os.path.join(str(settings.BASE_DIR), "json_tree.json")
    with open(json_file_path, "r", encoding="utf-8") as f:
        content = json.load(f)
    return Response({'data': content})



