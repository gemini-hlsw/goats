from astropy import config as _config

__all__ = ["conf", "Conf"]


class Conf(_config.ConfigNamespace):
    """Configuration parameters for `astroquery.gmeini.Observations`."""

    GOA_SERVER = _config.ConfigItem("https://archive.gemini.edu", "URL for GOA server.")
    GOA_TIMEOUT = _config.ConfigItem(10, "Time limit for connecting to GOA server.")
    GOA_READ_TIMEOUT = _config.ConfigItem(
        120, "Time limit for GOA to send more data during a download."
    )
    GOA_RADIUS = _config.ConfigItem("0.3 deg", "Default query radius if not provided.")
    GOA_CHUNK_SIZE = _config.ConfigItem(
        20 * 1024 * 1024, "Chunk size to read/download files."
    )


conf = Conf()
