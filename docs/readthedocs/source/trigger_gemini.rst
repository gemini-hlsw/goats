.. _trigger_gem:

Trigger Gemini 
--------------

GOATS will allow triggering of Gemini using the new Gemini Program Platform (GPP), which is the upgraded Observatory Control System of Gemini. 

Currently GPP is under active development. Its user-facing frontend, `Explore <https://explore.gemini.edu/>`_, which is a web-based application for preparing proposals and setting up observations is, however, already live. Connection between the GPP database and GOATS has been implemented such that users can now pull and save the observations defined for accepted proposals from their Explore account onto GOATS. Additionally, Explore is linked on the GOATS interface and users can directly launch the website from GOATS.  

Once GPP becomes ready to support target-of-opportunity (ToO) observations, users will then be able to set up ToO observations directly on GOATS for accepted programs and trigger Gemini, including automated triggering, i.e., without humans in the loop. 

Note that GOATS can also be used to trigger LCO and SOAR. See the details in :ref:`trigger_aeon`.

The video below highlights how users can interact with GPP (in its current state of development) using GOATS.  

.. _gpp-video:
.. video:: _static/gpp.mp4
   :alt: Integration of the Gemini Program Platform into GOATS 
   :muted:
   :width: 80%


