"""Demonstration module for all2md."""

#  Copyright (c) 2025 Tom Villani, Ph.D.

from all2md import convert
from all2md.options import DocxRendererOptions, PptxOptions

# Convert a PowerPoint file to Markdown
pptx_options = PptxOptions(
    attachment_mode="base64", include_slide_numbers=True, include_notes=True  # Embed images as base64
)
markdown = convert("sample_presentation.pptx", target_format="markdown", parser_options=pptx_options)

# Save the markdown output
with open("presentation.md", "w", encoding="utf-8") as f:
    f.write(markdown)

# Convert Markdown back to DOCX
docx_options = DocxRendererOptions(default_font="Calibri", default_font_size=11, use_styles=True)
convert("presentation.md", target_format="docx", output="presentation.docx", renderer_options=docx_options)

print("Conversion complete: PPTX -> Markdown -> DOCX")
