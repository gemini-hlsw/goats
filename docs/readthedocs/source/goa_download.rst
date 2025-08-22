.. _goa_download:

Download Gemini data
--------------------

Users can download Gemini data directly on the GOATS interface, without needing to visit the Gemini Observatory Archive (GOA) website. GOATS allows download of both public as well as proprietary data that a user has access to. To facilitate the latter, users will need to input their GOA credentials (see the :ref:`Managing Credential video <managing_credential>`). 

GOATS supports asynchronous download of the data using modern software technologies such as Redis and Dramatiq for managing background tasks. One thus need not wait for a download to complete to perform other operations on GOATS. 

.. note::  
   The default download will include both the science as well as the calibration files and the files will be automatically decompressed, as opposed to manually downloading from the Gemini archive [#f1]_. 

   The downloaded data are stored in the **data** subfolder of the **GOATS** folder (see :ref:`install`) unless a separate data directory option was provided during installation with the ``-m`` flag (:ref:`goats_cli`).  

.. _goa-video:
.. video:: _static/goa_download.mp4
   :alt: Automated download of Gemini data on GOATS 
   :muted:
   :width: 80%



.. rubric:: Footnotes

.. [#f1] For Gemini GHOST data, the files will also be de-bundled automatically when downloading on GOATS, which will make it easier for users to handle the data.   

