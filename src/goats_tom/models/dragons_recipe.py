"""Module for modified recipes."""

__all__ = ["DRAGONSRecipe"]

from typing import Any

from django.db import models

REDUCTION_MODE_SQ = "sq"
REDUCTION_MODE_QL = "ql"
REDUCTION_MODE_QA = "qa"

REDUCTION_MODE_CHOICES = (
    (REDUCTION_MODE_SQ, "Science-quality (sq)"),
    (REDUCTION_MODE_QL, "Quick look (ql)"),
    (REDUCTION_MODE_QA, "Quality assurance (qa)"),
)

DRPKG_GEMINIDR = "geminidr"

DRPKG_CHOICES = ((DRPKG_GEMINIDR, "geminidr"),)


class DRAGONSRecipe(models.Model):
    """
    Represents a DRAGONS recipe modification linked to a base recipe and a
    specific DRAGONS run.

    Attributes
    ----------
    recipe : models.ForeignKey
        A reference to a base recipe.
    dragons_run : models.ForeignKey
        A reference to the DRAGONS run to which this modified recipe belongs.
    function_definition : models.TextField
        The modified function definition provided by the user, if any.
    created_at : models.DateTimeField
        Timestamp when the recipe modification was created.
    modified_at : models.DateTimeField
        Timestamp when the recipe modification was last updated.
    observation_type : models.CharField
        A character field storing the type of the file.
    object_name : models.CharField
        An optional character field storing the name of the object related to
        the file, if applicable.
    uparms : models.TextField
        The uparms to apply to the recipe.
    reduction_mode : models.CharField
        The DRAGONS reduction mode to use.
    drpkg : models.CharField
        The data reduction package to use.
    additional_files : models.TextField
        Additional FITS files to pass to the reduction.
    ucals : models.TextField
        Calibration overrides to pass to the reduction.
    suffix : models.CharField
        An optional suffix to append to output files.
    """

    recipe = models.ForeignKey(
        "goats_tom.BaseRecipe",
        on_delete=models.CASCADE,
        related_name="modifications",
    )
    dragons_run = models.ForeignKey(
        "goats_tom.DRAGONSRun",
        on_delete=models.CASCADE,
        related_name="modified_recipes",
        editable=False,
        blank=False,
        null=False,
    )
    function_definition = models.TextField(
        editable=True,
        blank=True,
        null=True,
        help_text="Function definition by the user.",
    )
    uparms = models.TextField(
        editable=True,
        blank=True,
        null=True,
        help_text="The uparms to apply to the recipe.",
    )
    reduction_mode = models.CharField(
        max_length=4,
        choices=REDUCTION_MODE_CHOICES,
        default=REDUCTION_MODE_SQ,
        help_text="DRAGONS reduction mode passed to reduce_data(mode=...).",
    )
    drpkg = models.CharField(
        max_length=32,
        choices=DRPKG_CHOICES,
        default=DRPKG_GEMINIDR,
        help_text="Data reduction package passed to reduce_data(drpkg=...).",
    )
    additional_files = models.TextField(
        editable=True,
        blank=True,
        null=True,
        help_text=(
            "Additional FITS files to pass to reduce_data(files=...), "
            "stored as a list of paths relative to the target directory."
        ),
    )
    ucals = models.TextField(
        editable=True,
        blank=True,
        null=True,
        help_text=(
            "Calibration overrides passed to reduce_data(ucals=...), "
            "stored as a mapping of calibration type to file path."
        ),
    )
    suffix = models.CharField(
        max_length=64,
        blank=True,
        default=None,
        null=True,
        help_text="Optional suffix passed to reduce_data(suffix=...).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    observation_type = models.CharField(max_length=50, null=False, blank=False)
    object_name = models.CharField(max_length=100, null=True, blank=True)
    is_default = models.BooleanField(
        editable=False,
        null=False,
        blank=False,
        default=False,
    )
    observation_class = models.CharField(max_length=50, null=False, blank=False)

    class Meta:
        unique_together = (
            (
                "recipe",
                "dragons_run",
                "observation_type",
                "object_name",
                "observation_class",
            ),
        )

    def __str__(self) -> str:
        return f"v{self.version} {self.short_name} for run {self.dragons_run.run_id}"

    @property
    def short_name(self) -> str:
        """
        Provides the short name derived from the linked base recipe.

        Returns
        -------
        str
            The short name from the base recipe.
        """
        return self.recipe.short_name

    @property
    def instrument(self) -> str:
        """
        Provides the instrument derived from the linked base recipe.

        Returns
        -------
        str
            The instrument from the base recipe.
        """
        return self.recipe.instrument

    @property
    def recipes_module_name(self) -> str:
        """
        Provides the recipes module name.

        Returns
        -------
        str
            The recipes module name.
        """
        return self.recipe.recipes_module_name

    @property
    def name(self) -> str:
        """
        Provides the name derived from the linked base recipe.

        Returns
        -------
        str
            The name from the base recipe.
        """
        return self.recipe.name

    @property
    def version(self) -> str:
        """
        Provides the version derived from the linked base recipe.

        Returns
        -------
        str
            The version from the base recipe.
        """
        return self.recipe.version

    @property
    def active_function_definition(self) -> str:
        """
        Provides the active function definition, either the modified one if
        available or the base recipe's default.

        Returns
        -------
        str
            The active function definition.
        """
        return (
            self.function_definition
            if self.function_definition
            else self.recipe.function_definition
        )

    def list_primitives_and_docstrings(self) -> dict[str, Any]:
        """
        Retrieves the first file matching a specific file type from a collection
        managed by a DRAGONS run, and lists all available primitives and their
        documentation associated with that file.

        Returns
        -------
        dict[str, Any]
            A dictionary containing the method names as keys and their associated
            parameters and docstrings if a matching file is found. Returns an empty
            dictionary if no matching file is found.
        """
        first_file = self.recipe.recipes_module.files.filter(
            observation_type=self.observation_type
        ).first()

        if first_file:
            return first_file.list_primitives_and_docstrings()

        return {}

    def list_groups(self) -> list[str]:
        """
        Returns a list of groups for a recipe from the associated files.

        Returns
        -------
        list[str]
            A list of groups aka descriptors from the associated first file.
        """
        first_file = self.recipe.recipes_module.files.filter(
            observation_type=self.observation_type
        ).first()

        if first_file:
            return first_file.list_groups()

        return []
