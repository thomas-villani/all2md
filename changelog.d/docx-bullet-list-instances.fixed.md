- **docx: each bullet list is its own list, in Word and when read back.** Every bullet
  list the renderer wrote shared the "List Bullet" style's numbering instance, so Word
  treated all of a document's bullets as one list: restarting it or converting it to
  numbers changed every bullet list at once. And two bullet lists in a row read back
  as one. The renderer now gives every list, bulleted or numbered, a numbering instance
  that restarts, which is what makes Word see a new list. The parser now splits two
  runs of bullets where Word does: where the second run's instance restarts or uses
  another definition. Runs on instances that share a definition with no restart
  remain one list, as in Word. Found by the PDF → DOCX Word read-back
  (`benchmarks.pmc word`): 176 bullet lists in the development corpus were merged in
  Word.
