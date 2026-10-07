- **Attachment names are logged escaped.** `sanitize_attachment_filename` and the
  attachment helpers logged an untrusted name as it was, so a lone surrogate (which
  `surrogateescape` decoding produces) made the log record unencodable and broke the
  handler writing it, and a control character reached a terminal showing the log. They
  now log the name's `repr`.
