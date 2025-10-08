/**
 * Field Metadata Schema
 * ---------------------
 * Each field definition supports the following properties:
 *
 * Core Attributes:
 * ----------------
 * section     : string
 *     Section header under which this field will be rendered.
 *
 * id          : string (required)
 *     Unique DOM ID for the input control.
 *
 * path        : string
 *     Dot-separated path to the field in the JSON data.
 *
 * labelText   : string (optional)
 *     Custom label text (defaults to the last segment of `path`).
 *
 * element     : "input" | "textarea" | "select" (default: "input")
 *     HTML element type to use.
 *
 * options     : array (optional)
 *    For select elements, the list of options to display.
 *
 * type        : string (default: "text")
 *     Input type attribute (e.g., "number", "text", etc.).
 *
 * Input Decorations:
 * ------------------
 * prefix      : string (optional)
 *     Adds a Bootstrap input-group prefix before the input.
 *
 * suffix      : string (optional)
 *     Adds a Bootstrap input-group suffix after the input.
 *
 * colSize     : string (default: "col-lg-6")
 *     Bootstrap grid column class for layout.
 *
 * Behavior and Display:
 * ---------------------
 * handler     : function(data: object): void (optional)
 *     Called when input changes to handle custom behavior.
 *
 * lookup      : object (optional)
 *     Mapping of machine value → display label.
 *
 * formatter   : function(value: any): string (optional)
 *     Formats the displayed value (used with `lookup`).
 *
 * showIfMode  : "normal" | "too" | "both" (default: "both")
 *     Determines visibility based on observation mode.
 *
 * readOnly    : boolean (default: false)
 *     Whether the input is disabled (applies to "normal" mode only).
 */
const SHARED_FIELDS = [
  // Details section.
  { section: "Details" },
  {
    labelText: "ID",
    path: "id",
    id: "id",
    colSize: "col-lg-6",
    showIfMode: "normal",
    readOnly: true,
  },
  {
    labelText: "Reference",
    path: "reference.label",
    id: "reference",
    colSize: "col-lg-6",
    showIfMode: "normal",
    readOnly: true,
  },
  {
    labelText: "Right Ascension",
    path: "targetEnvironment.firstScienceTarget.sidereal.ra.hms",
    id: "rightAscension",
    showIfMode: "normal",
    readOnly: true,
    suffix: "hms",
    colSize: "col-lg-6",
  },
  {
    labelText: "Declination",
    path: "targetEnvironment.firstScienceTarget.sidereal.dec.dms",
    id: "declination",
    showIfMode: "normal",
    readOnly: true,
    suffix: "dms",
    colSize: "col-lg-6",
  },
  {
    labelText: "State",
    path: "execution.executionState",
    id: "executionState",
    colSize: "col-lg-6",
    formatter: Formatters.titleCaseFromUnderscore,
    showIfMode: "both",
    readOnly: true,
    options: ["Ready", "Defined", "Inative"],
    element: "select",
  },
  {
    labelText: "Title",
    path: "title",
    id: "title",
    colSize: "col-lg-6",
    showIfMode: "normal",
    readOnly: true,
  },
  {
    labelText: "Radial Velocity",
    path: "targetEnvironment.firstScienceTarget.sidereal.radialVelocity.kilometersPerSecond",
    suffix: "km/s",
    type: "number",
    id: "radialVelocity",
    showIfMode: "both",
  },
  {
    labelText: "Parallax",
    path: "targetEnvironment.firstScienceTarget.sidereal.parallax.milliarcseconds",
    suffix: "mas",
    type: "number",
    id: "parallax",
    showIfMode: "both",
  },
  {
    labelText: "\u03BC Right Ascension",
    path: "targetEnvironment.firstScienceTarget.sidereal.properMotion.ra.milliarcsecondsPerYear",
    suffix: "mas/year",
    type: "number",
    id: "uRa",
    showIfMode: "both",
    colSize: "col-lg-6",
  },
  {
    labelText: "\u03BC Declination",
    path: "targetEnvironment.firstScienceTarget.sidereal.properMotion.dec.milliarcsecondsPerYear",
    suffix: "mas/year",
    type: "number",
    id: "uDec",
    showIfMode: "both",
    colSize: "col-lg-6",
  },
  {
    labelText: "Science Band",
    path: "scienceBand",
    colSize: "col-lg-6",
    showIfMode: "both",
    readOnly: true,
  },
  {
    labelText: "Observer Notes",
    path: "observerNotes",
    element: "textarea",
    colSize: "col-12",
    id: "observerNotes",
    showIfMode: "both",
  },
  // Source profile section.
  {
    path: "targetEnvironment.firstScienceTarget.sourceProfile.point.bandNormalized.sed",
    handler: "handleSourceProfile",
  },
  // Brightnesses section.
  { section: "Brightnesses" },
  {
    path: "targetEnvironment.firstScienceTarget.sourceProfile.point.bandNormalized.brightnesses",
    handler: "handleBrightnessInputs",
  },
  // Constraint section.
  { section: "Constraint Set" },
  {
    labelText: "Image Quality",
    path: "constraintSet.imageQuality",
    id: "imageQuality",
    lookup: Lookups.imageQuality,
    element: "select",
    options: [
      "< 0.10 arcsec",
      "< 0.20 arcsec",
      "< 0.30 arcsec",
      "< 0.40 arcsec",
      "< 0.60 arcsec",
      "< 0.80 arcsec",
      "< 1.00 arcsec",
      "< 1.50 arcsec",
      "< 2.00 arcsec",
    ],
    showIfMode: "both",
  },
  {
    labelText: "Cloud Extinction",
    path: "constraintSet.cloudExtinction",
    id: "cloudExtinction",
    lookup: Lookups.cloudExtinction,
    options: [
      "0.00 mag",
      "< 0.10 mag",
      "< 0.30 mag",
      "< 0.50 mag",
      "< 1.00 mag",
      "< 2.00 mag",
      "< 3.00 mag",
    ],
    element: "select",
    showIfMode: "both",
  },
  {
    labelText: "Sky Background",
    path: "constraintSet.skyBackground",
    id: "skyBackground",
    formatter: Formatters.capitalizeFirstLetter,
    options: ["Darkest", "Dark", "Gray", "Bright"],
    element: "select",
    showIfMode: "both",
  },
  {
    labelText: "Water Vapor",
    path: "constraintSet.waterVapor",
    id: "waterVapor",
    formatter: Formatters.titleCaseFromUnderscore,
    options: ["Very Dry", "Dry", "Median", "Wet"],
    element: "select",
    showIfMode: "both",
  },
  {
    path: "constraintSet.elevationRange",
    showIfMode: "both",
    handler: "handleElevationRange",
  },
  { section: "Configuration" },
  {
    labelText: "Position Angle",
    id: "posAngleConstraint",
    path: "posAngleConstraint",
    handler: "handlePosAngleConstraint",
    options: [
      { labelText: "Fixed", value: "FIXED" },
      { labelText: "Allow 180° Flip", value: "ALLOW_180_FLIP" },
      { labelText: "Average Parallactic", value: "AVERAGE_PARALLACTIC" },
      { labelText: "Parallactic Override", value: "PARALLACTIC_OVERRIDE" },
      { labelText: "Unconstrained", value: "UNCONSTRAINED" },
    ],
    element: "select",
    value: "FIXED",
    suffix: "°E of N",
  },
];

const GMOS_NORTH_LONG_SLIT_FIELDS = [
  {
    labelText: "Instrument",
    path: "instrument",
    id: "instrument",
    lookup: Lookups.instrument,
  },
  {
    labelText: "Position Angle",
    path: "posAngleConstraint.angle.degrees",
    suffix: "deg",
    type: "number",
    id: "posAngle",
  },
  {
    labelText: "Grating",
    path: "observingMode.gmosNorthLongSlit.grating",
    id: "grating",
    formatter: Formatters.replaceUnderscore,
  },
  { labelText: "Filter", path: "observingMode.gmosNorthLongSlit.filter", id: "filter" },
  {
    labelText: "FPU",
    path: "observingMode.gmosNorthLongSlit.fpu",
    id: "fpu",
    lookup: Lookups.gmosNorthBuiltinFpu,
    colSize: "col-lg-6",
  },
  {
    labelText: "Spatial Offsets",
    path: "observingMode.gmosNorthLongSlit.spatialOffsets",
    id: "spatialOffsets",
    suffix: "arcsec",
    handler: "handleSpatialOffsetsList",
    colSize: "col-lg-6",
  },
  {
    labelText: "\u03BB Dithers",
    path: "observingMode.gmosNorthLongSlit.wavelengthDithers",
    id: "wavelengthDithers",
    suffix: "nm",
    handler: "handleWavelengthDithersList",
    colSize: "col-lg-6",
  },
  {
    labelText: "Central \u03BB",
    path: "observingMode.gmosNorthLongSlit.centralWavelength.nanometers",
    id: "centralWavelength",
    suffix: "nm",
  },
  {
    labelText: "Resolution",
    path: "scienceRequirements.spectroscopy.resolution",
    id: "resolution",
  },
  {
    labelText: "\u03BB Interval",
    path: "scienceRequirements.spectroscopy.wavelengthCoverage",
    id: "wavelengthCoverage",
  },
  {
    labelText: "Exposure Mode",
    path: "scienceRequirements.exposureTimeMode",
    id: "exposureMode",
    handler: "handleExposureMode",
  },
  {
    labelText: "X Binning",
    path: "observingMode.gmosNorthLongSlit.xBin",
    id: "xBin",
    lookup: Lookups.gmosBinning,
  },
  {
    labelText: "Y Binning",
    path: "observingMode.gmosNorthLongSlit.yBin",
    id: "yBin",
    lookup: Lookups.gmosBinning,
  },
  {
    labelText: "Read Mode",
    path: "observingMode.gmosNorthLongSlit.ampReadMode",
    id: "ampReadMode",
    formatter: Formatters.capitalizeFirstLetter,
  },
  {
    labelText: "ROI",
    path: "observingMode.gmosNorthLongSlit.roi",
    id: "roi",
    lookup: Lookups.gmosRoi,
  },
];

const GMOS_SOUTH_LONG_SLIT_FIELDS = [
  {
    labelText: "Instrument",
    path: "instrument",
    id: "instrument",
    lookup: Lookups.instrument,
  },
  {
    labelText: "Position Angle",
    path: "posAngleConstraint.angle.degrees",
    suffix: "deg",
    type: "number",
    id: "posAngle",
  },
  {
    labelText: "Grating",
    path: "observingMode.gmosSouthLongSlit.grating",
    id: "grating",
    formatter: Formatters.replaceUnderscore,
  },
  { labelText: "Filter", path: "observingMode.gmosSouthLongSlit.filter", id: "filter" },
  {
    labelText: "FPU",
    path: "observingMode.gmosSouthLongSlit.fpu",
    id: "fpu",
    lookup: Lookups.gmosSouthBuiltinFpu,
    colSize: "col-lg-6",
  },
  {
    labelText: "Spatial Offsets",
    path: "observingMode.gmosSouthLongSlit.spatialOffsets",
    id: "spatialOffsets",
    suffix: "arcsec",
    handler: "handleSpatialOffsetsList",
    colSize: "col-lg-6",
  },
  {
    labelText: "\u03BB Dithers",
    path: "observingMode.gmosSouthLongSlit.wavelengthDithers",
    id: "wavelengthDithers",
    suffix: "nm",
    handler: "handleWavelengthDithersList",
    colSize: "col-lg-6",
  },
  {
    labelText: "Central \u03BB",
    path: "observingMode.gmosSouthLongSlit.centralWavelength.nanometers",
    id: "centralWavelength",
    suffix: "nm",
  },
  {
    labelText: "Resolution",
    path: "scienceRequirements.spectroscopy.resolution",
    id: "resolution",
  },
  {
    labelText: "\u03BB Interval",
    path: "scienceRequirements.spectroscopy.wavelengthCoverage",
    id: "wavelengthCoverage",
  },
  {
    labelText: "Exposure Mode",
    path: "scienceRequirements.exposureTimeMode",
    id: "exposureMode",
    handler: "handleExposureMode",
  },
  {
    labelText: "X Binning",
    path: "observingMode.gmosSouthLongSlit.xBin",
    id: "xBin",
    lookup: Lookups.gmosBinning,
  },
  {
    labelText: "Y Binning",
    path: "observingMode.gmosSouthLongSlit.yBin",
    id: "yBin",
    lookup: Lookups.gmosBinning,
  },
  {
    labelText: "Read Mode",
    path: "observingMode.gmosSouthLongSlit.ampReadMode",
    id: "ampReadMode",
    formatter: Formatters.capitalizeFirstLetter,
  },
  {
    labelText: "ROI",
    path: "observingMode.gmosSouthLongSlit.roi",
    id: "roi",
    lookup: Lookups.gmosRoi,
  },
];

/**
 * Field configs
 * -------------
 * A lookup table that maps each supported observing mode to its corresponding list of
 * instrument-specific form field definitions.
 *
 * The shared/common fields (e.g. target name, constraints, etc.) are handled
 * separately. This table only contains fields that are unique to each observing mode's
 * instrument configuration.
 *
 * To support a new mode, simply add an entry to this object:
 * {
 *   MODE_NAME: [ ...fields ]
 * }
 */
const FIELD_CONFIGS = {
  GMOS_NORTH_LONG_SLIT: GMOS_NORTH_LONG_SLIT_FIELDS,
  GMOS_SOUTH_LONG_SLIT: GMOS_SOUTH_LONG_SLIT_FIELDS,
};
