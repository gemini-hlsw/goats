"""Grant delete permission on specific data products, deliberately and on the record.

Superusers do not get delete permission on data products implicitly -- see
`goats_tom.views.dataproduct_delete` for why. This command is the path when
an administrator genuinely needs to remove a PI's data: a corrupted file, a
departed PI's account being cleaned up, a mistaken upload the owner cannot
reach.

Deliberately a management command rather than a button. It requires shell
access to the server, which the person needing it already has, and it leaves
a log line naming who granted what and when. The point is not to stop the
administrator -- anyone with a Django shell can delete anything, and no
permission model changes that. The point is that destroying a PI's data
becomes an act somebody chose, with a record, rather than something that can
happen by misreading a page.

Examples
--------
One file, by its product id::

    python manage.py grant_delete --user admin --product ANT2020bk53s_lightcurve

Every file on an observation::

    python manage.py grant_delete --user admin --observation 42

Undo a grant that is no longer needed::

    python manage.py grant_delete --user admin --observation 42 --revoke

Notes
-----
Grants only `delete_dataproduct`. It does not grant view or change, and it
does not touch the observation record. An administrator who cannot already
see the file will not be able to see it afterwards -- though in practice
superusers still read everything, which is a separate open question recorded
in STATUS.md.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from guardian.shortcuts import assign_perm, remove_perm
from tom_dataproducts.models import DataProduct

logger = logging.getLogger(__name__)

DELETE_DATAPRODUCT = "tom_dataproducts.delete_dataproduct"


class Command(BaseCommand):
    help = (
        "Grant (or revoke) delete permission on specific data products. "
        "Superusers do not hold this implicitly; deleting another PI's data "
        "is a deliberate act and this command records it."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            required=True,
            metavar="USERNAME",
            help="The account that will be able to delete.",
        )
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument(
            "--product",
            metavar="PRODUCT_ID",
            help="A single data product, by its product_id.",
        )
        target.add_argument(
            "--observation",
            metavar="PK",
            type=int,
            help="Every data product on this observation record.",
        )
        parser.add_argument(
            "--revoke",
            action="store_true",
            help="Remove the grant instead of adding it.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=options["user"])
        except user_model.DoesNotExist:
            raise CommandError(f"No user named {options['user']!r}.")

        if options["product"]:
            products = list(
                DataProduct.objects.filter(product_id=options["product"])
            )
            if not products:
                raise CommandError(
                    f"No data product with product_id {options['product']!r}."
                )
        else:
            products = list(
                DataProduct.objects.filter(observation_record_id=options["observation"])
            )
            if not products:
                raise CommandError(
                    f"Observation {options['observation']} has no data products."
                )

        revoke = options["revoke"]
        for product in products:
            if revoke:
                remove_perm(DELETE_DATAPRODUCT, user, product)
            else:
                assign_perm(DELETE_DATAPRODUCT, user, product)

        verb = "Revoked" if revoke else "Granted"
        count = len(products)
        # Logged as well as printed: the printed line goes to whoever ran it,
        # the log line is what survives to be looked at afterwards.
        logger.warning(
            "%s delete permission on %d data product(s) for %s.",
            verb.lower(),
            count,
            user.username,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} delete on {count} data product"
                f"{'' if count == 1 else 's'} for {user.username}."
            )
        )
        if not revoke:
            self.stdout.write(
                "Revoke it again with --revoke once the deletion is done."
            )
