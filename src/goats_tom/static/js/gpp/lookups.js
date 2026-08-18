/**
 * A static utility class that provides dictionary-style mappings
 * from enum-style string keys to human-readable labels for various
 * fields used in observation forms.
 */

class Lookups {
  static imageQuality = {
    POINT_ONE: "< 0.10",
    POINT_TWO: "< 0.20",
    POINT_THREE: "< 0.30",
    POINT_FOUR: "< 0.40",
    POINT_SIX: "< 0.60",
    POINT_EIGHT: "< 0.80",
    ONE_POINT_ZERO: "< 1.00",
    ONE_POINT_FIVE: "< 1.50",
    TWO_POINT_ZERO: "< 2.00",
    THREE_POINT_ZERO: "< 3.00",
  };

  static cloudExtinction = {
    POINT_ONE: "< 0.10 mag",
    POINT_THREE: "< 0.30 mag",
    POINT_FIVE: "< 0.50 mag",
    ONE_POINT_ZERO: "< 1.00 mag",
    ONE_POINT_FIVE: "< 1.50 mag",
    TWO_POINT_ZERO: "< 2.00 mag",
    THREE_POINT_ZERO: "< 3.00 mag",
  };

  static gmosRoi = {
    FULL_FRAME: "Full Frame",
    CCD2: "CCD2",
    CENTRAL_SPECTRUM: "Central Spectrum",
    CENTRAL_STAMP: "Central Stamp",
    CUSTOM: "Custom",
  };

  static gmosBinning = {
    ONE: "1",
    TWO: "2",
    FOUR: "4",
  };

  static gmosNorthBuiltinFpu = {
    NS0: "NS0",
    NS1: "NS1",
    NS2: "NS2",
    NS3: "NS3",
    NS4: "NS4",
    NS5: "NS5",
    LONG_SLIT_0_25: "Longslit 0.25 arcsec",
    LONG_SLIT_0_50: "Longslit 0.50 arcsec",
    LONG_SLIT_0_75: "Longslit 0.75 arcsec",
    LONG_SLIT_1_00: "Longslit 1.00 arcsec",
    LONG_SLIT_1_50: "Longslit 1.50 arcsec",
    LONG_SLIT_2_00: "Longslit 2.00 arcsec",
    LONG_SLIT_5_00: "Longslit 5.00 arcsec",
    IFU2_SLITS: "IFU2 Slits",
    IFU_BLUE: "IFU Blue",
    IFU_RED: "IFU red",
  };

  static gmosSouthBuiltinFpu = {
    NS1: "NS1",
    NS2: "NS2",
    NS3: "NS3",
    NS4: "NS4",
    NS5: "NS5",
    LONG_SLIT_0_25: "Longslit 0.25 arcsec",
    LONG_SLIT_0_50: "Longslit 0.50 arcsec",
    LONG_SLIT_0_75: "Longslit 0.75 arcsec",
    LONG_SLIT_1_00: "Longslit 1.00 arcsec",
    LONG_SLIT_1_50: "Longslit 1.50 arcsec",
    LONG_SLIT_2_00: "Longslit 2.00 arcsec",
    LONG_SLIT_5_00: "Longslit 5.00 arcsec",
    IFU2_SLITS: "IFU2 Slits",
    IFU_BLUE: "IFU Blue",
    IFU_RED: "IFU Red",
    IFU_NS2_SLITS: "IFU NS2 Slits",
    IFU_NS_BLUE: "IFU NS Blue",
    IFU_NS_RED: "IFU NS Red",
  };
  static gmosImagingOffsetVariant = {
    PRE_IMAGING: "pre-imaging",
    GROUPED: "grouped",
    INTERLEAVED: "interleaved",
  };

  static gmosImagingOffsets = {
    NONE: "No Offset",
    ENUMERATED: "explicit",
    UNIFORM: "uniform",
    SPIRAL: "spiral",
    RANDOM: "random",
  };

  static gmosImagingWavelengthOrder = {
    INCREASING: "increasing",
    DECREASING: "decreasing",
  };

  /** GPP keys the imaging variant payload by name, not by display label. */
  static gmosImagingVariantDataKeys = {
    PRE_IMAGING: "preImaging",
    GROUPED: "grouped",
    INTERLEAVED: "interleaved",
  };

  /** GPP sends the pre-imaging offsets as four named keys, not as a list. */
  static gmosImagingPreImagingOffsetKeys = [
    "offset1",
    "offset2",
    "offset3",
    "offset4",
  ];

  /**
   * Exposure time mode labels. These travel to the backend as-is:
   * `ExposureModeSerializer.exposureModeSelect` validates them literally, so
   * changing a label here also changes the payload.
   */
  static exposureTimeMode = {
    SIGNAL_TO_NOISE: "Signal / Noise",
    TIME_AND_COUNT: "Time & Count",
  };

  /** Guide state values; toggled with a checkbox, so they have no labels. */
  static guideState = {
    ENABLED: "ENABLED",
    DISABLED: "DISABLED",
  };

  static gmosReadMode = {
    FAST: "Fast",
    SLOW: "Slow",
  };

  static instrument = {
    GMOS_SOUTH: "GMOS South",
    GMOS_NORTH: "GMOS North",
  };
}
