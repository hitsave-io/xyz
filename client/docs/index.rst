.. HitSave documentation master file, created by
   sphinx-quickstart on Tue Oct 25 09:31:09 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

HitSave: instant cloud caching for your data.
=============================================

HitSave lets you track your experiments and data in a code-dependent way.

Example
-------

.. code-block:: python

   from hitsave import memo


Features
--------

- Use `@memo` to cache your function on the cloud.
- If your code changes, the cache becomes invalidated.
- Track your generated files.
- We supply a collection of streaming datasets through `hitsave.datasets`.
- So much more!!!!!!

Contents
========

.. toctree::
   :maxdepth: 1
   :caption: Guides

   introduction
   guides/installation
   guides/getting_started
   guides/datasets
   guides/ml
   guides/files
   guides/customise

.. toctree::
   :maxdepth: 1
   :caption: Tutorials

   tutorials/balloons

.. toctree::
   :maxdepth: 1
   :caption: API reference

   module/decorators






Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
