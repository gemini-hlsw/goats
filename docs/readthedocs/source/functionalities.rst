.. _functionalities:

How to use GOATS? 
=================

The typical workflow for Gemini observations is presented in the chart below. Click on a given step to see the detailed instruction for the step. 

.. graphviz::
   :alt: Typical GOATS workflow 
   :align: center

     digraph workflow {
         a [label="Define Targets", labeljust=c, fontcolor="blue", href="./targets.html", target="_top"];
         b [label="Trigger Gemini", labeljust=c, fontcolor="blue", href="./trigger_gemini.html", target="_top"];
         c [label="Download Gemini data", labeljust=c, fontcolor="blue", href="./goa_download.html", target="_top"];
         d [label="Reduce Gemini data with DRAGONS", labeljust=c, fontcolor="blue", href="./dragons.html", target="_top"];
         e [label="Data management and visualization", labeljust=c, fontcolor="blue", href="./visualization.html", target="_top"];
         f [label="Spectroscopic data analysis", labeljust=c, fontcolor="blue", href="./analysis.html", target="_top"];
         g [label="Interface with Astro Data Lab", labeljust=c, fontcolor="blue", href="./datalab.html", target="_top"];
         h [label="Add existing observation", labeljust=c, fontcolor="blue", href="./existing_obs.html", target="_top"];
         a -> b 
         b -> c 
         a -> h
         h -> c
         c -> d 
         d -> e 
         e -> f 
         e -> g;
     }


.. note::

   There are two additional features in GOATS worth highlighting. First, it can also be used to trigger LCO and SOAR as well as retrieve the observation data from the LCO archive (see :ref:`trigger_aeon`). Second, users will be able to report discovery and/or classification of the transient to the `Transient Name Server <https://www.wis-tns.org/>`_ from GOATS (see :ref:`tns`).


.. toctree::
   :maxdepth: 1
   :hidden:

   targets.rst
   trigger_gemini.rst
   existing_obs.rst
   goa_download.rst
   dragons.rst
   visualization.rst
   analysis.rst
   datalab.rst


