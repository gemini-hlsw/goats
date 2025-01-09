from .brokerquery_name import update_brokerquery_name
from .dataproduct_delete import DataProductDeleteView
from .dataproduct_upload import DataProductUploadView
from .delete_observation_dataproducts import DeleteObservationDataProductsView
from .downloads import recent_downloads
from .dragons import DRAGONSView
from .goa_login import GOALoginView
from .goa_query_form import GOAQueryFormView
from .keys import ManageKeysView, activate_user_key, create_key, delete_key
from .observation_record_delete import ObservationRecordDeleteView
from .observation_record_detail import ObservationRecordDetailView
from .target_delete import TargetDeleteView
from .tasks import ongoing_tasks
from .user_generate_token import UserGenerateTokenView

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
    "tasks",
    "downloads",
    "ongoing_tasks",
    "recent_downloads",
    "update_brokerquery_name",
    "ObservationRecordDeleteView",
    "DataProductUploadView",
]
