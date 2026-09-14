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
 * datalist    : array of strings (optional)
 *     Suggested values rendered as a <datalist>. The input stays free-text.
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
    suffix: "hms",
    colSize: "col-lg-6",
    hasOverride: true,
    overridePlaceholder: "Using selected target's RA",
    targetValueKey: "ra",
  },
  {
    labelText: "Declination",
    path: "targetEnvironment.firstScienceTarget.sidereal.dec.dms",
    id: "declination",
    showIfMode: "normal",
    suffix: "dms",
    colSize: "col-lg-6",
    hasOverride: true,
    overridePlaceholder: "Using selected target's Dec",
    targetValueKey: "dec",
  },
  {
    labelText: "Title",
    path: "title",
    id: "title",
    colSize: "col-lg-6",
    showIfMode: "both",
    hasOverride: true,
    lockOverrideInMode: "too",
    overridePlaceholder: "Using selected target's name",
    targetValueKey: "name",
  },
  {
    labelText: "Discovery Survey",
    path: "subtitle",
    formatter: Formatters.discoverySurveyFromSubtitle,
    id: "discoverySurvey",
    colSize: "col-lg-6",
    showIfMode: "both",
    datalist: ["Rubin", "ZTF"],
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
    // Offered by GPP; the list below is what the form falls back to.
    optionsFrom: "imageQuality",
    element: "select",
    options: [
      { value: "POINT_ONE", labelText: "< 0.10" },
      { value: "POINT_TWO", labelText: "< 0.20" },
      { value: "POINT_THREE", labelText: "< 0.30" },
      { value: "POINT_FOUR", labelText: "< 0.40" },
      { value: "POINT_SIX", labelText: "< 0.60" },
      { value: "POINT_EIGHT", labelText: "< 0.80" },
      { value: "ONE_POINT_ZERO", labelText: "< 1.00" },
      { value: "ONE_POINT_TWO", labelText: "< 1.20" },
      { value: "ONE_POINT_FIVE", labelText: "< 1.50" },
      { value: "TWO_POINT_ZERO", labelText: "< 2.00" },
    ],
  },
  {
    labelText: "Cloud Extinction",
    path: "constraintSet.cloudExtinction",
    id: "cloudExtinction",
    // Offered by GPP; the list below is what the form falls back to.
    optionsFrom: "cloudExtinction",
    options: [
      { value: "ZERO", labelText: "0.00 mag" },
      { value: "POINT_ONE", labelText: "< 0.10 mag" },
      { value: "POINT_THREE", labelText: "< 0.30 mag" },
      { value: "POINT_FIVE", labelText: "< 0.50 mag" },
      { value: "ONE_POINT_ZERO", labelText: "< 1.00 mag" },
      { value: "TWO_POINT_ZERO", labelText: "< 2.00 mag" },
      { value: "THREE_POINT_ZERO", labelText: "< 3.00 mag" },
    ],
    element: "select",
  },
  {
    labelText: "Sky Background",
    path: "constraintSet.skyBackground",
    id: "skyBackground",
    // Offered by GPP; the list below is what the form falls back to.
    optionsFrom: "skyBackground",
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
    // Offered by GPP; the list below is what the form falls back to.
    optionsFrom: "waterVapor",
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
 * Turn a lookup map into `<select>` options.
 * @param {!Object<string, string>} lookup - Map of enum value to display label.
 * @returns {!Array<{value: string, labelText: string}>}
 */
function lookupOptions(lookup) {
  return Object.entries(lookup ?? {}).map(([value, labelText]) => ({
    value,
    labelText,
  }));
}

/**
 * Generate imaging fields for GMOS North/South.
 * @param {string} site - "North" or "South"
 * @returns {array} Field definitions for imaging mode
 */
function generateGmosImagingFields(site) {
  const obsPath = `observingMode.gmos${site}Imaging`;

  return [
    {
      // The filters the approved configuration fixed, as a comma separated
      // list: the exposure mode editor only carries the one on screen.
      path: `${obsPath}.filters`,
      element: "input",
      type: "hidden",
      id: "hiddenImagingFilters",
      showIfMode: "too",
      formatter: (filters) =>
        (filters ?? []).map((f) => f?.filter ?? f).join(","),
    },
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
      // Editable only when creating a ToO: the exposure mode is then applied to
      // every filter of the approved configuration.
      readOnly: "normal",
    },
    {
      labelText: "Binning",
      path: `${obsPath}.bin`,
      id: "bin",
      lookup: Lookups.gmosBinning,
      readOnly: "both",
      // GPP works this out from the configuration, so a ToO never asks for it.
      showIfMode: "normal",
    },
    {
      labelText: "Read Mode",
      path: `${obsPath}.ampReadMode`,
      id: "ampReadMode",
      formatter: Formatters.capitalizeFirstLetter,
      readOnly: "both",
      // GPP works this out from the configuration, so a ToO never asks for it.
      showIfMode: "normal",
    },
    {
      labelText: "ROI",
      path: `${obsPath}.roi`,
      id: "roi",
      lookup: Lookups.gmosRoi,
      readOnly: "both",
      // GPP works this out from the configuration, so a ToO never asks for it.
      showIfMode: "normal",
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
      // Creating from an approved configuration sends the disperser it fixed;
      // the visible field stays read-only, so it never travels on its own.
      path: `${obsPath}.grating`,
      element: "input",
      type: "hidden",
      id: "hiddenGrating",
      showIfMode: "too",
    },
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
      element: "select",
      // The filters GPP offers with the approved disperser.
      optionsFrom: "filter",
      readOnly: "normal",
    },
    {
      labelText: "FPU",
      path: `${obsPath}.fpu`,
      id: "fpu",
      element: "select",
      // The FPUs GPP offers with the approved disperser; updating an existing
      // observation falls back to the full list, just to display its value.
      optionsFrom: "fpu",
      options: lookupOptions(fpuLookup),
      colSize: "col-lg-6",
      readOnly: "normal",
      required: "too",
    },
    {
      labelText: "Spatial Offsets",
      path: obsPath,
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
      required: "too",
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
      // GPP works this out from the configuration, so a ToO never asks for it.
      showIfMode: "normal",
    },
    {
      labelText: "Y Binning",
      path: `${obsPath}.yBin`,
      id: "yBin",
      lookup: Lookups.gmosBinning,
      readOnly: "both",
      // GPP works this out from the configuration, so a ToO never asks for it.
      showIfMode: "normal",
    },
    {
      labelText: "Read Mode",
      path: `${obsPath}.ampReadMode`,
      id: "ampReadMode",
      formatter: Formatters.capitalizeFirstLetter,
      readOnly: "both",
      // GPP works this out from the configuration, so a ToO never asks for it.
      showIfMode: "normal",
    },
    {
      labelText: "ROI",
      path: `${obsPath}.roi`,
      id: "roi",
      lookup: Lookups.gmosRoi,
      readOnly: "both",
      // GPP works this out from the configuration, so a ToO never asks for it.
      showIfMode: "normal",
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
