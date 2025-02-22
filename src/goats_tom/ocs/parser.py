"""Module for OCSParser class, a specialized parser for handling XML data from
the Observation Control System (OCS).

This parser is designed to interpret and convert various XML response formats
from the OCS into structured Python dictionaries. It is capable of parsing data
related to sequences, telescope configurations, and observation database (ODB)
information.

Each method converts the XML data into a structured dictionary, facilitating
easier access and manipulation of the data in Python.
"""

__all__ = ["OCSParser"]

import xml.etree.ElementTree as ET
from typing import Any


class OCSParser:
    """Class to parse response from OCS."""

    def parse_sequence_response(self, xml_data: str) -> dict[str, Any]:
        """Parses the XML data of a sequence and converts it into a dictionary.

        Parameters
        ----------
        xml_data : `str`
            The XML data as a string.

        Returns
        -------
        `dict[str, Any]`
            A dictionary representation of the XML sequence data.

        """

        def parse_sequence_element(system_element: ET.Element) -> dict[str, Any]:
            """Parses an element of the XML into a dictionary.

            Parameters
            ----------
            system_element : `ET.Element`
                A "system" XML element.

            Returns
            -------
            `dict[str, Any]`
                A dictionary representation of the "system" element.

            """
            system_data = {}
            for param in system_element:
                # Check if the child element is a "param" tag.
                if param.tag == "param":
                    system_data[param.attrib["name"]] = param.attrib["value"]
            return system_data

        # Parse the XML data from the response.
        root = ET.fromstring(xml_data)

        # Initialize the dictionary to store parsed data.
        parsed_data = {"version": root.attrib.get("version", ""), "steps": {}}

        # Iterate over each "step" element found in the XML.
        for step in root.findall("step"):
            step_name = step.attrib.get("name", "")
            step_data = {}

            # Iterate over each "system" element within the step.
            for system in step.findall("system"):
                system_name = system.attrib.get("name", "")
                step_data[system_name] = parse_sequence_element(system)

            # Assign the processed data of this step to the corresponding step
            # in "parsed_data".
            parsed_data["steps"][step_name] = step_data

        return parsed_data

    def parse_coordinates_response(self, xml_data: str) -> dict[str, Any]:
        """Parses XML data of telescope configuration into a dictionary.

        Parameters
        ----------
        xml_data : `str`
            The XML data as a string.

        Returns
        -------
        `dict[str, Any]`
            A dictionary representation of the parsed XML data.

        """

        def parse_coordinates_element(element: ET.Element) -> dict[str, Any]:
            """Recursive helper function to parse an XML element.

            Parameters
            ----------
            element : `ET.Element`
                An XML element to parse.

            Returns
            -------
            `dict[str, Any]`
                A dictionary representation of the XML element.

            """
            # For "param" elements, return a dictionary with its name and
            # value.
            if element.tag == "param":
                return {element.attrib["name"]: element.attrib.get("value", "")}

            parsed_data = {}
            for child in element:
                if child.tag == "paramset":
                    # Determine the key using "type" and "name" attributes.
                    # If "type" is missing, use "name" as the key.
                    key = child.attrib.get("type") or child.attrib.get("name", "")
                    if "name" in child.attrib and "type" in child.attrib:
                        key = f"{key}_{child.attrib['name']}"

                    # Recursively parse nested "paramset" elements.
                    child_data = parse_coordinates_element(child)
                    parsed_data[key] = child_data
                elif child.tag == "param":
                    # Update parsed data with parsed "param" elements.
                    child_data = parse_coordinates_element(child)
                    parsed_data.update(child_data)

            return parsed_data

        # Parse the XML string into an ElementTree object and get the root.
        root = ET.fromstring(xml_data)

        parsed_dict = {}
        for paramset in root.findall("paramset"):
            # Use "type" or "name" as the key for each "paramset".
            key = paramset.attrib.get("type") or paramset.attrib.get("name", "")
            parsed_dict[key] = parse_coordinates_element(paramset)

        return parsed_dict

    def parse_odb_response(self, xml_data: str) -> dict[str, Any]:
        """Parses the XML data of program information.

        Parameters
        ----------
        xml_data : `str`
            The XML data as a string.

        Returns
        -------
        `dict[str, Any]`
            A dictionary representation of the parsed XML program data.

        """

        def parse_odb_element(element: ET.Element) -> Any:
            """Recursively parses an XML element into a dictionary.

            Parameters
            ----------
            element : `ET.Element`
                An XML element to parse.

            Returns
            -------
            `Any`
                A XML element.

            """
            parsed = {}
            # Consolidate text elements directly
            if element.text and element.text.strip():
                return element.text.strip()

            for child in element:
                child_parsed = parse_odb_element(child)
                if child.tag in parsed:
                    # Handle repeated elements as lists
                    if not isinstance(parsed[child.tag], list):
                        parsed[child.tag] = [parsed[child.tag]]
                    parsed[child.tag].append(child_parsed)
                else:
                    parsed[child.tag] = child_parsed

            return parsed

        root = ET.fromstring(xml_data)

        # Assuming the root is "queryResult", and the first child is "programs"
        # which contains a single "program" element.
        program_element = root.find("./programs/program")
        if program_element is not None:
            return parse_odb_element(program_element)
        else:
            return {}
