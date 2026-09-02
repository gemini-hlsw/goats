from goats_tom.views.add_existing_observation import GOATSAddExistingObservationView
from goats_tom.views.groups import (
    GOATSAddProductToGroupView,
    GOATSDataProductGroupCreateView,
    GOATSDataProductGroupDeleteView,
    GOATSDataProductGroupDetailView,
    GOATSDataProductGroupListView,
    GOATSObservationGroupDeleteView,
    GOATSObservationListView,
    GOATSTargetGroupingDeleteView,
)
from goats_tom.views.antares import RefreshAntaresPhotometryView
from goats_tom.views.sharing import share_observation_record
from goats_tom.views.registration import (
    decide_registration_request,
    register,
    registration_requests,
)
from goats_tom.views.user import GOATSUserCreateView, GOATSUserUpdateView
from goats_tom.views.antares_access_management import (
    antares_decide_join_request,
    antares_manage_access,
    antares_request_access,
    antares_revoke_membership,
)
from goats_tom.views.antares_locus_dashboard import (
    antares_dashboard_status,
    antares_locus_clear,
    antares_locus_dashboard,
    antares_locus_save_targets,
    antares_locus_saved_status,
    antares_locus_table,
    antares_remote_jobs,
)
from goats_tom.views.antares_stream_subscribe import (
    antares_available_topics,
    antares_stream_status,
    antares_stream_subscribe,
)
from goats_tom.views.astro_datalab import AstroDatalabView
from goats_tom.views.brokerquery_name import update_brokerquery_name
from goats_tom.views.dataproduct_delete import DataProductDeleteView
from goats_tom.views.dataproduct_stream import DataProductStreamView
from goats_tom.views.dataproduct_upload import DataProductUploadView
from goats_tom.views.delete_observation_dataproducts import (
    DeleteObservationDataProductsView,
)
from goats_tom.views.downloads import recent_downloads
from goats_tom.views.dragons import DRAGONSView
from goats_tom.views.goa_archive_redirect import GOAArchiveRedirectView
from goats_tom.views.goa_query_form import GOAQueryFormView
from goats_tom.views.logins import (
    AntaresKafkaLoginView,
    AstroDatalabLoginView,
    GOALoginView,
    GPPLoginView,
    LCOLoginView,
    RSPTapLoginView,
    TNSLoginView,
)
from goats_tom.views.observation_record_delete import ObservationRecordDeleteView
from goats_tom.views.observation_record_detail import ObservationRecordDetailView
from goats_tom.views.observation_template_create import ObservationTemplateCreateView
from goats_tom.views.status import status_view
from goats_tom.views.dataproduct_list import GOATSDataProductListView
from goats_tom.views.target_delete import TargetDeleteView
from goats_tom.views.target_list import GOATSTargetListView
from goats_tom.views.target_detail import TargetDetailView
from goats_tom.views.tasks import ongoing_tasks
from goats_tom.views.user_generate_token import UserGenerateTokenView

__all__ = [
    "GOATSAddProductToGroupView",
    "GOATSDataProductGroupCreateView",
    "GOATSDataProductGroupDeleteView",
    "GOATSObservationGroupDeleteView",
    "GOATSTargetGroupingDeleteView",
    "GOATSDataProductGroupDetailView",
    "GOATSDataProductGroupListView",
    "GOATSDataProductListView",
    "GOATSObservationListView",
    "GOATSTargetListView",
    "GOATSAddExistingObservationView",
    "share_observation_record",
    "DRAGONSView",
    "DeleteObservationDataProductsView",
    "GOAArchiveRedirectView",
    "GOALoginView",
    "GOAQueryFormView",
    "DataProductDeleteView",
    "DataProductStreamView",
    "ObservationRecordDetailView",
    "TargetDeleteView",
    "UserGenerateTokenView",
    "ongoing_tasks",
    "recent_downloads",
    "update_brokerquery_name",
    "ObservationRecordDeleteView",
    "DataProductUploadView",
    "AstroDatalabLoginView",
    "GPPLoginView",
    "AstroDatalabView",
    "LCOLoginView",
    "TargetDetailView",
    "ObservationTemplateCreateView",
    "TNSLoginView",
    "status_view",
    "RefreshAntaresPhotometryView",
    "register",
    "registration_requests",
    "decide_registration_request",
    "GOATSUserCreateView",
    "GOATSUserUpdateView",
    "antares_request_access",
    "antares_manage_access",
    "antares_decide_join_request",
    "antares_revoke_membership",
    "antares_locus_dashboard",
    "antares_locus_table",
    "antares_remote_jobs",
    "antares_locus_save_targets",
    "antares_locus_saved_status",
    "antares_locus_clear",
    "antares_dashboard_status",
    "antares_stream_subscribe",
    "antares_stream_status",
    "antares_available_topics",
    "AntaresKafkaLoginView",
    "RSPTapLoginView",
]
