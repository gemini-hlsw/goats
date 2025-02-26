from django.urls import include, path
from tom_alerts.views import BrokerQueryListView
from tom_common.api_router import SharedAPIRootRouter

from . import api_views, views

router = SharedAPIRootRouter()
router.register(
    r"reduceddatums", api_views.ReducedDatumViewSet, basename="reduceddatums"
)
router.register(r"dragonsruns", api_views.DRAGONSRunsViewSet, basename="dragonsruns")
router.register(r"dragonsfiles", api_views.DRAGONSFilesViewSet, basename="dragonsfiles")
router.register(
    r"dragonsrecipes", api_views.DRAGONSRecipesViewSet, basename="dragonsrecipes"
)
router.register(r"dragonsreduce", api_views.DRAGONSReduceViewSet)
router.register(r"baserecipes", api_views.BaseRecipeViewSet, basename="baserecipes")
router.register(
    r"recipesmodule", api_views.RecipesModuleViewSet, basename="recipesmodule"
)
router.register(r"dragonscaldb", api_views.DRAGONSCaldbViewSet, basename="dragonscaldb")
router.register(
    r"dragonsprocessedfiles",
    api_views.DRAGONSProcessedFilesViewSet,
    basename="dragonsprocessedfiles",
)
router.register(
    r"dragonsdataproducts",
    api_views.DataProductsViewSet,
    basename="dragonsdataproducts",
)
router.register(r"dragonsdata", api_views.DRAGONSDataViewSet, basename="dragonsdata")
router.register(r"runprocessor", api_views.RunProcessorViewSet, basename="runprocessor")
router.register(
    r"antares2goats", api_views.Antares2GoatsViewSet, basename="antares2goats"
)
router.register(r"astrodatalab", api_views.AstroDatalabViewSet, basename="astrodatalab")
# TODO: Add app_name and update paths and URL lookups.
# TODO: Make unified path formats.

urlpatterns = [
    path("astro-data-lab/", views.AstroDatalabView.as_view(), name="astro-data-lab"),
    path("api/", include(router.urls)),
    path(
        "targets/<int:pk>/delete/",
        views.TargetDeleteView.as_view(),
        name="target-delete",
    ),
    path(
        "alerts/query/<int:pk>/update-name",
        views.update_brokerquery_name,
        name="update-brokerquery-name",
    ),
    path(
        "observations/<int:pk>/delete-data-products/",
        views.DeleteObservationDataProductsView.as_view(),
        name="delete-observation-data-products",
    ),
    path(
        "observations/<int:pk>/",
        views.ObservationRecordDetailView.as_view(),
        name="observation-detail",
    ),
    path(
        "dataproducts/data/<int:pk>/delete/",
        views.DataProductDeleteView.as_view(),
        name="delete-dataproduct",
    ),
    path(
        "observations/<int:pk>/delete/",
        views.ObservationRecordDeleteView.as_view(),
        name="delete",
    ),
    path("brokers/list/", BrokerQueryListView.as_view(), name="list"),
    path(
        "users/<int:pk>/generate_token/",
        views.UserGenerateTokenView.as_view(),
        name="user-generate-token",
    ),
    path(
        "users/<int:pk>/goa_login/",
        views.GOALoginView.as_view(),
        name="user-goa-login",
    ),
    path(
        "users/<int:pk>/astro-data-lab/",
        views.AstroDatalabLoginView.as_view(),
        name="user-astro-data-lab-login",
    ),
    path("goa_query/<int:pk>/", views.GOAQueryFormView.as_view(), name="goa_query"),
    path("api/ongoing-tasks/", views.ongoing_tasks, name="ongoing_tasks"),
    path("recent-downloads/", views.recent_downloads, name="recent_downloads"),
    path(
        "users/<int:pk>/manage-keys/",
        views.ManageKeysView.as_view(),
        name="manage-keys",
    ),
    path(
        "users/<int:user_pk>/user-key/<int:pk>/delete/",
        views.delete_key,
        {"key_type": "user_key"},
        name="delete-user-key",
    ),
    path(
        "users/<int:user_pk>/program-key/<int:pk>/delete/",
        views.delete_key,
        {"key_type": "program_key"},
        name="delete-program-key",
    ),
    path(
        "users/<int:user_pk>/create-user-key/",
        views.create_key,
        {"key_type": "user_key"},
        name="create-user-key",
    ),
    path(
        "users/<int:user_pk>/create-program-key/",
        views.create_key,
        {"key_type": "program_key"},
        name="create-program-key",
    ),
    path(
        "users/<int:user_pk>/user-key/<int:pk>/activate/",
        views.activate_user_key,
        name="activate-user-key",
    ),
    path("observations/<int:pk>/dragons/", views.DRAGONSView.as_view(), name="dragons"),
    path(
        "dataproducts/data/upload/",
        views.DataProductUploadView.as_view(),
        name="upload",
    ),
]
