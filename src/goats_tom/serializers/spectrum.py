__all__ = ["SpectrumSerializer"]

from typing import Dict

import numpy as np
from astropy import units as u
from astropy.units import Quantity
from specutils import Spectrum1D


class SpectrumSerializer:
    def _to_list_none(self, arr) -> list:
        """
        Convert an array-like to a Python list, replacing non-finite numbers with None.
        Vectorized and tolerant of masked arrays.
        """
        # Unmask if needed (masked → fill with NaN)
        a = np.ma.getdata(arr)
        if np.ma.isMaskedArray(arr):
            a = np.ma.filled(arr, np.nan)

        a = np.asarray(a, dtype=float)
        # Vectorized non-finite mask
        mask = ~np.isfinite(a)
        out = a.tolist()
        # Replace non-finite with None (in-place, fast over loop-per-item)
        for i in np.nonzero(mask)[0]:
            out[i] = None
        return out

    def _from_list_none(self, seq) -> np.ndarray:
        """
        Convert a sequence where None means NaN into a float NumPy array.
        """
        return np.asarray(
            [float("nan") if v is None else float(v) for v in seq],
            dtype=float,
        )

    def serialize(self, spectrum: Spectrum1D) -> Dict[str, object]:
        """
        Serialize a Spectrum1D to a plain dict.

        Parameters
        ----------
        spectrum : Spectrum1D
            The spectrum to serialize.

        Returns
        -------
        dict
            Dictionary with keys:
            - ``"flux"``: list[float|None]
            - ``"flux_units"``: str
            - ``"wavelength"``: list[float|None]
            - ``"wavelength_units"``: str

        Raises
        ------
        ValueError
            If flux and wavelength lengths differ.
        """
        wl = getattr(spectrum, "wavelength", spectrum.spectral_axis)

        flux_vals = self._to_list_none(getattr(spectrum.flux, "value", spectrum.flux))
        wl_vals = self._to_list_none(getattr(wl, "value", wl))

        payload = {
            "flux": flux_vals,
            "flux_units": spectrum.flux.unit.to_string(),
            "wavelength": wl_vals,
            "wavelength_units": wl.unit.to_string(),
        }
        if len(payload["flux"]) != len(payload["wavelength"]):
            raise ValueError("Length mismatch between flux and wavelength")
        return payload

    def deserialize(self, data: Dict[str, object]) -> Spectrum1D:
        """
        Reconstruct a Spectrum1D from a dict produced by ``serialize``.

        Parameters
        ----------
        data : dict
            Dictionary with keys ``"flux"``, ``"flux_units"``,
            ``"wavelength"``, ``"wavelength_units"``.

        Returns
        -------
        Spectrum1D
            The reconstructed spectrum.

        Raises
        ------
        KeyError
            If any required key is missing.
        """
        try:
            flux_list = data["flux"]
            flux_units = data["flux_units"]
            wave_list = data["wavelength"]
            wave_units = data["wavelength_units"]
        except KeyError as exc:
            raise KeyError(f"Missing key in data: {exc.args[0]!r}") from exc

        flux = Quantity(self._from_list_none(flux_list), u.Unit(str(flux_units)))
        wave = Quantity(self._from_list_none(wave_list), u.Unit(str(wave_units)))

        return Spectrum1D(flux=flux, spectral_axis=wave)
