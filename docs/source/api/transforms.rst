Transforms
==========

The transform system provides a powerful pipeline for modifying documents during conversion.
Transforms operate on the AST (Abstract Syntax Tree) and can add, remove, or modify nodes.

Using Transforms
----------------

Transforms can be applied during conversion by passing them to the main API functions:

.. code-block:: python

   from all2md import to_markdown
   from all2md.transforms import RemoveImagesTransform, HeadingOffsetTransform

   markdown = to_markdown(
       'document.pdf',
       transforms=[
           RemoveImagesTransform(),
           HeadingOffsetTransform(offset=1)
       ]
   )

Transforms can also be specified by name:

.. code-block:: python

   markdown = to_markdown('document.pdf', transforms=['remove-images', 'heading-offset'])

Transform Pipeline
------------------

The transform pipeline coordinates transform execution and rendering:

.. autosummary::
   :nosignatures:

   all2md.transforms.pipeline.Pipeline
   all2md.transforms.pipeline.render
   all2md.transforms.pipeline.apply

Transform Registry
------------------

The registry manages transform discovery and instantiation. Custom transforms can be
registered via Python entry points:

.. autosummary::
   :nosignatures:

   all2md.transforms.registry.TransformRegistry

Built-in Transforms
-------------------

Commonly used transforms included with all2md:

.. autosummary::
   :nosignatures:

   all2md.transforms.builtin.RemoveImagesTransform
   all2md.transforms.builtin.RemoveNodesTransform
   all2md.transforms.builtin.HeadingOffsetTransform
   all2md.transforms.builtin.GenerateTocTransform
   all2md.transforms.builtin.RemoveBoilerplateTextTransform
   all2md.transforms.builtin.AddAttachmentFootnotesTransform
   all2md.transforms.builtin.AddHeadingIdsTransform
   all2md.transforms.builtin.LinkRewriterTransform
   all2md.transforms.builtin.TextReplacerTransform
   all2md.transforms.builtin.AddConversionTimestampTransform
   all2md.transforms.builtin.CalculateWordCountTransform

For the complete list, see :doc:`all2md.transforms.builtin`.

Transform Hooks
---------------

Hooks allow custom code execution at specific points in the pipeline:

.. autosummary::
   :nosignatures:

   all2md.transforms.hooks.HookManager
   all2md.transforms.hooks.HookContext

Transform Options
-----------------

Options for configuring transform behavior:

.. autosummary::
   :nosignatures:

   all2md.transforms.options.RemoveNodesOptions
   all2md.transforms.options.HeadingOffsetOptions
   all2md.transforms.options.GenerateTocOptions

Complete Transform Reference
----------------------------

.. toctree::
   :maxdepth: 1

   all2md.transforms
   all2md.transforms.builtin
   all2md.transforms.pipeline
   all2md.transforms.registry
   all2md.transforms.hooks
   all2md.transforms.options
   all2md.transforms.metadata
