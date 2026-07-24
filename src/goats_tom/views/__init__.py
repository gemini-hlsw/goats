from goats_tom.views.antares import RefreshAntaresPhotometryView
from goats_tom.views.antares_locus_dashboard import (
    antares_dashboard_status,
    antares_locus_clear,
    antares_locus_dashboard,
    antares_locus_save_targets,
    antares_locus_saved_status,
    antares_locus_table,
)
from goats_tom.views.antares_stream_subscribe import (
    antares_available_topics,
    antares_stream_status,
    antares_stream_subscribe,
)
from goats_tom.views.astro_datalab import AstroDatalabView
from goats_tom.views.brokerquery_name import update_brokerquery_name
from goats_tom.views.dataproduct_delete import DataProductDeleteView
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
    TNSLoginView,
)
from goats_tom.views.observation_record_delete import ObservationRecordDeleteView
from goats_tom.views.observation_record_detail import ObservationRecordDetailView
from goats_tom.views.observation_template_create import ObservationTemplateCreateView
from goats_tom.views.status import status_view
from goats_tom.views.target_delete import TargetDeleteView
from goats_tom.views.target_detail import TargetDetailView
from goats_tom.views.tasks import ongoing_tasks
from goats_tom.views.user_generate_token import UserGenerateTokenView

__all__ = [
    "DRAGONSView",
    "DeleteObservationDataProductsView",
    "GOAArchiveRedirectView",
    "GOALoginView",
    "GOAQueryFormView",
    "DataProductDeleteView",
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
    "antares_locus_dashboard",
    "antares_locus_table",
    "antares_locus_save_targets",
    "antares_locus_saved_status",
    "antares_locus_clear",
    "antares_dashboard_status",
    "antares_stream_subscribe",
    "antares_stream_status",
    "antares_available_topics",
    "AntaresKafkaLoginView",
]
