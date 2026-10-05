- **GitHub alerts are read and written.** A quote whose first line is `[!NOTE]`, `[!TIP]`,
  `[!IMPORTANT]`, `[!WARNING]` or `[!CAUTION]` (in any case) is now an admonition, with
  the same `admonition_type` metadata as RST, MkDocs and AsciiDoc ones, instead of a
  quote that opens with the marker as text. As on GitHub, a marker sharing its line with
  text, a quote holding only the marker, or another kind stays an ordinary quote, and
  `parse_admonitions=False` turns it off. GFM, the default flavor, writes an untitled
  admonition of those five kinds back as an alert, from any source: a README with alerts
  round trips unchanged, and an RST `.. warning::` becomes `> [!WARNING]`. A titled
  admonition keeps its title as the bold label, since alerts have none, and other flavors
  keep the label too (`markdown_plus` still writes `!!!`). Flavors gain
  `supports_github_alerts()`.
