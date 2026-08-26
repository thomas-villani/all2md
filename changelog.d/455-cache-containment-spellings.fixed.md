- **benchmarks/pmc: a cold corpus cache no longer rejects its own directories** (#455).
  Materializing more than one article ran the workers concurrently, and each called
  ``mkdir(parents=True)`` on the shared ``articles/`` parent. ``Path.resolve()`` normally
  strips Win32's ``\?\`` extended-length prefix before returning, but that strip is
  verified against the filesystem and the verification fails while a sibling directory is
  being created — so one worker resolved ``\?\C:\cache\…\PMC1.1`` while the corpus root
  resolved to plain ``C:\cache\…``. ``relative_to`` compares path *parts*, and the
  prefixed spelling begins with ``\?\C:\`` rather than ``C:\``, so the containment check
  reported that a directory had escaped the root it was plainly inside. The check now
  compares one spelling of each path. It was only ever a cold cache and only ever more
  than one article — a single article materializes on the calling thread, and once
  ``articles/`` exists there is no ``mkdir`` left to race — which is why it read as a
  Windows flake rather than a defect. Scoring any manifest subset on a cold cache failed
  outright; ``test_a_withdrawn_article_does_not_disturb_the_others`` was intermittently
  red for the same reason.
