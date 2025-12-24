"""
URL configuration for testdj project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Tweet API",
        default_version='v1',
        description="Welcome to the world of Tweet",
        terms_of_service="https://www.tweet.org",
        contact=openapi.Contact(email="demo@tweet.org"),
        license=openapi.License(name="Awesome IP"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

from django.contrib import admin
from django.urls import path, include
from Plaque_MS_app import protein_views, cyviews, plot_views, pathTree, insert_views, networkTree, plaquery_views, auth_views, home_views, calc_pred_views, syntax_score_views

urlpatterns = [
    path('', home_views.home_view, name='home'),  # Root path for Home.html
    path('admin/', admin.site.urls),
    # Login endpoints
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('register/', auth_views.register_view, name='register'),
    path('dashboard/', auth_views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/approve-user/<int:user_id>/', auth_views.approve_user, name='approve_user'),
    path('dashboard/deactivate-user/<int:user_id>/', auth_views.deactivate_user, name='deactivate_user'),
    path('dashboard/activate-user/<int:user_id>/', auth_views.activate_user, name='activate_user'),
    path('dashboard/delete-user/<int:user_id>/', auth_views.delete_user, name='delete_user'),
    # Other endpoints
    path('proteins/', protein_views.get_protein_list, name="proteins"),
    path('insert_proteins/', insert_views.insert_protein_data),
    path('insert_one/', insert_views.insert_one),
    path('insert_two/', insert_views.insert_two),
    path('insert_three/', insert_views.insert_three),
    path('insert_diff/', insert_views.insert_diff),
    path('insert_dataset/', insert_views.insert_dataset),
    path('tree/', pathTree.path_to_dict),
    path('get_json/', pathTree.get_json_file),
    path('network_json/', networkTree.path_to_dict),
    path('get_network_json/', networkTree.get_json_file),
    path('get_diff/', networkTree.get_diff),
    path('plot/', plot_views.get_pic_list, name="plot"),
    path('tryc/', cyviews.try_curl, name="cy"),
    path('networks/', cyviews.create_network),
    path('mcl/', cyviews.do_mcl),
    path('color/', cyviews.do_coloring),
    path('get_gene_list/', cyviews.get_gene_list),
    path('sidebar/', plot_views.get_child),
    # PlaQuery endpoints
    path('protein-abundance/', plaquery_views.plaquery_view, name='protein-abundance'),
    path('protein-ids/', plaquery_views.get_protein_ids, name='get_protein_ids'),
    path('abundance-data/', plaquery_views.get_abundance_data, name='get_abundance_data'),
    # Calcification predictor
    path('calc-predict/', calc_pred_views.calc_prediction_view, name='calc_predict'),
    path("calc-predict/upload/", calc_pred_views.calc_prediction_upload_view,  name="calc_upload"),
    path("calc-predict/filter/", calc_pred_views.calc_prediction_filter_view,  name="calc_filter"),
    # Syntax score predictor
    path('syntax-predict/', syntax_score_views.syntax_prediction_view, name='syntax_predict'),
    path("syntax-predict/upload/", syntax_score_views.syntax_prediction_upload_view,  name="syntax_upload"),
    path("syntax-predict/filter/", syntax_score_views.syntax_prediction_filter_view,  name="syntax_filter")
]


