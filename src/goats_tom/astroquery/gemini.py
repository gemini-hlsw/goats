# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""==================================================
Gemini Observatory Archive (GOA) Astroquery Module
==================================================

Query public and proprietary data from GOA.
"""

__all__ = ["Observations", "ObservationsClass"]

import bz2
import os
import shutil
import tarfile
import tempfile
import time
from datetime import date
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import astrodata
import astropy
import astropy.units as u
import numpy as np
from astropy.table import MaskedColumn, Table
from astroquery import log
from astroquery.query import QueryWithLogin
from astroquery.utils.class_or_instance import class_or_instance
from gempy.utils import logutils
from gevent.threadpool import ThreadPool
from recipe_system import cal_service
from recipe_system.reduction.coreReduce import Reduce

from .conf import conf
from .urlhelper import URLHelper

__valid_instruments__ = [
    "GMOS",
    "GMOS-N",
    "GMOS-S",
    "GNIRS",
    "GRACES",
    "NIRI",
    "NIFS",
    "GSAOI",
    "F2",
    "GPI",
    "NICI",
    "MICHELLE",
    "TRECS",
    "BHROS",
    "HRWFS",
    "OSCIR",
    "FLAMINGOS",
    "HOKUPAA+QUIRC",
    "PHOENIX",
    "TEXES",
    "ABU",
    "CIRPASS",
]


__valid_observation_class__ = [
    "science",
    "acq",
    "progCal",
    "dayCal",
    "partnerCal",
    "acqCal",
]

__valid_observation_types__ = [
    "OBJECT",
    "BIAS",
    "DARK",
    "FLAT",
    "ARC",
    "PINHOLE",
    "RONCHI",
    "CAL",
    "FRINGE",
    "MASK",
]

__valid_modes__ = ["imaging", "spectroscopy", "LS", "MOS", "IFS"]

__valid_adaptive_optics__ = ["NOTAO", "AO", "NGS", "LGS"]

__valid_raw_reduced__ = [
    "RAW",
    "PREPARED",
    "PROCESSED_BIAS",
    "PROCESSED_FLAT",
    "PROCESSED_FRINGE",
    "PROCESSED_ARC",
]


class ObservationsClass(QueryWithLogin):
    url_helper = URLHelper()

    def __init__(self, *args):
        """Query class for observations in the Gemini archive.

        This class provides query capabilities against the gemini archive.
        Queries can be done by cone search, by name, or by a set of criteria.
        """
        super().__init__()

    def _login(self, username, password):
        """Login to the Gemini Archive website.

        This method will authenticate the session as a particular user.
        This may give you access to additional information or access based on
        your credentials

        Parameters
        ----------
        username : str
            The username to login as
        password : str
            The password for the given account

        Returns
        -------
        bool
            Returns `True` if login was successful, else `False`.

        """
        url = self.url_helper.get_login_url()
        data = {"username": username, "password": password}
        r = self._session.post(url, data=data)
        if r == 200:
            # Login successful.
            return False
        return True

    @class_or_instance
    def query_region(self, coordinates, *, radius=None):
        """Search for Gemini observations by target on the sky.

        Given a sky position and radius, returns a `~astropy.table.Table` of
        Gemini observations.

        Parameters
        ----------
        coordinates : str or `~astropy.coordinates` object
            The target around which to search. It may be specified as a
            string or as the appropriate `~astropy.coordinates` object.
        radius : str or `~astropy.units.Quantity` object, optional
            Default 0.3 degrees.
            The string must be parsable by `~astropy.coordinates.Angle`. The
            appropriate `~astropy.units.Quantity` object from
            `~astropy.units` may also be used. Defaults to 0.3 deg.

        Returns
        -------
        response : `~astropy.table.Table`

        """
        if radius is None:
            radius = u.Quantity(conf.GOA_RADIUS)
        return self.query_criteria(coordinates=coordinates, radius=radius)

    @class_or_instance
    def query_object(self, objectname, *, radius=None):
        """Search for Gemini observations by target on the sky.

        Given an object name and optional radius, returns a
        `~astropy.table.Table` of Gemini observations.

        Parameters
        ----------
        objectname : str
            The name of an object to search for.  This attempts to resolve the
            object by name and do a search on that area of the sky.  This does
            not handle moving targets.
        radius : str or `~astropy.units.Quantity` object, optional
            Default 0.3 degrees.
            The string must be parsable by `~astropy.coordinates.Angle`. The
            appropriate `~astropy.units.Quantity` object from
            `~astropy.units` may also be used. Defaults to 0.3 deg.

        Returns
        -------
        response : `~astropy.table.Table`

        """
        if radius is None:
            radius = u.Quantity(conf.GOA_RADIUS)
        return self.query_criteria(objectname=objectname, radius=radius)

    @class_or_instance
    def query_criteria(
        self,
        *rawqueryargs,
        coordinates=None,
        radius=None,
        pi_name=None,
        program_id=None,
        utc_date=None,
        instrument=None,
        observation_class=None,
        observation_type=None,
        mode=None,
        adaptive_optics=None,
        program_text=None,
        objectname=None,
        raw_reduced=None,
        orderby=None,
        **rawquerykwargs,
    ):
        """Search a variety of known parameters against the Gemini observations.

        Given various criteria, search the Gemini archive for matching
        observations.  Note that ``rawqueryargs`` and ``rawquerykwargs`` will
        pick up additional positional and key=value arguments and pass then on
        to the raw query as is.

        Parameters
        ----------
        coordinates : str or `~astropy.coordinates` object
            The target around which to search. It may be specified as a
            string or as the appropriate `~astropy.coordinates` object.
        radius : str or `~astropy.units.Quantity` object, optional
            Default 0.3 degrees if coordinates are set, else None
            The string must be parsable by `~astropy.coordinates.Angle`. The
            appropriate `~astropy.units.Quantity` object from
            `~astropy.units` may also be used. Defaults to 0.3 deg.
        pi_name : str, optional
            Default None.
            Can be used to search for data by the PI's name.
        program_id : str, optional
            Default None.
            Can be used to match on program ID
        utc_date : date or (date,date) tuple, optional
            Default None.
            Can be used to search for observations on a particular day or range
            of days (inclusive).
        instrument : str, optional
            Can be used to search for a particular instrument.  Valid values
            are:
                'GMOS',
                'GMOS-N',
                'GMOS-S',
                'GNIRS',
                'GRACES',
                'NIRI',
                'NIFS',
                'GSAOI',
                'F2',
                'GPI',
                'NICI',
                'MICHELLE',
                'TRECS',
                'BHROS',
                'HRWFS',
                'OSCIR',
                'FLAMINGOS',
                'HOKUPAA+QUIRC',
                'PHOENIX',
                'TEXES',
                'ABU',
                'CIRPASS'
        observation_class : str, optional
            Specifies the class of observations to search for.  Valid values
            are:
                'science',
                'acq',
                'progCal',
                'dayCal',
                'partnerCal',
                'acqCal'
        observation_type : str, optional
            Search for a particular type of observation.  Valid values are:
                'OBJECT',
                'BIAS',
                'DARK',
                'FLAT',
                'ARC',
                'PINHOLE',
                'RONCHI',
                'CAL',
                'FRINGE',
                'MASK'
        mode : str, optional
            The mode of the observation.  Valid values are:
                'imaging',
                'spectroscopy',
                'LS',
                'MOS',
                'IFS'
        adaptive_optics : str, optional
            Specify the presence of adaptive optics.  Valid values are:
                'NOTAO',
                'AO',
                'NGS',
                'LGS'
        program_text : str, optional
            Specify text in the information about the program.  This is free
            form text.
        objectname : str, optional
            Give the name of the target.
        raw_reduced : str, optional
            Indicate the raw or reduced status of the observations to search
            for.  Valid values are:
                'RAW',
                'PREPARED',
                'PROCESSED_BIAS',
                'PROCESSED_FLAT',
                'PROCESSED_FRINGE',
                'PROCESSED_ARC'
        orderby : str, optional
            Indicates how the results should be sorted.  Values should be like
            the ones used in the archive website when sorting a column.
            example, ``data_label_desc`` would sort by the data label in
            descending order.
        rawqueryargs : list, optional
            Additional arguments will be passed down to the raw query.  This
            covers any additional parameters that would end up as
            '/parametervalue/' in the URL to the archive webservice.
        rawquerykwargs : dict, optional
            Additional key/value arguments will also be passed down to the raw
            query.  This covers any parameters that would end up as
            '/key=value/' in the URL to the archive webservice.

        Returns
        -------
        response : `~astropy.table.Table`

        Raises
        ------
        ValueError: passed value is not recognized for the given field, see
        message for details

        """
        # Build parameters into raw query
        #
        # This consists of a set of unnamed arguments, args, and key/value
        # pairs, kwargs

        # These will hold the passed freeform parameters plus the explicit
        # criteria for our eventual call to the raw query method
        args = list()
        kwargs = dict()

        # Copy the incoming set of free-form arguments
        if rawqueryargs:
            for arg in rawqueryargs:
                args.append(arg)
        if rawquerykwargs:
            for k, v in rawquerykwargs.items():
                kwargs[k] = v

        # If coordinates is set but we have no radius, set a default
        if (coordinates or objectname) and radius is None:
            radius = u.Quantity(conf.GOA_RADIUS)
        # Now consider the canned criteria
        if radius is not None:
            kwargs["radius"] = radius
        if coordinates is not None:
            kwargs["coordinates"] = coordinates
        if pi_name is not None:
            kwargs["PIname"] = pi_name
        if program_id is not None:
            kwargs["progid"] = program_id.upper()
        if utc_date is not None:
            if isinstance(utc_date, date):
                args.append(utc_date.strftime("YYYYMMdd"))
            elif isinstance(utc_date, tuple):
                if len(utc_date) != 2:
                    raise ValueError("utc_date tuple should have two values")
                if not isinstance(utc_date[0], date) or not isinstance(
                    utc_date[1], date
                ):
                    raise ValueError("utc_date tuple should have date values in it")
                args.append(f"{utc_date[0]:%Y%m%d}-{utc_date[1]:%Y%m%d}")
        if instrument is not None:
            if instrument.upper() not in __valid_instruments__:
                raise ValueError(f"Unrecognized instrument: {instrument}")
            args.append(instrument)
        if observation_class is not None:
            if observation_class not in __valid_observation_class__:
                raise ValueError(f"Unrecognized observation class: {observation_class}")
            args.append(observation_class)
        if observation_type is not None:
            if observation_type not in __valid_observation_types__:
                raise ValueError(f"Unrecognized observation type: {observation_type}")
            args.append(observation_type)
        if mode is not None:
            if mode not in __valid_modes__:
                raise ValueError(f"Unrecognized mode: {mode}")
            args.append(mode)
        if adaptive_optics is not None:
            if adaptive_optics not in __valid_adaptive_optics__:
                raise ValueError(f"Unrecognized adaptive optics: {adaptive_optics}")
            args.append(adaptive_optics)
        if program_text is not None:
            kwargs["ProgramText"] = program_text
        if objectname is not None:
            kwargs["object"] = objectname
        if raw_reduced is not None:
            if raw_reduced not in __valid_raw_reduced__:
                raise ValueError(f"Unrecognized raw/reduced setting: {raw_reduced}")
            args.append(raw_reduced)
        if orderby is not None:
            kwargs["orderby"] = orderby

        return self.query_raw(*args, **kwargs)

    @class_or_instance
    def query_raw(self, *args, **kwargs):
        """Perform flexible query against Gemini observations

        This is a more flexible query method.  This method will do special
        handling for coordinates and radius if present in kwargs.  However, for
        the remaining arguments it assumes all of args are useable as query
        path elements.  For kwargs, it assumes all of the elements can be
        passed as name=value within the query path to Gemini.

        This method does not do any validation checking or attempt to
        interperet the values being passed, aside from coordinates and radius.

        This method is most useful when the query_criteria and query_region do
        not meet your needs and you can build the appropriate search in the
        website.  When you see the URL that is generated by the archive, you
        can translate that into an equivalent python call with this method. For
        example, if the URL in the website is:

        https://archive.gemini.edu/searchform/RAW/cols=CTOWEQ/notengineering/GMOS-N/PIname=Hirst/NotFail

        You can disregard NotFail, cols=x and notengineering. You would run
        this query as

        query_raw('GMOS-N', PIname='Hirst')

        Parameters
        ----------
        args :
            The list of parameters to be passed via the query path to the
            webserver
        kwargs :
            The dictionary of parameters to be passed by name=value within the
            query path to the webserver.  The ``orderby`` key value pair has a
            special intepretation and is appended as a query parameter like the
            one used in the archive website for sorting results.

        Returns
        -------
        response : `~astropy.table.Table`

        """
        url = self.url_helper.get_summary_url(*args, **kwargs)

        response = self._request(
            method="GET",
            url=url,
            data={},
            timeout=conf.GOA_TIMEOUT,
            cache=False,
        )

        js = response.json()
        return _gemini_json_to_table(js)

    def get_file_list(self, *query_args, **query_kwargs):
        url = self.url_helper.get_file_list_url(*query_args, **query_kwargs)

        response = self._request(
            method="GET",
            url=url,
            data={},
            timeout=conf.GOA_TIMEOUT,
            cache=False,
        )

        js = response.json()
        return _gemini_json_to_table(js)

    def get_file(self, filename, *, download_dir=".", timeout=None):
        """Download the requested file to the current directory

        filename : str
            Name of the file to download
        download_dir : str, optional
            Name of the directory to download to
        timeout : int, optional
            Timeout of the request in milliseconds
        """
        url = self.get_file_url(filename)
        local_filepath = os.path.join(download_dir, filename)
        self._download_file(url=url, local_filepath=local_filepath, timeout=timeout)

    def _download_file_content(
        self,
        url,
        timeout=None,
        auth=None,
        method="GET",
        **kwargs,
    ):
        """Download content from a URL and return it. Resembles
        `_download_file` but returns the content instead of saving it to a
        local file.

        Parameters
        ----------
        url : str
            The URL from where to download the file.
        timeout : int, optional
            Time in seconds to wait for the server response, by default
            `None`.
        auth : dict[str, Any], optional
            Authentication details, by default `None`.
        method : str, optional
            The HTTP method to use, by default "GET".

        Returns
        -------
        bytes
            The downloaded content.

        """
        response = self._session.request(
            method,
            url,
            timeout=timeout,
            auth=auth,
            **kwargs,
        )
        response.raise_for_status()

        if "content-length" in response.headers:
            length = int(response.headers["content-length"])
            if length == 0:
                log.warn(f"URL {url} has length=0")

        blocksize = astropy.utils.data.conf.download_block_size
        content = b""

        for block in response.iter_content(blocksize):
            content += block

        response.close()

        return content

    def logout(self):
        """Logout from the GOA service by deleting the specific session cookie
        and updating the authentication state.
        """
        # Delete specific cookie.
        cookie_name = "gemini_archive_session"
        if cookie_name in self._session.cookies:
            del self._session.cookies[cookie_name]

        # Update authentication state.
        self._authenticated = False

    def get_file_content(
        self,
        filename,
        timeout=None,
        auth=None,
        method="GET",
        **kwargs,
    ):
        """Wrapper around `_download_file_content`.

        Parameters
        ----------
        filename : str
            Name of the file to download content.
        timeout : int, optional
            Time in seconds to wait for the server response, by default
            `None`.
        auth : dict[str, Any], optional
            Authentication details, by default `None`.
        method : str, optional
            The HTTP method to use, by default "GET".

        Returns
        -------
        bytes
            The downloaded content.

        """
        url = self.get_file_url(filename)
        return self._download_file_content(
            url,
            timeout=timeout,
            auth=auth,
            method=method,
            **kwargs,
        )

    def get_file_url(self, filename):
        """Generate the file URL based on the filename.

        Parameters
        ----------
        filename : str
            The name of the file.

        Returns
        -------
        str
            The URL where the file can be downloaded.

        """
        return self.url_helper.get_file_url(filename)

    def get_search_url(self, program_id):
        """Generate the search URL based on the program ID.

        Parameters
        ----------
        program_id : str
            The program ID to search for.

        Returns
        -------
        str
            The URL for the program ID.

        """
        return self.url_helper.get_search_url(program_id)

    def get_calibration_files(
        self,
        dest_folder,
        *query_args,
        decompress_fits=True,
        remove_readme=True,
        download_state=None,
        **query_kwargs,
    ) -> dict[str, Any]:
        """Download all associated calibrations files as a tar archive. Will
        untar folder after download.

        This will overwrite any files that already exist.

        Parameters
        ----------
        dest_folder : Path or str
            The folder where the tar archive should be saved and extracted
            files moved to.
        query_args : tuple
            Query arguments to pass to GOA query.
        decompress_fits : bool, optional
            Decompress bz2 fits files, default is `True`.
        remove_readme : bool, optional
            Remove README and MD5 text files included in download, default is
            `True`.
        download_state : DownloadProgressState, optional
            State of the current download, by default `None`.
        query_kwargs : dict
            Query keyword arguments to pass to GOA query.

        Returns
        -------
        dict[str, Any]
            A dictionary containing the number of files downloaded, the number
            of files omitted, a human-readable message, and boolean success.

        """
        # Assign argument to get calibrations.
        args = query_args + ("associated_calibrations",)

        return self.get_files(
            dest_folder,
            *args,
            decompress_fits=decompress_fits,
            remove_readme=remove_readme,
            download_state=download_state,
            **query_kwargs,
        )

    def get_files(
        self,
        dest_folder,
        *query_args,
        decompress_fits=True,
        remove_readme=True,
        download_state=None,
        **query_kwargs,
    ) -> dict[str, Any]:
        """Download all files associated with a GOA query as a tar
        archive and optionally decompress bz2 files.

        Parameters
        ----------
        dest_folder : Path or str
            The folder where the tar archive should be saved and extracted
            files moved to.
        query_args : tuple
            Query arguments to pass to GOA query.
        decompress_fits : bool, optional
            Decompress bz2 fits files, default is `True`.
        remove_readme : bool, optional
            Remove README and MD5 text files included in download, default is
            `True`.
        download_state : str, optional
            State of the current download, by default `None`.
        query_kwargs : dict
            Query keyword arguments to pass to GOA query.

        Returns
        -------
        dict[str, Any]
            A dictionary containing the number of files downloaded, the number
            of files omitted, a human-readable message, and boolean success.

        """
        last_update_time = time.time()
        parallize = False
        # Convert destination folder.
        dest_folder = Path(dest_folder).expanduser()
        url = self.url_helper.get_tar_file_url(*query_args, **query_kwargs)

        response = self._session.get(url, stream=True)
        response.raise_for_status()

        # Check if data is good.
        data = response.iter_content(chunk_size=conf.GOA_CHUNK_SIZE)
        first_chunk = next(data)
        downloaded_bytes = len(first_chunk)
        if b"No files to download." in first_chunk:
            response.close()
            return {
                "downloaded_files": [],
                "num_files_downloaded": 0,
                "num_files_omitted": 0,
                "message": "No available files to download. Verify search is valid.",
                "search_url": url,
                "success": False,
            }

        dest_folder.mkdir(parents=True, exist_ok=True)

        # Use a temporary directory to unpack.
        with tempfile.TemporaryDirectory(dir=dest_folder) as temp_dir:
            temp_dir_path = Path(temp_dir)
            # Generate tar_filename based on current time.
            tar_path = temp_dir_path / "goa-query.tar"

            # Stream download.
            with open(tar_path, "wb") as f:
                f.write(first_chunk)
                for chunk in data:
                    f.write(chunk)
                    downloaded_bytes += len(chunk)

                    # Check if enough time passed to update.
                    if download_state is not None:
                        current_time = time.time()
                        if current_time - last_update_time > 1:
                            download_state.update_and_send(
                                downloaded_bytes=downloaded_bytes,
                            )
                            last_update_time = current_time

            response.close()

            if download_state is not None:
                download_state.update_and_send(
                    status="Extracting and decompressing...",
                    downloaded_bytes=downloaded_bytes,
                )

            # Extract the tar archive.
            with tarfile.open(tar_path, "r") as tar:
                tar.extractall(path=temp_dir_path)

            # Delete the tar file after extraction.
            tar_path.unlink()

            # Build download statistics.
            download_info = self._generate_download_info(temp_dir_path)

            # Delete additional files if wanted.
            # TODO: Now that we have this in a temp directory, this does nothing.
            if remove_readme:
                for file_name in ["README.txt", "md5sums.txt"]:
                    file_path = temp_dir_path / file_name
                    if file_path.exists():
                        file_path.unlink()

            # Decompress inner files.
            if decompress_fits:
                file_paths = [
                    (temp_dir_path / filename)
                    for filename in download_info["downloaded_files"]
                ]

                if parallize:
                    self._gevent_decompress_bz2_parallel(file_paths)
                else:
                    for f in file_paths:
                        self._decompress_bz2(f)

                # Update file names in download_info.
                download_info["downloaded_files"] = [
                    filename.replace(".bz2", "")
                    for filename in download_info["downloaded_files"]
                ]

            # If GHOST data, unpack.
            bundled_ghost_files = []
            for filename in download_info["downloaded_files"]:
                file_path = temp_dir_path / filename

                # Check if its bundled ghost data.
                ad = astrodata.open(file_path)
                if {"GHOST", "BUNDLE"}.issubset(ad.tags):
                    # Got bundled ghost data, let us add to the list to unbundle.
                    bundled_ghost_files.append(file_path)

            # Now run the dragons process.
            if bundled_ghost_files:
                # Update download bar.
                if download_state is not None:
                    download_state.update_and_send(
                        status="Unbundling GHOST data...",
                        downloaded_bytes=downloaded_bytes,
                    )

                # Update the log output for DRAGONS to quiet and level 40 (ERROR).
                logutils.config(mode="quiet", file_lvl=40)

                # Create directory to unbundle in.
                unbundle_ghost_dir = temp_dir_path / "unbundle_ghost"
                unbundle_ghost_dir.mkdir()

                # Create calibration database needed for DRAGONS.
                db_path = unbundle_ghost_dir / "unbundle_ghost.db"
                cal_service.LocalDB(db_path, force_init=True)

                # Create the dragonsrc file.
                dragons_rc = unbundle_ghost_dir / "dragonsrc"
                with open(dragons_rc, "w") as f:
                    f.write(f"[calibs]\ndatabases = {db_path} get store")

                # Change directory to where DRAGONS needs to write unbundled data.
                os.chdir(unbundle_ghost_dir)
                r = Reduce()
                # DRAGONS requires strings to be passed.
                r.files.extend([str(file) for file in bundled_ghost_files])
                r.config_file = str(dragons_rc)
                r.runr()

                # Get the list of new files created by DRAGONS.
                new_files = [file.name for file in unbundle_ghost_dir.glob("*.fits")]

                # Remove the original bundled files from download_info.
                for bundled_file in bundled_ghost_files:
                    download_info["downloaded_files"].remove(bundled_file.name)
                    bundled_file.unlink()

                # Add new files to the download_info.
                download_info["downloaded_files"].extend(new_files)
                download_info["num_files_downloaded"] += len(new_files) - len(
                    bundled_ghost_files
                )

            # Prepare file paths for moving.
            move_file_paths = [
                (file_path, dest_folder / file_path.name)
                for file_path in temp_dir_path.glob("**/*.fits")
                if file_path.is_file()
            ]

            if parallize:
                # Use gevent to move files in parallel.
                self._gevent_move_files_parallel(move_file_paths)
            else:
                for move_file_path in move_file_paths:
                    self._move_file(move_file_path)

        return download_info

    def _generate_download_info(self, extract_dir: Path) -> dict[str, Any]:
        """Generate download information.

        Parameters
        ----------
        `extract_dir` : Path
            The directory where "README.txt" and "md5sums.txt" are located.

        Returns
        -------
        `dict[str, Any]`
            A dictionary containing the number of files downloaded, the number
            of files omitted, a human-readable message, and boolean success.

        """
        readme_path = extract_dir / "README.txt"
        md5sums_path = extract_dir / "md5sums.txt"

        # Get names of files downloaded.
        downloaded_files = set()
        if md5sums_path.exists():
            with open(md5sums_path) as file:
                for line in file:
                    parts = line.strip().split()
                    if len(parts) == 2:
                        filename = parts[1]
                        if filename in downloaded_files:
                            print(f"Duplicate file detected in md5sums: {filename}")
                        # Set ignores duplicates.
                        downloaded_files.add(filename)

        # Get number of files downloaded.
        num_files_downloaded = len(downloaded_files)

        # Get number of files omitted.
        num_files_omitted = 0
        if readme_path.exists():
            with open(readme_path) as file:
                num_files_omitted = sum(1 for line in file if ".fits.bz2" in line)

        # Constructing the message
        if num_files_downloaded == 0 and num_files_omitted == 0:
            message = (
                "No files were found or downloaded. Data for this observation "
                "record does not exist."
            )
        else:
            message = f"Downloaded {num_files_downloaded} files."
            if num_files_omitted > 0:
                message += f" {num_files_omitted} proprietary files were omitted."

        # Extract search criteria from README.txt
        search_url = ""
        if readme_path.exists():
            with open(readme_path) as file:
                for line in file:
                    if "The search criteria was:" in line:
                        search_url = line.split(": ")[1].strip()
                        break

        download_info = {
            "downloaded_files": list(downloaded_files),
            "num_files_downloaded": num_files_downloaded,
            "num_files_omitted": num_files_omitted,
            "message": message,
            "search_url": search_url,
            "success": True,
        }

        return download_info

    def _decompress_bz2_parallel(self, file_paths: list[Path]) -> None:
        """Parallize decompressing files.

        Parameters
        ----------
        file_paths : list[Paths]
            List of file paths to decompress.

        """
        # TODO: Make n cores a configuration.
        with Pool() as pool:
            pool.map(self._decompress_bz2, file_paths)

    def _decompress_bz2(self, file_path: Path) -> None:
        """Decompress a .bz2 file and write to the same filename.

        This will overwrite any files that already exist.

        Parameters
        ----------
        file_path : Path
            Path to the .bz2 file to be decompressed.

        """
        decompressed_file_path = file_path.with_suffix("")

        with (
            bz2.open(file_path, "rb") as in_file,
            open(decompressed_file_path, "wb") as out_file,
        ):
            while chunk := in_file.read(conf.GOA_CHUNK_SIZE):
                out_file.write(chunk)

        file_path.unlink()

    def _gevent_decompress_bz2_parallel(self, file_paths: list[Path]) -> None:
        """Parallelize decompressing files compatible with "gevent" and "huey".

        Parameters
        ----------
        file_paths : `list[Paths]`
            List of file paths to decompress.

        """
        # TODO: Make gevent threads a configuration.
        pool = ThreadPool(10)
        pool.map(self._decompress_bz2, file_paths)
        pool.join()

    def _gevent_move_files_parallel(self, file_paths: list[tuple[Path, Path]]) -> None:
        """Parallelize moving files using gevent's pool.map.

        Parameters
        ----------
        file_paths : `list[tuple[Path, Path]]`
            List of tuples containing source and destination paths for files
            to be moved.

        """
        pool = ThreadPool(10)
        pool.map(self._move_file, file_paths)
        pool.join()

    def _move_file(self, src_dest_paths: tuple[Path, Path]) -> None:
        """Move a file from source to destination.

        Parameters
        ----------
        src_dest_paths : tuple[Path, Path]
            Tuple containing the source and destination file paths.

        """
        src_path, dest_path = src_dest_paths

        if dest_path.exists():
            dest_path.unlink()
        shutil.move(src_path, dest_path)


def _gemini_json_to_table(json):
    """Takes a JSON object as returned from the Gemini archive webserver and turns
    it into an `~astropy.table.Table`.

    Parameters
    ----------
    json : list[dict]
        A list of JSON objects from the Gemini archive webserver

    Returns
    -------
    response : `~astropy.table.Table`

    """
    if not json:
        return Table()

    # Inferring keys from the first JSON object
    keys = json[0].keys()

    data_table = Table(masked=True)

    for key in keys:
        col_data = np.array([obj.get(key, None) for obj in json])

        atype = str  # Define type if necessary; default is string
        col_mask = np.equal(col_data, None)

        data_table.add_column(
            MaskedColumn(col_data.astype(atype), name=key, mask=col_mask),
        )

    return data_table


Observations = ObservationsClass()
