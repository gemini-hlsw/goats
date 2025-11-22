"""
Base serializer for GPP serializers.
"""

__all__ = ["_BaseGPPSerializer"]

from typing import Any

from pydantic import BaseModel
from rest_framework import serializers


class _BaseGPPSerializer(serializers.Serializer):
    """
    Base serializer for GPP serializers.
    """

    pydantic_model: type[BaseModel] | None = None
    """The Pydantic model class corresponding to this serializer."""

    def to_pydantic(self) -> BaseModel | None:
        """
        Return the corresponding Pydantic model instance using formatted GPP input.

        Returns
        -------
        BaseModel | None
            An instance of the specified Pydantic model or ``None`` if formatted data
            is ``None``.

        Raises
        ------
        ValueError
            If ``pydantic_model`` is not defined.
        """
        data = self.to_gpp()
        if data is None:
            return None
        if self.pydantic_model is None:
            raise ValueError(f"{self.__class__.__name__} must define `pydantic_model`.")
        return self.finalize_pydantic(self.pydantic_model(**data))

    def finalize_pydantic(self, model: BaseModel) -> BaseModel:
        """
        Hook to modify or wrap the Pydantic model instance before returning.

        Subclasses may override this method to:
        - Attach metadata.
        - Inject nested values.
        - Transform the model (e.g., set defaults, reorder fields).

        Parameters
        ----------
        model : BaseModel
            The Pydantic model instance generated from GPP-formatted data.

        Returns
        -------
        BaseModel
            The possibly modified or wrapped Pydantic model instance.
        """
        return model

    def to_gpp(self) -> dict[str, Any] | None:
        """
        Public method to get the formatted GPP input dict.

        Returns
        -------
        dict[str, Any] | None
            The formatted GPP input dictionary.

        Notes
        -----
        - Must call ``.is_valid()`` before calling this method.
        """
        return self.finalize_gpp(self.format_gpp())

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Must be implemented by subclasses to format validated data
        into GPP input format.

        Returns
        -------
        dict[str, Any] | None
            The formatted GPP input dictionary.

        Raises
        ------
        NotImplementedError
            If the subclass does not implement this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement `format_gpp()` to produce "
            "GPP client input."
        )

    def finalize_gpp(self, formatted: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Hook for subclasses to modify or wrap formatted output.

        Subclasses may override this method to add metadata, combine
        sections, or enforce global schema consistency.
        """
        return formatted
