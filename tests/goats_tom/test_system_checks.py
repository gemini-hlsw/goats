"""Runs Django's own system checks as a test.

`pytest-django` calls `django.setup()` but never runs the system-check
framework, so a whole class of model-level mistake passes the entire suite
and only surfaces when somebody runs `migrate` or `runserver`. That is the
worst possible place to find it: the checks are what stand between a bad
field definition and a deployment that will not boot.

This was not hypothetical. A `ForeignKey("tom_targets.Target")` on
`goats_tom.models.TNSSubmissionRecord` passed every test here and failed
`migrate` with `fields.E300`, because `tom_targets.Target` is a module-level
alias assigned from ``settings.TARGET_MODEL_CLASS`` rather than a model the
app registry knows about. One test that runs the checks would have caught it
immediately.
"""

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_django_system_checks_pass():
    """`manage.py check` reports no issues.

    Notes
    -----
    Raises `SystemCheckError` on failure, which fails the test with Django's
    own message naming the offending field -- more useful than anything a
    custom assertion could produce.

    Deliberately not restricted to the `models` tag. The check framework
    also validates URLs, templates, admin registrations and security
    settings, and none of those are otherwise exercised as a whole here.
    """
    call_command("check")
