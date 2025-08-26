.. _trigger_aeon:

Triggering AEON facilities - LCO and SOAR
=========================================
The Astronomical Event Observatory Network (`AEON <https://noirlab.edu/science/observing-noirlab/aeon>`_), jointly founded by NOIRLab and LCO, is a collection of world-class telescopes capable of rapidly following up time-domain and multi-messenger alerts. Gemini Observatory along with SOAR and LCO were the earliest facilities to be integrated into AEON. 

The TOM Toolkit base library already includes support for triggering LCO and SOAR, and automatically retrieving observation data from the LCO archive. As GOATS is built upon the TOM Toolkit library, the aforementioned capabilities are available on GOATS as well, including enhancements for ease of use. For example, the Credential Manager of GOATS (:ref:`managing_credential`) allows users to easily store their LCO/SOAR API key on the GOATS interface instead of fiddling with configuration scripts. 

See the video below for how one can use GOATS for LCO and SOAR observations.

.. _aeon-video:
.. video:: ../_static/lco_soar.mp4
   :alt: Support for LCO and SOAR on GOATS
   :muted:
   :width: 80%