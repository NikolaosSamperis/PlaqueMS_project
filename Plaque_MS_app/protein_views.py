from django.http import HttpResponse, Http404
from django.shortcuts import render

from Plaque_MS_app.models import Proteins
from django.db.models import Q

import xlwt
from io import BytesIO

"""
get proteins
"""


def get_protein_list(request):
    # get keywords
    uniprotkb_id = request.GET.get("uniprotkb_id", "")
    gene_name = request.GET.get("gene_name", "")
    page_number = request.GET.get("page_number", "")

    if page_number:
        current_page = int(page_number)
    else:
        current_page = 1
    page_size = 10

    query = Proteins.objects

    if gene_name and uniprotkb_id:
        name_search_list = gene_name.split(",")
        id_search_list = uniprotkb_id.split(",")
        query = query.filter(Q(uniprot_accession_id__in=id_search_list) | Q(gene_name__in=name_search_list))

    elif uniprotkb_id and gene_name == '':
        id_search_list = uniprotkb_id.split(",")
        query = query.filter(uniprot_accession_id__in=id_search_list)

    elif uniprotkb_id == '' and gene_name:
        name_search_list = gene_name.split(",")
        query = query.filter(gene_name__in=name_search_list)

    start_row = (current_page - 1) * page_size
    end_row = current_page * page_size

    result = query.values('protein_id', 'uniprot_accession_id', 'uniprotkb_id', 'gene_name')[start_row:end_row]

    counts = query.count()

    total_count = 0
    if counts % page_size == 0:
        total_count = counts // page_size
    else:
        total_count = counts // page_size + 1

    if current_page > 1:
        has_previous = True
        previous_page = current_page - 1
    else:
        has_previous = False
        previous_page = current_page

    if current_page < total_count:
        has_next = True
        next_page = current_page + 1
    else:
        has_next = False
        next_page = current_page
    context = {
        "result": result,
        "page": current_page,
        "gene_name": gene_name,
        "uniprotkb_id": uniprotkb_id,
        "total_count": total_count,
        "has_previous": has_previous,
        "has_next": has_next,
        "previous_page": previous_page,
        "next_page": next_page,
    }
    return render(request, "protein.html", context)
