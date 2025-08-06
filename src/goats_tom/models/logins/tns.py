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
    group_names : list
        The list of group names the bot belongs to.
    """

    bot_id = models.CharField(max_length=50, blank=False, null=False)
    bot_name = models.CharField(max_length=50, blank=False, null=False)
    group_names = models.JSONField(default=list, blank=False, null=False)
