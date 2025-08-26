.. _visualization:

Data management and visualization
---------------------------------

GOATS has various features allowing users to efficiently manage the observation data (see the video below). 

All the downloaded data from different observations for a given target from the facilities supported by GOATS are aggregated in the **Manage Data** page of the target (the data products for a specific observation are also available on the corresponding page of the observation). The data files are listed along with options to delete, open in JS9, etc. Additionally, users can use this page to upload data relevant to this target -- either FITS or CSV files. 

For Gemini data reduced with DRAGONS on GOATS, users should `add` the reduced data to `GOATS Data Products` on the DRAGONS reduction page (see the video below) to ensure that those products are accessible for other operations on GOATS like visualization, analysis, etc. 

Light curves and spectra of a given target can be visualized using the **Photometry** and **Spectroscopy** tabs. Users can choose the desired file(s) to display using the file selector. The plots are rendered using Plotly and users can avail various options to interact with the plots, such as panning, zooming, autoscaling, etc. GOATS also allows users to edit the axis label and plot titles as well as manually adjust the limits of the axes, if desired. 

.. _visualization-video:
.. video:: _static/visualization.mp4
   :alt: Data management and visualization on GOATS 
   :muted:
   :width: 80%
