- Tables in a Word file made with a DOCX template no longer lose their borders when the template defines no
  table style. Word only saves a table style once a document uses it, so templates made in Word usually have
  none; the output now gets `Table Grid` instead. `table_style=None` still gives a plain table.
