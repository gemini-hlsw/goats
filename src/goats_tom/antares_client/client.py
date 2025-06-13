"""ANTARES client code, imported directly due to dependency issues.

This module was adapted from the antares-client project. We had to import it directly
because the antares-client has pinned dependencies that are incompatible with Python
3.12, DRAGONS 4.0, and conda-forge including unmaintained packages like
marshmallow-jsonapi and confluent-kafka being pinned to an old version. This direct
import allows us to avoid these issues while retaining functionality for fetching
ANTARES alerts and loci.

As soon as the client issues are resolved, we hope to remove this and rely on the
client.
"""

__all__ = ["search", "get_by_id"]

import datetime
import json
from collections import defaultdict
from io import StringIO
from typing import Any, Dict, Iterator, List, Optional, Type
from urllib.parse import urljoin

import astropy.time
import astropy.timeseries
import marshmallow
import pandas as pd
import requests
from astropy.coordinates import SkyCoord
from marshmallow import fields, post_load
from marshmallow_jsonapi import Schema
from marshmallow_jsonapi import fields as jfields
from typing_extensions import TypedDict


def mjd_to_datetime(mjd):
    time = astropy.time.Time(mjd, format="mjd")
    time.format = "datetime"
    return time.value


class AntaresException(Exception):
    pass


PageParam = TypedDict(
    "PageParam",
    {
        "limit": int,
        "offset": int,
    },
)


QueryParams = TypedDict(
    "QueryParams",
    {
        "sort": str,
        "page": PageParam,
        "fields": Dict[str, List[str]],
        "elasticsearch_query": Dict,
        # "filter": None  # RESERVED
    },
)


config = {
    "ANTARES_API_BASE_URL": "https://api.antares.noirlab.edu/v1/",
    "API_TIMEOUT": 60,
}


class AlertGravWaveEvent(TypedDict):
    gracedb_id: str
    contour_level: float
    contour_area: float


class Alert:
    """
    An ANTARES alert represents a single visit/observation of an astronomical object.
    Attributes
    ----------
    alert_id: str
        ANTARES ID for this alert.
    mjd: float
        Modified julian date of the alert.
    properties: dict
        Arbitrary, survey-specific properties associated with this alert.
    Note
    ----------
    processed_at and grav_wave_events are Optional to not break user code that
    uses the Alert class. This Optional doesn't apply to antares non client.
    """

    def __init__(
        self,
        alert_id: str,
        mjd: float,
        properties: dict,
        processed_at: Optional[datetime.datetime] = None,
        grav_wave_events: Optional[List[Optional[AlertGravWaveEvent]]] = None,
        **_,
    ):
        self.alert_id = alert_id
        self.mjd = mjd
        self.processed_at = processed_at
        self.properties = properties
        self.grav_wave_events = grav_wave_events


class Locus:
    """
    An ANTARES locus is a collection of metadata describing a single astronomical
    object.
    Attributes
    ----------
    locus_id: str
        ANTARES ID for this object.
    ra: float
        Right ascension of the centroid of alert history.
    dec: float
        Declination of the centroid of alert history.
    properties: dict
        A dictionary of ANTARES- and user-generated properties that are updated every
        time there is activity on this locus (e.g. a new alert).
    tags: List[str]
        A list of strings that are added to this locus by ANTARES- and user-submitted
        filters that run against the real-time alert stream.
    alerts: Optional[List[Alert]]
        A list of alerts that are associated with this locus. If `None`, the alerts
        will be loaded on first access from the ANTARES HTTP API.
    catalogs: Optional[List[str]]
        Names of catalogs that this locus has been associated with.
    catalog_objects: Optional[List[dict]]
        A list of catalog objects that are associated with this locus. If `None`, they
        will be loaded on first access from the ANTARES HTTP API.
    lightcurve: Optional[pd.DataFrame]
        Data frame representation of a subset of normalized alert properties. If `None`
        it will be loaded on first access from the ANTARES HTTP API.
    watch_list_ids: Optional[List[str]]
        A list of IDs corresponding to user-submitted regional watch lists.
    watch_object_ids: Optional[List[str]]
        A list of IDs corresponding to user-submitted regional watch list objects.
    grav_wave_events: Optional[List[str]]
        A list of gravitational wave event ids that are associated with this locus.
    Notes
    -----
    Instances of this class lazy-load a few of their attributes from the ANTARES API.
    These attributes are: `alerts`, `catalog_objects` and `lightcurve`.
    """

    def __init__(
        self,
        locus_id: str,
        ra: float,
        dec: float,
        properties: dict,
        tags: List[str],
        alerts: Optional[List[Alert]] = None,
        catalogs: Optional[List[str]] = None,
        catalog_objects: Optional[List[dict]] = None,
        lightcurve: Optional[pd.DataFrame] = None,
        watch_list_ids: Optional[List[str]] = None,
        watch_object_ids: Optional[List[str]] = None,
        grav_wave_events: Optional[List[str]] = None,
        **_,
    ):
        self.locus_id = locus_id
        self.ra = ra
        self.dec = dec
        self.properties = properties
        self.tags = tags
        self.catalogs = catalogs
        if self.catalogs is None:
            self.catalogs = []
        self.watch_list_ids = watch_list_ids
        if self.watch_list_ids is None:
            self.watch_list_ids = []
        self.watch_object_ids = watch_object_ids
        if self.watch_object_ids is None:
            self.watch_object_ids = []
        self.grav_wave_events = grav_wave_events
        if self.grav_wave_events is None:
            self.grav_wave_events = []
        self._alerts = alerts
        self._catalog_objects = catalog_objects
        self._lightcurve = lightcurve
        self._timeseries = None
        self._coordinates = None

    def _fetch_alerts(self) -> List[Alert]:
        alerts = _list_resources(
            config["ANTARES_API_BASE_URL"]
            + "/".join(("loci", self.locus_id, "alerts")),
            _AlertSchema,
        )
        return list(alerts)

    def _fetch_lightcurve(self) -> pd.DataFrame:
        locus = _get_resource(
            config["ANTARES_API_BASE_URL"] + "/".join(("loci", self.locus_id)),
            _LocusSchema,
        )
        return locus.lightcurve

    def _fetch_catalog_objects(self) -> dict:
        catalog_matches = _list_resources(
            config["ANTARES_API_BASE_URL"]
            + "/".join(("loci", self.locus_id, "catalog-matches")),
            _CatalogEntrySchema,
        )
        catalog_matches = list(catalog_matches)
        catalog_objects = defaultdict(list)
        for match in catalog_matches:
            catalog_name = match["catalog_entry_id"].split(":")[0]
            catalog_objects[catalog_name].append(match["properties"])
        return catalog_objects

    @property
    def timeseries(self) -> astropy.timeseries.TimeSeries:
        """
        This `TimeSeries` contains all of the historical alert data associated with
        this object.
        """
        if self._timeseries is None:
            self._timeseries = astropy.timeseries.TimeSeries(
                data=[alert.properties for alert in self.alerts],
                time=[mjd_to_datetime(alert.mjd) for alert in self.alerts],
            )
        return self._timeseries

    @timeseries.setter
    def timeseries(self, value) -> None:
        self._timeseries = value

    @property
    def alerts(self) -> List[Alert]:
        """A list of alerts that are associated with this locus."""
        if self._alerts is None:
            self._alerts = self._fetch_alerts()
        return self._alerts

    @alerts.setter
    def alerts(self, value) -> None:
        self._alerts = value

    @property
    def catalog_objects(self) -> dict:
        """
        A dictionary of catalog objects that are associated with this locus. It has a
        structure like::
            {
                "<catalog_name">: [
                    { **<catalog_object_properties> },
                    { **<catalog_object_properties> },
                    ...
                ],
                ...
            }
        """
        if self._catalog_objects is None:
            self._catalog_objects = self._fetch_catalog_objects()
        return self._catalog_objects

    @catalog_objects.setter
    def catalog_objects(self, value) -> None:
        self._catalog_objects = value

    @property
    def lightcurve(self) -> pd.DataFrame:
        """Data frame representation of a subset of normalized alert properties."""
        if self._lightcurve is None:
            self._lightcurve = self._fetch_lightcurve()
        return self._lightcurve

    @lightcurve.setter
    def lightcurve(self, value) -> None:
        self._lightcurve = value

    @property
    def coordinates(self) -> SkyCoord:
        """Centroid of the locus as an AstroPy SkyCoord object."""
        if self._coordinates is None:
            self._coordinates = SkyCoord(f"{self.ra}d {self.dec}d")
        return self._coordinates


class _CatalogEntrySchema(Schema):
    class Meta:
        type_ = "catalog_entry"
        unknown = marshmallow.EXCLUDE

    id = jfields.Str(attribute="catalog_entry_id")
    object_id = jfields.Str()
    object_name = jfields.Str()
    name = jfields.Str()
    ra = jfields.Float()
    dec = jfields.Float()
    properties = jfields.Dict()
    catalog = jfields.Relationship()
    resource_meta = jfields.ResourceMeta()
    document_meta = jfields.DocumentMeta()


class _AlertSchema(Schema):
    class Meta:
        type_ = "alert"
        unknown = marshmallow.EXCLUDE

    id = jfields.String(attribute="alert_id")
    properties = jfields.Dict()
    processed_at = jfields.DateTime()
    mjd = jfields.Float()
    grav_wave_events = jfields.List(jfields.Dict())
    thumbnails = jfields.Relationship()
    resource_meta = jfields.ResourceMeta()
    document_meta = jfields.DocumentMeta()

    @post_load
    def make_alert(self, data: dict, **_):
        return Alert(**data)


class _Lightcurve(fields.Field):
    """Field that represents an ANTARES lightcurve as a pandas dataframe"""

    def _deserialize(self, value, attr, data, **kwargs):
        return pd.read_csv(StringIO(value))


def _list_all_resources(
    url: str, schema_cls: Type[Schema], params: Optional[QueryParams] = None
) -> Iterator[Any]:
    while True:
        response = requests.get(url, params=params, timeout=config["API_TIMEOUT"])
        if response.status_code >= 400:
            raise AntaresException(response.json())
        yield from schema_cls(many=True, partial=True).load(response.json())
        url = response.json().get("links", {}).get("next")
        if url is None:
            break
        params = None


def _get_resource(
    url: str, schema_cls: Type[Schema], params: Optional[QueryParams] = None
) -> Optional[Any]:
    response = requests.get(url, params=params, timeout=config["API_TIMEOUT"])
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise AntaresException(response.json())
    return schema_cls(partial=True).load(response.json())


def _list_resources(
    url: str, schema_cls: Type[Schema], params: Optional[QueryParams] = None
) -> Iterator[Any]:
    response = requests.get(url, params=params, timeout=config["API_TIMEOUT"])
    if response.status_code >= 400:
        raise AntaresException(response.json())
    yield from schema_cls(many=True, partial=True).load(response.json())


class _LocusListingSchema(Schema):
    class Meta:
        type_ = "locus_listing"
        unknown = marshmallow.EXCLUDE

    id = jfields.Str(attribute="locus_id")
    htm16 = jfields.Int()
    ra = jfields.Float()
    dec = jfields.Float()
    properties = jfields.Dict()
    locus = jfields.Relationship()
    alerts = jfields.Relationship()
    tags = jfields.List(jfields.Str())
    catalogs = jfields.List(jfields.Str())
    resource_meta = jfields.ResourceMeta()
    document_meta = jfields.DocumentMeta()

    @post_load
    def make_locus(self, data: dict, **_):
        return Locus(**data)


class _LocusSchema(Schema):
    class Meta:
        type_ = "locus"
        unknown = marshmallow.EXCLUDE

    id = jfields.Str(attribute="locus_id")
    htm16 = jfields.Int()
    ra = jfields.Float()
    dec = jfields.Float()
    grav_wave_events = jfields.List(jfields.Str())
    properties = jfields.Dict()
    lightcurve = _Lightcurve()
    alerts = jfields.Relationship()
    tags = jfields.List(jfields.Str())
    catalogs = jfields.List(jfields.Str())
    catalog_matches = jfields.List(jfields.Dict())
    resource_meta = jfields.ResourceMeta()
    document_meta = jfields.DocumentMeta()

    @post_load
    def make_locus(self, data: dict, **_):
        return Locus(**data)


def search(query: Dict) -> Iterator[Locus]:
    """
    Searches the ANTARES database for loci that meet certain criteria. Results are
    returned with the most recently updated objects first (sorted on the
    `properties.newest_alert_observation_time` field in descending order).
    Parameters
    ----------
    query: dict
        An ElasticSearch query. Must contain a top-level "query" key and only that
        top-level key. Other ES search arguments (e.g. "aggregations") are not allowed.
    Returns
    ----------
    Iterator over Locus objects
    """
    return _list_all_resources(
        urljoin(config["ANTARES_API_BASE_URL"], "loci"),
        _LocusListingSchema,
        params={
            "sort": "-properties.newest_alert_observation_time",
            "elasticsearch_query[locus_listing]": json.dumps(query),
        },
    )


def get_by_id(locus_id: str) -> Optional[Locus]:
    """
    Gets an ANTARES locus by its ANTARES ID.
    Parameters
    ----------
    locus_id: str
    Returns
    ----------
    Locus or None
    """
    return _get_resource(
        urljoin(config["ANTARES_API_BASE_URL"], f"loci/{locus_id}"),
        _LocusSchema,
    )
