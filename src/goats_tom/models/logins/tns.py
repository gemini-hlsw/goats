__all__ = ["TNSLogin"]

from django.db import models

from .base import TokenLogin


class TNSLogin(TokenLogin):
    """A login model for TNS credentials, using an API key as the token.

    Attributes
    ----------
    bot_id : str
        The bot ID used for submissions.
    bot_name : str
        The name of the bot submitting data.

    Notes
    -----
    The groups this bot may file under are rows in
    `goats_tom.models.TNSGroup`, not a list here. They were a list of strings
    on this model, which made the name the only thing identifying a group:
    correcting a typo in it silently revoked everyone who had been approved
    for the old spelling, because their membership pointed at the text rather
    than at a row.
    """

    bot_id = models.CharField(max_length=50, blank=False, null=False)
    bot_name = models.CharField(max_length=50, blank=False, null=False)
