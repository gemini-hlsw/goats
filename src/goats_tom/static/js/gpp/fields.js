/**
 * Fields map
 * ----------
 * section   : string        - render header
 * id        : string        – required DOM id for the control
 * path      : string        - dotted route to the value in the JSON
 * labelText : string        - label text (default = last segment of path)
 * element   : "input"|"textarea" (default "input")
 * type      : any <input type=""> (default "text")
 * prefix    : string        - input-group addon on the left
 * suffix    : string        - input-group addon on the right
 * colSize   : "col-"        - bootstrap col classes (default "col-lg-6")
 * handler   : function      - handler to call on the data
 * lookup    : object        - dictionary map to convert machine value to human-readable label
 * formatter : function      - function to format the looked-up value before display
 * display   : boolean       - force the field to render even if the value is null or undefined
 *
 * Notes
 * -----
 * - If `path` resolves undefined or null it is skipped automatically.
 */
const SHARED_FIELDS = [
  // Details section.
  { section: "Details" },
  { labelText: "ID", path: "id", id: "id", display: true, colSize: "col-lg-6" },
  {
    labelText: "Reference",
    path: "reference.label",
    id: "reference",
    display: true,
    colSize: "col-lg-6",
  },
  {
    labelText: "State",
    path: "execution.executionState",
    id: "executionState",
    display: true,
    colSize: "col-lg-6",
    formatter: Formatters.titleCaseFromUnderscore,
  },
  {
    labelText: "Title",
    path: "title",
    id: "title",
    display: true,
    colSize: "col-lg-6",
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
    labelText: "\u03BC RA",
    path: "targetEnvironment.firstScienceTarget.sidereal.properMotion.ra.milliarcsecondsPerYear",
    suffix: "mas/year",
    type: "number",
    id: "uRa",
  },
  {
    labelText: "\u03BC Dec",
    path: "targetEnvironment.firstScienceTarget.sidereal.properMotion.dec.milliarcsecondsPerYear",
    suffix: "mas/year",
    type: "number",
    id: "uDec",
  },
  { labelText: "Science Band", path: "scienceBand" },
  {
    labelText: "Observer Notes",
    path: "observerNotes",
    element: "textarea",
    colSize: "col-12",
    id: "observerNotes",
    display: true,
  },
  // Brightnesses section.
  { section: "Brightnesses" },
  {
    path: "targetEnvironment.firstScienceTarget.sourceProfile.point.bandNormalized.brightnesses",
    handler: "handleBrightnessInputs",
    id: "brightness",
    type: "number",
    colSize: "col-xxl-6",
  },
  // Constraint section.
  { section: "Constraint Set" },
  {
    labelText: "Image Quality",
    path: "constraintSet.imageQuality",
    id: "imageQuality",
    lookup: Lookups.imageQuality,
  },
  {
    labelText: "Cloud Extinction",
    path: "constraintSet.cloudExtinction",
    id: "cloudExtinction",
    lookup: Lookups.cloudExtinction,
  },
  {
    labelText: "Sky Background",
    path: "constraintSet.skyBackground",
    id: "skyBackground",
    formatter: Formatters.capitalizeFirstLetter,
  },
  {
    labelText: "Water Vapor",
    path: "constraintSet.waterVapor",
    id: "waterVapor",
    formatter: Formatters.titleCaseFromUnderscore,
  },
  {
    labelText: "Airmass Min",
    path: "constraintSet.elevationRange.airMass.min",
    id: "airmassMin",
  },
  {
    labelText: "Airmass Max",
    path: "constraintSet.elevationRange.airMass.max",
    id: "airmassMax",
  },
];

const GMOS_NORTH_LONG_SLIT_FIELDS = [
  { section: "Configuration" },
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
    path: "observingMode.gmosSouthLongSlit.wavelengthDithers",
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
    labelText: "\u03BB for S/N",
    path: "scienceRequirements.exposureTimeMode.signalToNoise.at.nanometers",
    id: "wavelengthForSn",
    suffix: "nm",
  },
  {
    labelText: "S/N",
    path: "scienceRequirements.exposureTimeMode.signalToNoise.value",
    id: "sn",
  },
  {
    labelText: "\u03BB for Time & Count",
    path: "scienceRequirements.exposureTimeMode.timeAndCount.at.nanometers",
    id: "wavelengthForTimeAndCount",
    suffix: "nm",
  },
  {
    labelText: "Exposure Time",
    path: "scienceRequirements.exposureTimeMode.timeAndCount.time.seconds",
    id: "exposureTime",
    suffix: "seconds",
  },
  {
    labelText: "Exposure Count",
    path: "scienceRequirements.exposureTimeMode.timeAndCount.count",
    id: "exposureCount",
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
  { section: "Configuration" },
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
    labelText: "\u03BB for S/N",
    path: "scienceRequirements.exposureTimeMode.signalToNoise.at.nanometers",
    id: "wavelengthForSn",
    suffix: "nm",
  },
  {
    labelText: "S/N",
    path: "scienceRequirements.exposureTimeMode.signalToNoise.value",
    id: "sn",
  },
  {
    labelText: "\u03BB for Time & Count",
    path: "scienceRequirements.exposureTimeMode.timeAndCount.at.nanometers",
    id: "wavelengthForTimeAndCount",
    suffix: "nm",
  },
  {
    labelText: "Exposure Time",
    path: "scienceRequirements.exposureTimeMode.timeAndCount.time.seconds",
    id: "exposureTime",
    suffix: "seconds",
  },
  {
    labelText: "Number of Exposures",
    path: "scienceRequirements.exposureTimeMode.timeAndCount.count",
    id: "numberOfExposures",
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
