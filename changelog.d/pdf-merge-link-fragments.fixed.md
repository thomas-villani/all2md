- **pdf: a link is one link, not one per text span.** A PDF link annotation covers a
  rectangle, and every span inside it became a link of its own: "BioMed Central" came
  out as `[Bio](u)[Med](u)[ ](u)[Central](u)`, and a wrapped reference as one link per
  printed line. Neighboring links to the same URL and title, with only whitespace or
  line breaks between them, are now merged into one. On PMC2500011.1 that takes 43
  links to 18, with the same 16 URLs.
