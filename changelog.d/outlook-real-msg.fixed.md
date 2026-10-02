- **Outlook `.msg` files convert again; every real one used to fail.** The parser
  read `message_id` from extract-msg's message, an attribute that library has
  never had (it is `messageId`), so any message got as far as its headers and then
  stopped with "Failed to parse MSG file: AttributeError". The test suite stubbed
  extract-msg with the same wrong attribute, so it passed. Three further mismatches
  surfaced once real files were read:
  - `To`/`Cc` are now built from extract-msg's structured recipient list. Its
    joined strings use `;`, which the email package reads as the end of an address
    group, so every recipient after the first was dropped.
  - A display name that only repeats the address is omitted.
  - The HTML body arrives as bytes. It is now decoded and kept beside the plain body
    as an alternative, as in an `.eml`, so the EML options (`include_plain_parts`,
    `convert_html_to_markdown`) can choose it. A failure reading it is logged, not
    swallowed.

  The `outlook` extra now requires `extract-msg>=0.56.1`. With 0.37.1, the previous
  floor and the locked version, reading the HTML body of an RTF-encapsulated
  message (which is how Outlook usually stores HTML) crashes inside extract-msg
  under current RTFDE. The stub in the golden tests now mirrors extract-msg's real
  API, and a contract test checks the attributes the parser uses against the
  installed library.
