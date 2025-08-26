.. _dragons:

Reduce Gemini data with DRAGONS
-------------------------------

One of the powerful features that GOATS offers is the functionality to reduce Gemini data. This is accomplished by fully integrating the modern Python-based data reduction software of Gemini---|DRAGONS|---into GOATS, in fact, transforming DRAGONS into a web application. 

With this integration, GOATS also includes several nifty features making DRAGONS reduction more user-friendly than using the native DRAGONS API or command line. The features include: 

- Automated sorting of files into observation types (science files, calibration files like bias, flat, arc, etc.) 
- Option to further group and/or filter files within a given observation type
- Access to the available reduction recipes for each observation type, along with the documentation
- Functionality to customize the reduction code directly on the GOATS interface
- Option to view, add, remove processed calibration files
- Option to view, delete reduced science files as well as save as `GOATS Data Products`. The latter enables using the files for other operations on GOATS like analysis, uploading to Astro Data Lab, etc. 
- Option to review the history of a previous run of DRAGONS for a given data set

The movie below shows a quick demonstration of DRAGONS reduction on GOATS. 

.. note::
   GOATS supports all the instruments and modes that DRAGONS operates on. 


.. _dragons-video:
.. video:: _static/goats_dragons.mp4
   :alt: DRAGONS data reduction on GOATS 
   :muted:
   :width: 80%


