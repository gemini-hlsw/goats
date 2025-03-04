.. _targets:

Define targets
--------------

There are two ways to select and store targets on the GOATS interface. Each stored target gets a dedicated page.  

1. Brokers: This may be mostly relevant for users conducting time-domain and multimessenger follow-up. Users can select and store targets from a broker available in GOATS. In particular, we provide enhanced support for NOIRLab's |ANTARES| broker, whereby users can directly leverage the ANTARES portal to search and select targets and transfer the information with the click of a browser-extension button. This extension is named ``antares2goats``. Currently, ``antares2goats`` is available for Chrome and Firefox browsers. Follow the video below for installing (a one-off process) and using this extension to select and transfer a target information from ANTARES to GOATS for Firefox. 

.. note::  
   For further information, including installation for the different browsers, refer to the :doc:`antares2goats/index` documentation. 

   

.. _antares2goats-video:
.. video:: _static/antares2goats.mp4
   :alt: antares2goats target selection 
   :muted:
   :width: 80%

|

2. Create targets manually: Users can also manually input the target information to store it on GOATS or upload a CSV file in case of multiple targets. Additionally, one can also retrieve the target information from a catalog, such as SIMBAD, NED, JPL Horizons, etc. 

.. _targets-video:
.. video:: _static/create_targets.mp4
   :alt: Manual target creation 
   :muted:
   :width: 80%

|

As can be seen in the videos, the dedicated page of a given target has multiple tabs for various operations: 

- **Observe** for triggering follow-up of this target on telescope facilities, in particular Gemini 
- **Observations** for listing triggered observations as well as to add any other past observations of the target   
- **Manage Data** for listing data from all observations of the target as well as uploading additional data files
- **Manage Groups** for listing the group(s) that the target belongs to, if the user has grouped it with other targets 
- **Photometry** for viewing photometry data of the target 
- **Spectroscopy** for viewing spectroscopy data of the target
