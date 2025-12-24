import os
import json
import subprocess
import time
from django.conf import settings
from django.http import Http404
from django.shortcuts import render, HttpResponse
import urllib3
import pandas as pd
import py4cytoscape as p4c
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import requests
from rest_framework.response import Response
from Plaque_MS_app.models import Networks, Statistics, DiffResult

def try_curl(request):
    return render(request, "network.html")

def wait_for_cytoscape_startup(max_attempts=5, wait_seconds=20):
    """
    Pings Cytoscape until it responds (or until max_attempts are reached)
    """
    for attempt in range(max_attempts):
        try:
            p4c.cytoscape_ping()
            return True
        except Exception:
            time.sleep(wait_seconds)
    return False

@csrf_exempt
@api_view(['GET', 'POST'])
def create_network(request):
    """
    Creates the network in Cytoscape from the file (and applies filtering if provided)
    but does NOT perform MCL clustering.
    """
    try:
        # 1) Ensure Cytoscape is running.
        try:
            p4c.cytoscape_ping()
        except Exception:
            subprocess.Popen([r"C:\Program Files\Cytoscape_v3.10.3\Cytoscape.exe"])
            if not wait_for_cytoscape_startup():
                return Response({'error': 'Cytoscape is still starting up, please wait and try again.'}, status=500)

        # 2) Load the network file and filter by selected nodes if provided.
        network_id = request.GET.get("network_id", "")
        network = Networks.objects.get(network_id=network_id)
        # prepend the static folder to the stored relative path
        file_path = os.path.join(settings.BASE_DIR, 'static', network.filepath)
        network_data = pd.read_table(file_path)

        node_list_str = request.GET.get("node_list", "")
        if node_list_str:
            selected_nodes = [x.strip() for x in node_list_str.split(',') if x.strip()]
            network_data = network_data[
                network_data["Regulator"].isin(selected_nodes) &
                network_data["Target"].isin(selected_nodes)
            ]

        if network_data.empty:
            return Response({"error": "No interactions found among the selected genes."}, status=400)

        # 3) Create the network in Cytoscape.
        edge_data = {
            'source': network_data["Regulator"],
            'target': network_data["Target"],
            'MI': network_data["MI"],
            'pvalue': network_data["pvalue"],
            'directionality': network_data["directionality"]
        }
        edges_df = pd.DataFrame(data=edge_data, columns=['source', 'target', 'MI', 'pvalue', 'directionality'])
        edges_df['directionality-positive'] = edges_df.apply(lambda a: 1 if a['directionality'] > 0 else 0, axis=1)

        p4c.create_network_from_data_frames(edges=edges_df, title=network.filename, collection=network.filename)

        # 4) Retrieve the current network elements (without clustering).
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        json_data = {'network': 'current'}
        resp = requests.post('http://localhost:1234/v1/commands/network/get', headers=headers, json=json_data)
        suid = resp.json()["data"]["SUID"]

        http = urllib3.PoolManager()
        r = http.request('GET', f'http://localhost:1234/v1/networks/{suid}')
        jsonData = r.json()
        nodes = jsonData["elements"]["nodes"]
        edges = jsonData["elements"]["edges"]

        # Ensure each node has an mclCluster attribute for consistency.
        for node in nodes:
            data = node.get("data", {})
            if "mclCluster" not in data:
                data["mclCluster"] = "NA"

        clusters = set(node["data"]["mclCluster"] for node in nodes)
        unique_clusters = clusters - {"NA"}
        if len(unique_clusters) < 2:
            for node in nodes:
                data = node.get("data", {})
                if "mclCluster" in data:
                    del data["mclCluster"]
        numClusters = len(unique_clusters)

        # 5) Retrieve the default style.
        r_style = http.request('GET', 'http://localhost:1234/v1/styles/default.json')
        json_style = r_style.json()
        style = json_style[0]["style"]

        return Response({'nodes': nodes, 'edges': edges, 'style': style, 'numClusters': numClusters})
    except Exception as e:
        print("Error in create_network:", e)
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def do_mcl(request):
    """
    Performs MCL clustering on the current network in Cytoscape.
    This function assumes that the network has already been loaded.
    """
    try:
        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        json_data = {'network': 'current'}
        pre_resp = requests.post('http://localhost:1234/v1/commands/network/get', headers=headers, json=json_data)
        old_suid = pre_resp.json()["data"]["SUID"]

        json_mcl = {
            "adjustLoops": "true",
            "attribute": "pvalue",
            "clusterAttribute": "mclCluster",
            "clusteringThresh": "1e-15",
            "createGroups": "false",
            "createNewClusteredNetwork": "true",
            "edgeWeighter": "1-value",
            "forceDecliningResidual": "true",
            "inflation_parameter": "2.5",
            "iterations": "16",
            "maxResidual": "0.001",
            "selectedOnly": "false",
            "undirectedEdges": "true"
        }

        res = requests.post('http://localhost:1234/v1/commands/cluster/mcl', headers=headers, json=json_mcl)
        if "Specified factory is null or has wrong DataCategory (SESSION)" in res.text:
            return Response({
                'error': (
                    "Please enable New clustered network creation in the Cytoscape Desktop app to utilize this feature.\n"
                    "1. Install clusterMaker2 if not installed.\n"
                    "2. Navigate: Apps > clusterMaker2 > MCL Cluster > Create new clustered network."
                )
            }, status=400)

        post_resp = requests.post('http://localhost:1234/v1/commands/network/get', headers=headers, json=json_data)
        new_suid = post_resp.json()["data"]["SUID"]

        if new_suid == old_suid:
            return Response({
                'error': (
                    "Please enable \"New clustered network creation\" in the Cytoscape Desktop app to utilize this feature.\n"
                    "1. Install clusterMaker2 if not installed.\n"
                    "2. Navigate: Apps > clusterMaker2 > MCL Cluster > Create new clustered network."
                )
            }, status=400)

        http = urllib3.PoolManager()
        r = http.request('GET', f'http://localhost:1234/v1/networks/{new_suid}')
        jsonData = r.json()
        nodes = jsonData["elements"]["nodes"]
        edges = jsonData["elements"]["edges"]

        for node in nodes:
            data = node.get("data", {})
            if "mclCluster" not in data:
                data["mclCluster"] = "NA"

        clusters = set(node["data"]["mclCluster"] for node in nodes)
        unique_clusters = clusters - {"NA"}

        if len(unique_clusters) < 2:
            for node in nodes:
                data = node.get("data", {})
                if "mclCluster" in data:
                    del data["mclCluster"]

        numClusters = len(unique_clusters)

        r_style = http.request('GET', 'http://localhost:1234/v1/styles/default.json')
        json_style = r_style.json()
        style = json_style[0]["style"]

        return Response({'nodes': nodes, 'edges': edges, 'style': style, 'numClusters': numClusters})
    except Exception as e:
        print("Error in do_mcl:", e)
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_gene_list(request):
    """
    Returns the list of unique gene names (from both 'Regulator' and 'Target') for a given network.
    """
    try:
        network_id = request.GET.get("network_id", "")
        network = Networks.objects.get(network_id=network_id)
        # prepend the static folder to the stored relative path
        file_path = os.path.join(settings.BASE_DIR, 'static', network.filepath)
        network_data = pd.read_table(file_path)
        genes = list(set(network_data["Regulator"]).union(set(network_data["Target"])))
        genes.sort()
        return Response({'genes': genes})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def do_coloring(request):
    """
    Applies the coloring scheme to the current network based on differential expression data.
    """
    try:
        doc_id = request.GET.get("doc_id", "")
        doc = DiffResult.objects.get(doc_id=doc_id)
        # prepend the static folder to the stored relative path
        full_path = os.path.join(settings.BASE_DIR, 'static', doc.filepath)
        network_data = pd.read_table(full_path, index_col=0)

        df_dict = {
            'logFC':   network_data["logFC"],
            'CI.L':    network_data["CI.L"],
            'CI.R':    network_data["CI.R"],
            'AveExpr': network_data["AveExpr"],
            't':       network_data["t"],
            'P.Value': network_data["P.Value"],
            'adj.P.Val': network_data["adj.P.Val"],
            'B':       network_data["B"]
        }
        df = pd.DataFrame(data=df_dict, columns=['logFC', 'CI.L', 'CI.R', 'AveExpr', 't', 'P.Value', 'adj.P.Val', 'B'])
        p4c.load_table_data(df)

        # Compute extreme logFC values for color mapping.
        min_value = df['logFC'].min()
        max_value = df['logFC'].max()
        abs_min = abs(min_value)
        abs_max = abs(max_value)
        log_value = abs_min if abs_min >= abs_max else abs_max

        json_color = [
            {
                "mappingType": "continuous",
                "mappingColumn": "logFC",
                "mappingColumnType": "Double",
                "visualProperty": "NODE_FILL_COLOR",
                "points": [
                    {
                        "value": -log_value,
                        "lesser": "#2166AC",
                        "equal": "#4393C3",
                        "greater": "#4393C3"
                    },
                    {
                        "value": 0.0,
                        "lesser": "#F7F7F7",
                        "equal": "#F7F7F7",
                        "greater": "#F7F7F7"
                    },
                    {
                        "value": log_value,
                        "lesser": "#D6604D",
                        "equal": "#D6604D",
                        "greater": "#B2182B"
                    }
                ]
            },
            {
                "mappingType": "passthrough",
                "mappingColumn": "MI",
                "mappingColumnType": "Double",
                "visualProperty": "EDGE_WIDTH"
            },
            {
                "mappingType": "discrete",
                "mappingColumn": "directionality-positive",
                "mappingColumnType": "Integer",
                "visualProperty": "EDGE_TARGET_ARROW_SHAPE",
                "map": [
                    {"key": "0", "value": "T"},
                    {"key": "1", "value": "ARROW"}
                ]
            }
        ]

        headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        color_res = requests.post(
            'http://localhost:1234/v1/styles/Sample1/mappings',
            headers=headers,
            json=json_color
        )
        print("Sample1 style mapping response:", color_res.text)

        json_data = {'network': 'current'}
        response = requests.post('http://localhost:1234/v1/commands/network/get', headers=headers, json=json_data)
        suid = response.json()["data"]["SUID"]

        http = urllib3.PoolManager()
        apply_style_resp = http.request('GET', f'http://localhost:1234/v1/apply/styles/Sample1/{suid}')
        print("Apply style response status:", apply_style_resp.status)

        r = http.request('GET', f'http://localhost:1234/v1/networks/{suid}')
        jsonData = r.json()
        nodes = jsonData["elements"]["nodes"]
        edges = jsonData["elements"]["edges"]

        for node in nodes:
            data = node.get("data", {})
            if "mclCluster" not in data:
                data["mclCluster"] = "NA"

        clusters = set(node["data"]["mclCluster"] for node in nodes)
        unique_clusters = clusters - {"NA"}

        if len(unique_clusters) < 2:
            for node in nodes:
                data = node.get("data", {})
                if "mclCluster" in data:
                    del data["mclCluster"]
        else:
            for node in nodes:
                data = node.get("data", {})
                if "mclCluster" not in data:
                    data["mclCluster"] = "NA"

        numClusters = len(unique_clusters)

        r_style = http.request('GET', 'http://localhost:1234/v1/styles/Sample1.json')
        json_style = r_style.json()
        style = json_style[0]["style"]

        return Response({'nodes': nodes, 'edges': edges, 'style': style, 'numClusters': numClusters})
    except Exception as e:
        print("Error in do_coloring:", e)
        return Response({'error': str(e)}, status=500)
