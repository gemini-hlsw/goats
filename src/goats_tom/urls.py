from django.urls import include, path
from tom_alerts.views import BrokerQueryListView
from tom_common.api_router import SharedAPIRootRouter

from . import views

router = SharedAPIRootRouter()
router.register(r"dragonsruns", views.DRAGONSRunsViewSet)
router.register(r"dragonsfiles", views.DRAGONSFilesViewSet)
router.register(r"dragonsrecipes", views.DRAGONSRecipesViewSet)
router.register(r"dragonsreduce", views.DRAGONSReduceViewSet, basename="dragonsreduce")


# TODO: Add app_name and update paths and URL lookups.
# TODO: Make unified path formats.


urlpatterns = [
    path("api/", include(router.urls)),
    path(
        "targets/<int:pk>/delete/",
        views.GOATSTargetDeleteView.as_view(),
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
        views.GOATSObservationRecordDetailView.as_view(),
        name="observation-detail",
    ),
    path(
        "dataproducts/data/<int:pk>/delete/",
        views.GOATSDataProductDeleteView.as_view(),
        name="delete-dataproduct",
    ),
    path(
        "observations/<int:pk>/delete/",
        views.ObservationRecordDeleteView.as_view(),
        name="delete",
    ),
    path("brokers/list/", BrokerQueryListView.as_view(), name="list"),
    path("receive_query/", views.receive_query, name="receive_query"),
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
]
