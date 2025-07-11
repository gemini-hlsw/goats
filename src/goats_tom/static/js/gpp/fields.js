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
 * colSize   : "col-"        - bootstrap col classes (default "col-sm-6")
 * handler   : function      - handler to call on the data
 *
 * Notes
 * -----
 * - If `path` resolves undefined or null it is skipped automatically.
 */
const SHARED_FIELDS = [
  // Details section.
  { section: "Details" },
  { labelText: "Instrument", path: "instrument", id: "instrument" },
  { labelText: "ID", path: "id", id: "id" },
  { labelText: "Reference", path: "reference", id: "reference" },
  { labelText: "Title", path: "title", id: "title" },
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
    labelText: "Position Angle",
    path: "posAngleConstraint.angle.degrees",
    suffix: "deg",
    type: "number",
    id: "posAngle",
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
  },
  // Brightnesses section.
  { section: "Brightnesses" },
  {
    path: "targetEnvironment.firstScienceTarget.sourceProfile.point.bandNormalized.brightnesses",
    handler: "handleBrightnessInputs",
    id: "brightness",
    colSize: "col-md-6",
    type: "number",
  },
  // Constraint section.
  { section: "Constraint Set" },
  {
    labelText: "Image Quality",
    path: "constraintSet.imageQuality",
    id: "imageQuality",
  },
  {
    labelText: "Cloud Extinction",
    path: "constraintSet.cloudExtinction",
    id: "cloudExtinction",
  },
  {
    labelText: "Sky Background",
    path: "constraintSet.skyBackground",
    id: "skyBackground",
  },
  { labelText: "Water Vapor", path: "constraintSet.waterVapor", id: "waterVapor" },
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
    labelText: "Grating",
    path: "observingMode.gmosNorthLongSlit.grating",
    id: "grating",
  },
  { labelText: "Filter", path: "observingMode.gmosNorthLongSlit.filter", id: "filter" },
  { labelText: "FPU", path: "observingMode.gmosNorthLongSlit.fpu", id: "fpu" },
  {
    labelText: "Spatial Offsets",
    path: "observingMode.gmosNorthLongSlit.spatialOffsets",
    id: "spatialOffsets",
    suffix: "arcsec",
    handler: "handleSpatialOffsetsList",
  },
  {
    labelText: "Central Wavelength",
    path: "observingMode.gmosNorthLongSlit.centralWavelength.nanometers",
    id: "centralWavelength",
    suffix: "nm",
  },
  {
    labelText: "Grating",
    path: "observingMode.gmosNorthLongSlit.grating",
    id: "grating",
  },
  { labelText: "X Binning", path: "observingMode.gmosNorthLongSlit.xBin", id: "xBin" },
  { labelText: "Y Binning", path: "observingMode.gmosNorthLongSlit.yBin", id: "yBin" },
  {
    labelText: "Read Mode",
    path: "observingMode.gmosNorthLongSlit.ampReadMode",
    id: "ampReadMode",
  },
  { labelText: "ROI", path: "observingMode.gmosNorthLongSlit.roi", id: "roi" },
];

const GMOS_SOUTH_LONG_SLIT_FIELDS = [
  { section: "Configuration" },
  {
    labelText: "Grating",
    path: "observingMode.gmosSouthLongSlit.grating",
    id: "grating",
  },
  { labelText: "Filter", path: "observingMode.gmosSouthLongSlit.filter", id: "filter" },
  { labelText: "FPU", path: "observingMode.gmosSouthLongSlit.fpu", id: "fpu" },
  {
    labelText: "Spatial Offsets",
    path: "observingMode.gmosSouthLongSlit.spatialOffsets",
    id: "spatialOffsets",
    suffix: "arcsec",
    handler: "handleSpatialOffsetsList",
  },
  {
    labelText: "Central Wavelength",
    path: "observingMode.gmosSouthLongSlit.centralWavelength.nanometers",
    id: "centralWavelength",
    suffix: "nm",
  },
  {
    labelText: "Grating",
    path: "observingMode.gmosSouthLongSlit.grating",
    id: "grating",
  },
  { labelText: "X Binning", path: "observingMode.gmosSouthLongSlit.xBin", id: "xBin" },
  { labelText: "Y Binning", path: "observingMode.gmosSouthLongSlit.yBin", id: "yBin" },
  {
    labelText: "Read Mode",
    path: "observingMode.gmosSouthLongSlit.ampReadMode",
    id: "ampReadMode",
  },
  { labelText: "ROI", path: "observingMode.gmosSouthLongSlit.roi", id: "roi" },
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
