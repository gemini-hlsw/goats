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
 *    Each option can be a string (used for both value and label) or an object
 *    with `labelText`, `value`, and `disabled` properties.
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
 * readOnly    : "normal" | "too" | "both" (optional)
 *     Whether the input is disabled (if omitted, then not read-only).
 */
const SHARED_FIELDS = [
  // Details section.
  { section: "Details" },
  {
    path: "id",
    element: "input",
    type: "hidden",
    id: "hiddenObservationId",
  },
  {
    path: "reference.label",
    element: "input",
    type: "hidden",
    id: "hiddenReferenceLabel",
  },
  {
    path: "targetEnvironment.firstScienceTarget.id",
    type: "hidden",
    element: "input",
    id: "hiddenTargetId",
  },
  {
    path: "observingMode.mode",
    element: "input",
    type: "hidden",
    id: "hiddenObservingMode",
  },
  {
    labelText: "ID",
    path: "id",
    id: "id",
    colSize: "col-lg-6",
    showIfMode: "normal",
    readOnly: "normal",
  },
  {
    labelText: "Reference",
    path: "reference.label",
    id: "reference",
    colSize: "col-lg-6",
    showIfMode: "normal",
    readOnly: "normal",
  },
  {
    labelText: "State",
    path: "workflow.value.state",
    id: "workflowState",
    colSize: "col-12",
    element: "select",
    options: [
      { value: "READY", labelText: "Ready" },
      { value: "DEFINED", labelText: "Defined" },
      { value: "INACTIVE", labelText: "Inactive" },
      { value: "ONGOING", labelText: "Ongoing", disabled: true },
      { value: "COMPLETED", labelText: "Completed", disabled: true },
      { value: "UNAPPROVED", labelText: "Unapproved", disabled: true },
      { value: "UNDEFINED", labelText: "Undefined", disabled: true },
    ],
  },
  {
    labelText: "Right Ascension",
    path: "targetEnvironment.firstScienceTarget.sidereal.ra.hms",
    id: "rightAscension",
    showIfMode: "normal",
    readOnly: "normal",
    suffix: "hms",
    colSize: "col-lg-6",
  },
  {
    labelText: "Declination",
    path: "targetEnvironment.firstScienceTarget.sidereal.dec.dms",
    id: "declination",
    showIfMode: "normal",
    readOnly: "normal",
    suffix: "dms",
    colSize: "col-lg-6",
  },
  {
    labelText: "Title",
    path: "title",
    id: "title",
    colSize: "col-lg-6",
    showIfMode: "normal",
    readOnly: "normal",
  },
  {
    labelText: "Radial Velocity",
    path: "targetEnvironment.firstScienceTarget.sidereal.radialVelocity.kilometersPerSecond",
    suffix: "km/s",
    type: "number",
    id: "radialVelocity",
  },
  {
    labelText: "Parallax",
    path: "targetEnvironment.firstScienceTarget.sidereal.parallax.milliarcseconds",
    suffix: "mas",
    type: "number",
    id: "parallax",
  },
  {
    labelText: "μ Right Ascension",
    path: "targetEnvironment.firstScienceTarget.sidereal.properMotion.ra.milliarcsecondsPerYear",
    suffix: "mas/year",
    type: "number",
    id: "uRa",
    colSize: "col-lg-6",
  },
  {
    labelText: "μ Declination",
    path: "targetEnvironment.firstScienceTarget.sidereal.properMotion.dec.milliarcsecondsPerYear",
    suffix: "mas/year",
    type: "number",
    id: "uDec",
    colSize: "col-lg-6",
  },
  {
    path: "scienceBand",
    handler: "handleScienceBand",
    allocationsPath: "program.allocations",
    timeChargePath: "program.timeCharge",
  },
  {
    labelText: "Observer Notes",
    path: "observerNotes",
    element: "textarea",
    colSize: "col-12",
    id: "observerNotes",
  },
  // Source profile section.
  {
    path: "targetEnvironment.firstScienceTarget.sourceProfile",
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
    element: "select",
    options: [
      { value: "POINT_ONE", labelText: "< 0.10" },
      { value: "POINT_TWO", labelText: "< 0.20" },
      { value: "POINT_THREE", labelText: "< 0.30" },
      { value: "POINT_FOUR", labelText: "< 0.40" },
      { value: "POINT_SIX", labelText: "< 0.60" },
      { value: "POINT_EIGHT", labelText: "< 0.80" },
      { value: "ONE_POINT_ZERO", labelText: "< 1.00" },
      { value: "ONE_POINT_FIVE", labelText: "< 1.50" },
      { value: "TWO_POINT_ZERO", labelText: "< 2.00" },
      { value: "THREE_POINT_ZERO", labelText: "< 3.00" },
    ],
  },
  {
    labelText: "Cloud Extinction",
    path: "constraintSet.cloudExtinction",
    id: "cloudExtinction",
    options: [
      { value: "POINT_ONE", labelText: "< 0.10 mag" },
      { value: "POINT_THREE", labelText: "< 0.30 mag" },
      { value: "POINT_FIVE", labelText: "< 0.50 mag" },
      { value: "ONE_POINT_ZERO", labelText: "< 1.00 mag" },
      { value: "ONE_POINT_FIVE", labelText: "< 1.50 mag" },
      { value: "TWO_POINT_ZERO", labelText: "< 2.00 mag" },
      { value: "THREE_POINT_ZERO", labelText: "< 3.00 mag" },
    ],
    element: "select",
  },
  {
    labelText: "Sky Background",
    path: "constraintSet.skyBackground",
    id: "skyBackground",
    options: [
      { value: "DARK", labelText: "Dark" },
      { value: "GRAY", labelText: "Gray" },
      { value: "BRIGHT", labelText: "Bright" },
      { value: "DARKEST", labelText: "Darkest" },
    ],
    element: "select",
  },
  {
    labelText: "Water Vapor",
    path: "constraintSet.waterVapor",
    id: "waterVapor",
    options: [
      { value: "DRY", labelText: "Dry" },
      { value: "MEDIAN", labelText: "Median" },
      { value: "WET", labelText: "Wet" },
      { value: "VERY_DRY", labelText: "Very Dry" },
    ],
    element: "select",
  },
  {
    path: "constraintSet.elevationRange",
    handler: "handleElevationRange",
  },
  //Timing Windows section
  { section: "Scheduling Windows" },
  {
    path: "timingWindows",
    handler: "handleSchedulingWindowsInputs",
  },
  {
    section: "Finder Charts",
  },
  {
    path: "attachments",
    handler: "handleFinderCharts",
  },
  { section: "Configuration" },
  {
    labelText: "Position Angle",
    id: "posAngleConstraint",
    path: "posAngleConstraint",
    handler: "handlePosAngleConstraint",
    options: [
      { labelText: "Fixed", value: "FIXED" },
      { labelText: "Allow 180° Flip", value: "ALLOW_FLIP" },
      { labelText: "Average Parallactic", value: "AVERAGE_PARALLACTIC" },
      { labelText: "Parallactic Override", value: "PARALLACTIC_OVERRIDE" },
      { labelText: "Unbounded", value: "UNBOUNDED" },
    ],
    element: "select",
    value: "FIXED",
    suffix: "°E of N",
  },
];

/**
 * Generate imaging fields for GMOS North/South.
 * @param {string} site - "North" or "South"
 * @returns {array} Field definitions for imaging mode
 */
function generateGmosImagingFields(site) {
  const obsPath = `observingMode.gmos${site}Imaging`;
  const fpuLookup = Lookups[`gmos${site}BuiltinFpu`];

  return [
    {
      labelText: "Instrument",
      path: "instrument",
      id: "instrument",
      lookup: Lookups.instrument,
      readOnly: "both",
    },
    {
      labelText: "Position Angle",
      path: "posAngleConstraint.angle.degrees",
      suffix: "deg",
      type: "number",
      id: "posAngle",
      readOnly: "both",
    },
    {
      path: `${obsPath}.variant`,
      handler: "handleOffsetVariant",
    },
    {
      labelText: "Exposure Mode",
      path: `${obsPath}.filters`,
      id: "exposureMode",
      handler: "handleExposureMode",
      mode: "imaging",
      readOnly: true, /**only when handler is present  */
    },
    {
      labelText: "Binning",
      path: `${obsPath}.bin`,
      id: "bin",
      lookup: Lookups.gmosBinning,
      readOnly: "both",
    },
    {
      labelText: "Read Mode",
      path: `${obsPath}.ampReadMode`,
      id: "ampReadMode",
      formatter: Formatters.capitalizeFirstLetter,
      readOnly: "both",
    },
    {
      labelText: "ROI",
      path: `${obsPath}.roi`,
      id: "roi",
      lookup: Lookups.gmosRoi,
      readOnly: "both",
    },
  ];
}

/**
 * Generate long-slit fields for GMOS North/South.
 * @param {string} site - "North" or "South"
 * @returns {array} Field definitions for long-slit mode
 */
function generateGmosLongSlitFields(site) {
  const obsPath = `observingMode.gmos${site}LongSlit`;
  const fpuLookup = Lookups[`gmos${site}BuiltinFpu`];

  return [
    {
      labelText: "Instrument",
      path: "instrument",
      id: "instrument",
      lookup: Lookups.instrument,
      readOnly: "both",
    },
    {
      labelText: "Position Angle",
      path: "posAngleConstraint.angle.degrees",
      suffix: "deg",
      type: "number",
      id: "posAngle",
      readOnly: "both",
    },
    {
      labelText: "Grating",
      path: `${obsPath}.grating`,
      id: "grating",
      formatter: Formatters.replaceUnderscore,
      readOnly: "both",
    },
    {
      labelText: "Filter",
      path: `${obsPath}.filter`,
      id: "filter",
      readOnly: "both",
    },
    {
      labelText: "FPU",
      path: `${obsPath}.fpu`,
      id: "fpu",
      lookup: fpuLookup,
      colSize: "col-lg-6",
      readOnly: "both",
    },
    {
      labelText: "Spatial Offsets",
      path: `${obsPath}.offsets`,
      id: "spatialOffsets",
      suffix: "arcsec",
      handler: "handleSpatialOffsetsList",
      colSize: "col-lg-6",
    },
    {
      labelText: "λ Dithers",
      path: `${obsPath}.wavelengthDithers`,
      id: "wavelengthDithers",
      suffix: "nm",
      handler: "handleWavelengthDithersList",
      colSize: "col-lg-6",
    },
    {
      labelText: "Central λ",
      path: `${obsPath}.centralWavelength.nanometers`,
      id: "centralWavelength",
      suffix: "nm",
    },
    {
      labelText: "Exposure Mode",
      path: `${obsPath}.exposureTimeMode`,
      id: "exposureMode",
      handler: "handleExposureMode",
      mode: "longSlit"
    },
    {
      labelText: "X Binning",
      path: `${obsPath}.xBin`,
      id: "xBin",
      lookup: Lookups.gmosBinning,
      readOnly: "both",
    },
    {
      labelText: "Y Binning",
      path: `${obsPath}.yBin`,
      id: "yBin",
      lookup: Lookups.gmosBinning,
      readOnly: "both",
    },
    {
      labelText: "Read Mode",
      path: `${obsPath}.ampReadMode`,
      id: "ampReadMode",
      formatter: Formatters.capitalizeFirstLetter,
      readOnly: "both",
    },
    {
      labelText: "ROI",
      path: `${obsPath}.roi`,
      id: "roi",
      lookup: Lookups.gmosRoi,
      readOnly: "both",
    },
  ];
}

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
  GMOS_NORTH_IMAGING: generateGmosImagingFields("North"),
  GMOS_NORTH_LONG_SLIT: generateGmosLongSlitFields("North"),
  GMOS_SOUTH_IMAGING: generateGmosImagingFields("South"),
  GMOS_SOUTH_LONG_SLIT: generateGmosLongSlitFields("South"),
};
