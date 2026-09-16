- **The DOCX benchmark lane now gates every pull request.** Its corpus is Word-generated
  documents committed as bytes — 23 cases at this release — so replaying it costs seconds
  and depends on nothing external — but the gate had been living only on a
  developer's machine while six parser fixes landed against it. It now runs in the test
  suite: nothing crashes, no control case reports a defect, and scoring cannot silently
  produce no findings. The defect *count* is deliberately not gated, since a gate on it
  would punish adding a corpus case that exposes a real defect.
