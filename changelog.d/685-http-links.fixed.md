- **HTML `http:` links are kept.** With the default `require_https=True`, the HTML parser
  emptied the target of every `http:` and `ftp:` link it wrote to the output
  (`[old link]()`) and logged a warning for each one. `require_https` governs what the
  converter *fetches*, and a link in the output fetches nothing, so it no longer applies
  to links. Dangerous schemes such as `javascript:`, `data:` and `vbscript:` are still
  removed (#685).
