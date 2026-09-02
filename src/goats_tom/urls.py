from django.urls import include, path
from tom_alerts.views import BrokerQueryListView
from tom_common.api_router import SharedAPIRootRouter
from tom_tns.urls import urlpatterns as tom_tns_urls

from . import api_views, views

router = SharedAPIRootRouter()
# Claims the `dataproducts` basename before `tom_dataproducts.urls` can.
# `SharedAPIRootRouter` declines a second registration of a basename it
# already holds, and this module is included before `tom_common.urls` (which
# is what imports every app's urls.py), so this registration wins and
# upstream's is refused with a log line.
#
# The point is the permission check: upstream's viewset exposes DELETE with
# no object-level check, which is why the superuser delete ban had no effect
# on the live instance. See `GOATSDataProductViewSet`. Registered first, and
# not down with the rest, because order is the whole mechanism here --
# `tests/goats_tom/test_api_delete_scoping.py` asserts the route resolves to
# the GOATS class rather than trusting that it does.
router.register(
    r"dataproducts", api_views.GOATSDataProductViewSet, basename="dataproducts"
)
router.register(r"gpp", api_views.GPPViewSet, basename="gpp")
router.register(r"gpp/programs", api_views.GPPProgramViewSet, basename="gppprograms")
router.register(
    r"gpp/observations", api_views.GPPObservationViewSet, basename="gppobservations"
)
# Not nested under "gpp/observations": that viewset's detail route matches any
# single path segment and would swallow the finder chart list route.
router.register(
    r"gpp/finder-charts",
    api_views.GPPFinderChartViewSet,
    basename="gppfindercharts",
)
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
router.register(r"targets", api_views.TargetViewSet, basename="targets")
router.register(r"astrodatalab", api_views.AstroDatalabViewSet, basename="astrodatalab")
# Retagging a data product's type. Written and exported but never routed,
# so `static/js/dataproduct_type.js` PATCHed a URL that did not resolve and
# nobody could change a file type, including on their own files.
router.register(
    r"dataproducttype",
    api_views.DataProductTypeViewSet,
    basename="dataproducttype",
)
router.register(r"status", api_views.StatusViewSet, basename="status")
router.register(r"system", api_views.SystemViewSet, basename="system")
# TODO: Add app_name and update paths and URL lookups.
# TODO: Make unified path formats.

urlpatterns = [
    path("status/", views.status_view, name="status"),
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
    # Overrides closing TOM's group permission bypasses -- see
    # `goats_tom.views.groups`. Declared before the tom_* includes so these
    # win.
    path(
        "targets/targetgrouping/<int:pk>/delete/",
        views.GOATSTargetGroupingDeleteView.as_view(),
        name="goats-targetgrouping-delete",
    ),
    path(
        "observations/groups/<int:pk>/delete/",
        views.GOATSObservationGroupDeleteView.as_view(),
        name="goats-observationgroup-delete",
    ),
    path(
        "dataproducts/data/",
        views.GOATSDataProductListView.as_view(),
        name="goats-dataproduct-list",
    ),
    path(
        # `<path:name>` rather than `<str:name>`: a storage name contains
        # separators -- `users/<username>/goats/<target>/...` -- and `str`
        # stops at the first one.
        #
        # Answers what `VOSpaceStorage.url` returns. Nothing routes here on
        # a desktop install, where `FileSystemStorage` serves files from
        # MEDIA_URL directly.
        "dataproducts/stream/<path:name>",
        views.DataProductStreamView.as_view(),
        name="dataproduct-stream",
    ),
    path(
        "dataproducts/data/group/list/",
        views.GOATSDataProductGroupListView.as_view(),
        name="goats-dataproduct-group-list",
    ),
    path(
        "dataproducts/data/group/create/",
        views.GOATSDataProductGroupCreateView.as_view(),
        name="goats-dataproduct-group-create",
    ),
    path(
        "dataproducts/data/group/add/",
        views.GOATSAddProductToGroupView.as_view(),
        name="goats-dataproduct-group-add",
    ),
    path(
        "dataproducts/data/group/<int:pk>/",
        views.GOATSDataProductGroupDetailView.as_view(),
        name="goats-dataproduct-group-detail",
    ),
    path(
        "dataproducts/data/group/<int:pk>/delete/",
        views.GOATSDataProductGroupDeleteView.as_view(),
        name="goats-dataproduct-group-delete",
    ),
    path(
        "observations/list/",
        views.GOATSObservationListView.as_view(),
        name="goats-observation-list",
    ),
    path(
        "observations/add/",
        views.GOATSAddExistingObservationView.as_view(),
        name="add-existing-observation",
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
    path(
        "users/<int:pk>/lco/",
        views.LCOLoginView.as_view(),
        name="user-lco-login",
    ),
    path(
        "users/<int:pk>/tns/",
        views.TNSLoginView.as_view(),
        name="user-tns-login",
    ),
    path("users/<int:pk>/gpp/", views.GPPLoginView.as_view(), name="user-gpp-login"),
    path(
        "users/<int:pk>/antares-kafka/",
        views.AntaresKafkaLoginView.as_view(),
        name="user-antares-kafka-login",
    ),
    path(
        "users/<int:pk>/rsp-tap/",
        views.RSPTapLoginView.as_view(),
        name="user-rsp-tap-login",
    ),
    path("goa_query/<int:pk>/", views.GOAQueryFormView.as_view(), name="goa_query"),
    path(
        "observations/<int:pk>/goa-archive/",
        views.GOAArchiveRedirectView.as_view(),
        name="goa-archive-redirect",
    ),
    path("api/ongoing-tasks/", views.ongoing_tasks, name="ongoing_tasks"),
    path("recent-downloads/", views.recent_downloads, name="recent_downloads"),
    path("observations/<int:pk>/dragons/", views.DRAGONSView.as_view(), name="dragons"),
    path(
        "dataproducts/data/upload/",
        views.DataProductUploadView.as_view(),
        name="upload",
    ),
    path(
        "observations/template/<str:facility>/create/",
        views.ObservationTemplateCreateView.as_view(),
        name="template-create",
    ),
    path("targets/<int:pk>/", views.TargetDetailView.as_view(), name="detail"),
    # Scopes the "Add/Remove from grouping" select and the target group
    # filter, both of which listed every PI's target groups. Declared
    # before the tom_targets include so this wins.
    path("targets/", views.GOATSTargetListView.as_view(), name="goats-target-list"),
    path("tns/", include(tom_tns_urls)),
    path(
        "targets/<int:target_id>/refresh-antares/",
        views.RefreshAntaresPhotometryView.as_view(),
        name="refresh_antares_photometry",
    ),
    path(
        "antares/loci/",
        views.antares_locus_dashboard,
        name="antares-locus-dashboard",
    ),
    path(
        "antares/loci/table/",
        views.antares_locus_table,
        name="antares-locus-table",
    ),
    path(
        "observations/<int:pk>/share/",
        views.share_observation_record,
        name="share-observation-record",
    ),
    path(
        "antares/loci/remote-jobs/",
        views.antares_remote_jobs,
        name="antares-remote-jobs",
    ),
    path(
        "antares/loci/save/",
        views.antares_locus_save_targets,
        name="antares-locus-save-targets",
    ),
    path(
        "antares/loci/saved-status/",
        views.antares_locus_saved_status,
        name="antares-locus-saved-status",
    ),
    path(
        "antares/loci/clear/",
        views.antares_locus_clear,
        name="antares-locus-clear",
    ),
    path(
        "antares/loci/status/",
        views.antares_dashboard_status,
        name="antares-dashboard-status",
    ),
    path(
        "register/",
        views.register,
        name="register",
    ),
    path(
        "users/requests/",
        views.registration_requests,
        name="registration-requests",
    ),
    path(
        "users/requests/<int:pk>/decide/",
        views.decide_registration_request,
        name="decide-registration-request",
    ),
    # Shadow tom_common's user create/update so the group picker hides
    # automatically-managed groups. goats_tom.urls is included before
    # tom_common.urls (see the project urls.py), so these win.
    path(
        "users/create/",
        views.GOATSUserCreateView.as_view(),
        name="user-create",
    ),
    path(
        "users/<int:pk>/update/",
        views.GOATSUserUpdateView.as_view(),
        name="user-update",
    ),
    path(
        "antares/access/request/",
        views.antares_request_access,
        name="antares-request-access",
    ),
    path(
        "antares/access/manage/",
        views.antares_manage_access,
        name="antares-manage-access",
    ),
    path(
        "antares/access/requests/<int:pk>/decide/",
        views.antares_decide_join_request,
        name="antares-decide-join-request",
    ),
    path(
        "antares/access/members/<int:pk>/revoke/",
        views.antares_revoke_membership,
        name="antares-revoke-membership",
    ),
    path(
        "antares/stream/subscribe/",
        views.antares_stream_subscribe,
        name="antares-stream-subscribe",
    ),
    path(
        "antares/stream/status/",
        views.antares_stream_status,
        name="antares-stream-status",
    ),
    path(
        "antares/stream/topics/",
        views.antares_available_topics,
        name="antares-available-topics",
    ),
]
