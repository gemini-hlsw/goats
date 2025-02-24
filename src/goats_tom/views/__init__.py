from goats_tom.views.astro_datalab import AstroDatalabView
from goats_tom.views.brokerquery_name import update_brokerquery_name
from goats_tom.views.dataproduct_delete import DataProductDeleteView
from goats_tom.views.dataproduct_upload import DataProductUploadView
from goats_tom.views.delete_observation_dataproducts import (
    DeleteObservationDataProductsView,
)
from goats_tom.views.downloads import recent_downloads
from goats_tom.views.dragons import DRAGONSView
from goats_tom.views.goa_query_form import GOAQueryFormView
from goats_tom.views.keys import (
    ManageKeysView,
    activate_user_key,
    create_key,
    delete_key,
)
from goats_tom.views.logins import AstroDatalabLoginView, GOALoginView
from goats_tom.views.observation_record_delete import ObservationRecordDeleteView
from goats_tom.views.observation_record_detail import ObservationRecordDetailView
from goats_tom.views.target_delete import TargetDeleteView
from goats_tom.views.tasks import ongoing_tasks
from goats_tom.views.user_generate_token import UserGenerateTokenView

__all__ = [
    "DRAGONSView",
    "DeleteObservationDataProductsView",
    "GOALoginView",
    "GOAQueryFormView",
    "DataProductDeleteView",
    "ObservationRecordDetailView",
    "TargetDeleteView",
    "ManageKeysView",
    "UserGenerateTokenView",
    "activate_user_key",
    "create_key",
    "delete_key",
    "ongoing_tasks",
    "recent_downloads",
    "update_brokerquery_name",
    "ObservationRecordDeleteView",
    "DataProductUploadView",
    "AstroDatalabLoginView",
    "AstroDatalabView",
]
