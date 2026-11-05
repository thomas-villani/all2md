# ruff: noqa: E501 - contract and report wording reads better unwrapped
"""The corpus, as scripts. Every organization, person and figure here is invented.

Each case builds a document through ``wordlive``, reaching for COM only for what it has no verb
for, and declares what the finished document must contain. `generate.py` asks Word whether that
is true before anything is written. The declaration exists because the first probe got its own
truth wrong twice without noticing: a style leaked into the paragraphs after a heading, and a
chart landed inside one. Either would have scored as a conversion defect.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from benchmarks.docx.generate.session import WordSession

WD_ALIGN_RIGHT = 2
WD_ALIGN_JUSTIFY = 3
NUMBER_ARABIC = 0
NUMBER_LOWERCASE_LETTER = 4
CONTROL_CHECKBOX = 8
TAB_LEADER_LINES = 3
WD_SECTION_BREAK_CONTINUOUS = 3


@dataclass(frozen=True)
class Expect:
    """What the finished document must contain, checked against Word's own reading."""

    headings: tuple[str, ...] = ()
    tables: tuple[tuple[int, int], ...] = ()
    footnotes: int = 0
    pictures: int = 0
    markers: tuple[str, ...] = ()
    header: str = ""
    footer: str = ""
    columns: int = 1


@dataclass(frozen=True)
class Case:
    """One scripted document."""

    family: str
    name: str
    description: str
    build: Callable[[Builder], None]
    expect: Expect = field(default_factory=Expect)
    control: bool = False


class Builder:
    """The handful of moves every case repeats."""

    def __init__(self, session: WordSession) -> None:
        self.s = session
        self.empty = True

    @property
    def doc(self) -> Any:
        return self.s.doc()

    def setup(self, font: str, size: float, paper: str | None = None) -> None:
        """Set the body font and paper. Real documents vary, and a check our defaults pass by luck measures nothing."""
        normal = self.doc.Styles("Normal").Font
        normal.Name = font
        normal.Size = size
        if paper:
            self.s.wl("page-setup", "--section", "1", "--paper-size", paper)

    def add(self, *items: str | tuple[str, str]) -> None:
        """Append paragraphs. Every one names its style, so a style cannot leak into the next."""
        block = [
            {"text": item, "style": "Normal"} if isinstance(item, str) else {"text": item[0], "style": item[1]}
            for item in items
        ]
        self.s.wl("insert-block", "--anchor-id", "start" if self.empty else "end", "--items", json.dumps(block))
        self.empty = False

    def index(self, starts_with: str) -> int:
        """Return the 1-based index of the last paragraph starting with this text."""
        found = None
        for number in range(1, self.doc.Paragraphs.Count + 1):
            if self.doc.Paragraphs(number).Range.Text.startswith(starts_with):
                found = number
        if found is None:
            raise KeyError(starts_with)
        return found

    def table(self, rows: list[list[str]], *, style: str | None = None, header: bool = False) -> Any:
        args = ["table", "create", "--anchor-id", "end", "--rows", str(len(rows)), "--cols", str(len(rows[0]))]
        if style:
            args += ["--style", style]
        if header:
            args.append("--header")
        self.s.wl(*args, "--data", json.dumps(rows))
        self.empty = False
        return self.doc.Tables(self.doc.Tables.Count)

    def furniture(self, header: str, footer: str) -> None:
        self.s.wl("header", "write", "--section", "1", "--text", header)
        self.s.wl("footer", "write", "--section", "1", "--text", footer)
        self.s.wl("insert-field", "--anchor-id", "footer:1:primary", "--kind", "page")

    def footnote(self, starts_with: str, ends_with: str, text: str) -> None:
        """Hang a footnote off the end of a phrase, so it does not land in the next paragraph."""
        paragraph = self.doc.Paragraphs(self.index(starts_with)).Range
        position = paragraph.Text.index(ends_with) + len(ends_with)
        note = self.doc.Footnotes.Add(self.doc.Range(paragraph.Start + position, paragraph.Start + position))
        note.Range.Text = text

    def outline(self, first: int, levels: list[int], formats: list[tuple[str, int]], name: str) -> None:
        """Apply a multilevel list to consecutive paragraphs, as a legal template does."""
        template = self.doc.ListTemplates.Add(OutlineNumbered=True, Name=name)
        for level, (number_format, number_style) in enumerate(formats, start=1):
            entry = template.ListLevels(level)
            entry.NumberFormat = number_format
            entry.NumberStyle = number_style
            entry.NumberPosition = 0 if level < 3 else 36
            entry.TextPosition = 36 if level < 3 else 72
            entry.TabPosition = 36 if level < 3 else 72
        span = self.doc.Range(
            self.doc.Paragraphs(first).Range.Start, self.doc.Paragraphs(first + len(levels) - 1).Range.End
        )
        span.ListFormat.ApplyListTemplate(template, False, 0)
        for offset, level in enumerate(levels):
            self.doc.Paragraphs(first + offset).Range.ListFormat.ListLevelNumber = level

    def plain_list(self, starts_with: str, count: int, kind: str) -> None:
        """Make consecutive paragraphs one bulleted or numbered list."""
        first = self.index(starts_with)
        start = self.doc.Paragraphs(first).Range.Start
        end = self.doc.Paragraphs(first + count - 1).Range.End
        self.s.wl("list", "apply", "--anchor-id", f"range:{start}-{end}", "--type", kind)

    def picture(self, stem: str, wrap: str = "inline", width: float = 216.0) -> None:
        """Add a picture in a new paragraph at the end. The bytes are generated, so nothing licensed gets in."""
        from PIL import Image, ImageDraw

        path = Path(tempfile.gettempdir()) / f"pdfword-{stem}.png"
        image = Image.new("RGB", (600, 300), (232, 240, 248))
        draw = ImageDraw.Draw(image)
        for step in range(6):
            draw.rectangle((40 + step * 90, 260 - step * 35, 100 + step * 90, 280), fill=(40 + step * 30, 90, 160))
        image.save(path)
        self.add("PICTUREHERE")
        at = self.index("PICTUREHERE")
        args = ["insert-image", "--anchor-id", f"para:{at}", "--path", str(path), "--wrap", wrap, "--width", str(width)]
        self.s.wl(*args, "--alt-text", f"Bar graphic: {stem}", "--before", "--block")
        self.doc.Paragraphs(self.index("PICTUREHERE")).Range.Delete()


CLAUSES: list[tuple[int, str]] = [
    (1, "Definitions"),
    (
        2,
        'In this Agreement, "Services" means the managed hosting and support services described in Schedule 1, and "Fees" means the amounts payable under Clause 3.',
    ),
    (2, '"Confidential Information" means all non-public information disclosed by one party to the other, including:'),
    (3, "business plans, pricing and customer lists;"),
    (3, "software, specifications and technical data; and"),
    (3, "the terms of this Agreement."),
    (1, "Term and Termination"),
    (
        2,
        "This Agreement starts on the Effective Date and continues for an initial term of thirty-six (36) months, unless terminated earlier under this Clause 2.",
    ),
    (2, "Either party may terminate this Agreement on thirty (30) days' written notice if the other party:"),
    (3, "commits a material breach that it fails to remedy within that period; or"),
    (3, "becomes insolvent or enters into administration."),
    (2, "Termination does not affect any rights that accrued before the date of termination."),
    (1, "Fees and Payment"),
    (
        2,
        "The Customer shall pay the Fees set out in Schedule 1 within forty-five (45) days of the date of each invoice.",
    ),
    (
        2,
        "Overdue amounts bear interest at one and one half percent (1.5%) per month, or the highest rate permitted by law if lower.",
    ),
    (2, "All Fees exclude value added, sales and similar taxes, which the Customer shall pay in addition."),
    (1, "Limitation of Liability"),
    (
        2,
        "Neither party excludes liability for death or personal injury caused by negligence, for fraud, or for any other liability that cannot be excluded by law.",
    ),
    (
        2,
        "Subject to Clause 4.1, each party's total liability in any contract year shall not exceed the Fees paid or payable in that contract year.",
    ),
    (1, "Confidentiality"),
    (
        2,
        "Each party shall keep the other party's Confidential Information secret and shall use it only to perform or exercise its rights under this Agreement.",
    ),
    (2, "This Clause 5 survives termination of this Agreement for a period of five (5) years."),
    (1, "Governing Law"),
    (
        2,
        "This Agreement is governed by the laws of the State of Delaware, and the parties submit to the exclusive jurisdiction of its courts.",
    ),
]


def msa_numbered(b: Builder) -> None:
    b.setup("Times New Roman", 11)
    b.add(
        ("Master Services Agreement", "Title"),
        'This Master Services Agreement (the "**Agreement**") is entered into as of March 1, 2026 (the "**Effective Date**") between **Alder Street Hosting LLC**, a Delaware limited liability company (the "**Provider**"), and **Quillfeather Books Inc.**, a New York corporation (the "**Customer**").',
        "The parties agree as follows:",
    )
    first = b.doc.Paragraphs.Count + 1
    b.add(*[(text, "Heading 1" if level == 1 else "Normal") for level, text in CLAUSES])
    b.outline(
        first,
        [level for level, _ in CLAUSES],
        [("%1.", NUMBER_ARABIC), ("%1.%2", NUMBER_ARABIC), ("(%3)", NUMBER_LOWERCASE_LETTER)],
        "LegalClauses",
    )
    b.add(
        ("Schedule 1: Services and Fees", "Heading 1"),
        "The Provider shall supply the following Services for the monthly Fees shown.",
    )
    b.doc.Paragraphs(b.index("Schedule 1:")).Range.ListFormat.RemoveNumbers()
    b.doc.Paragraphs(b.index("The Provider shall supply")).Range.ListFormat.RemoveNumbers()
    b.table(
        [
            ["Service", "Description", "Monthly Fee"],
            ["Managed hosting", "Dedicated servers with 99.9% uptime", "$4,200.00"],
            ["Support", "Twenty-four hour support by telephone and email", "$1,150.00"],
            ["Backups", "Nightly off-site backups, retained for 90 days", "$375.00"],
            ["Total", "", "$5,725.00"],
        ],
        header=True,
    )
    b.add("IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date.")
    signatures = b.table(
        [
            ["ALDER STREET HOSTING LLC", "QUILLFEATHER BOOKS INC."],
            ["By: ____________________", "By: ____________________"],
            ["Name: Dana Whitlock", "Name: Morgan Ashby"],
            ["Title: Chief Executive Officer", "Title: President"],
        ]
    )
    signatures.Borders.Enable = False
    b.footnote("Overdue amounts", "if lower.", "Interest accrues daily from the due date until payment in full.")
    b.furniture("CONFIDENTIAL", "Master Services Agreement, page ")


def nda_typed(b: Builder) -> None:
    b.setup("Times New Roman", 12)
    b.add(("Mutual Non-Disclosure Agreement", "Title"))
    lines = [
        (
            'This Agreement is made on June 12, 2026 between Pellward Instruments Inc. and Tamsin Reed Consulting LLC, each a "Party".',
            0,
        ),
        ("1.\tPurpose", 0),
        (
            "1.1\tThe Parties wish to explore a possible business relationship and may disclose confidential information to each other for that purpose.",
            1,
        ),
        ("1.2\tNothing in this Agreement obliges either Party to enter into any further agreement.", 1),
        ("2.\tObligations", 0),
        (
            "2.1\tEach Party shall protect the other Party's Confidential Information using at least the degree of care it applies to its own.",
            1,
        ),
        ("2.2\tA receiving Party shall not:", 1),
        ("(a)\tdisclose Confidential Information to any third party without prior written consent;", 2),
        ("(b)\tuse Confidential Information for any purpose other than the stated purpose; or", 2),
        ("(c)\tcopy Confidential Information except as reasonably necessary.", 2),
        ("3.\tExclusions", 0),
        (
            "3.1\tThese obligations do not apply to information that is or becomes public through no fault of the receiving Party.",
            1,
        ),
        (
            "3.2\tA Party may disclose information when a court or regulator requires it, after giving prompt notice to the other Party where lawful.",
            1,
        ),
        ("4.\tTerm", 0),
        (
            "4.1\tThis Agreement lasts for three (3) years from the date above, and obligations for trade secrets continue for as long as they remain trade secrets.",
            1,
        ),
    ]
    for text, depth in lines:
        b.add(text)
        paragraph = b.doc.Paragraphs(b.doc.Paragraphs.Count)
        paragraph.Alignment = WD_ALIGN_JUSTIFY
        paragraph.LeftIndent = 36 * (depth + 1) if depth else 36
        paragraph.FirstLineIndent = -36
        if depth == 0 and text[0].isdigit():
            paragraph.Range.Font.Bold = True
            paragraph.Range.Font.AllCaps = True
    b.add(
        "Signed by the Parties' authorized representatives:",
        "Pellward Instruments Inc.: ______________________",
        "Tamsin Reed Consulting LLC: ______________________",
    )
    b.furniture("Mutual NDA", "Page ")


def lease_articles(b: Builder) -> None:
    b.setup("Garamond", 12, "a4")
    b.add(
        ("Commercial Lease", "Title"),
        "WHEREAS, Landlord owns the building at 40 Copperline Road (the Building); and",
        "WHEREAS, Tenant wishes to lease part of the Building on the terms below;",
        "NOW, THEREFORE, the parties agree as follows.",
        ("Basic Terms", "Heading 1"),
        "The following terms apply throughout this Lease.",
    )
    terms = b.table(
        [
            ["Landlord", "Copperline Estates LLC"],
            ["Tenant", "Marrow & Finch Studio Inc."],
            ["Premises", "Suite 310, third floor"],
            ["Term", "Sixty months from July 1, 2026"],
            ["Base Rent", "$8,450.00 per month"],
            ["Security Deposit", "$16,900.00"],
        ]
    )
    terms.Borders.Enable = False
    b.add(
        ("Rent", "Heading 1"),
        "Tenant shall pay Base Rent in advance on the first day of each month, without demand, deduction or set-off.",
        "If Rent is more than five days late, Tenant shall pay a late charge of five percent of the overdue amount.",
        ("Use of Premises", "Heading 1"),
        "Tenant shall use the Premises only for general office and design studio purposes, and shall comply with all laws that apply to its use.",
        ("Maintenance", "Heading 1"),
        "Landlord shall keep the roof, structure and common areas in good repair. Tenant shall keep the interior of the Premises clean and in good condition.",
        ("Default", "Heading 1"),
        "Each of the following is a default by Tenant:",
        "failure to pay Rent within ten days of written notice;",
        "failure to perform any other obligation within thirty days of written notice; and",
        "abandonment of the Premises.",
    )
    b.plain_list("failure to pay Rent", 3, "numbered")
    b.s.link_list_style("Heading 1", number_style=NUMBER_ARABIC, fmt="Article %1.", template_name="LeaseArticles")
    b.add("Landlord: ______________________ Date: __________", "Tenant: ______________________ Date: __________")
    b.add(
        ("Exhibit A: Floor Plan Notes", "Heading 1"),
        "Suite 310 comprises approximately 2,400 rentable square feet, measured using the current BOMA standard.",
    )
    b.doc.Paragraphs(b.index("Exhibit A:")).PageBreakBefore = True
    b.furniture("Suite 310 Lease", "Lease, page ")


def terms_two_column(b: Builder) -> None:
    b.setup("Arial", 10)
    b.add(
        ("Terms and Conditions of Sale", "Title"),
        "These terms apply to every order placed with Brindlewood Supply Co. Please read them carefully.",
    )
    b.add("SECTIONBREAK")
    place = b.doc.Paragraphs(b.index("SECTIONBREAK")).Range
    place.MoveEnd(1, -1)
    place.Text = ""
    place.InsertBreak(WD_SECTION_BREAK_CONTINUOUS)
    clauses = [
        (
            "Orders",
            "An order is accepted only when we confirm it in writing or ship the goods. We may decline any order for any reason.",
        ),
        (
            "Prices",
            "Prices are those in effect on the date of shipment and exclude tax, freight and insurance, which we will add to the invoice.",
        ),
        (
            "Payment",
            "Payment is due within thirty days of the invoice date. We may suspend shipments while any amount is overdue.",
        ),
        (
            "Delivery",
            "Delivery dates are estimates only. Risk of loss passes to you when the goods leave our warehouse.",
        ),
        (
            "Returns",
            "You may return unused goods within fourteen days with our prior authorization. A restocking fee of ten percent applies.",
        ),
        (
            "Warranty",
            "We warrant that goods will conform to their published specifications for twelve months from the date of delivery.",
        ),
        (
            "Liability",
            "Our total liability for any claim will not exceed the price paid for the goods that gave rise to that claim.",
        ),
        (
            "Force Majeure",
            "Neither party is liable for delay caused by events beyond its reasonable control, including strikes, fire and flood.",
        ),
        (
            "Governing Law",
            "These terms are governed by the laws of the State of Ohio, excluding its conflict of laws rules.",
        ),
    ]
    for number, (title, body) in enumerate(clauses, start=1):
        b.add(f"**{number}. {title}.** {body}")
        paragraph = b.doc.Paragraphs(b.doc.Paragraphs.Count)
        paragraph.Alignment = WD_ALIGN_JUSTIFY
        paragraph.Range.Font.Size = 8.5
    # A continuous break after the clauses makes Word balance the two columns.
    b.add("SECTIONBREAK", "Questions about these terms? Contact your account manager or the sales office.")
    place = b.doc.Paragraphs(b.index("SECTIONBREAK")).Range
    place.MoveEnd(1, -1)
    place.Text = ""
    place.InsertBreak(WD_SECTION_BREAK_CONTINUOUS)
    b.s.wl("page-setup", "--section", "2", "--columns", "2")
    b.furniture("Brindlewood Supply Co.", "Terms of Sale, page ")


def _containing(b: Builder, text: str) -> int:
    for number in range(1, b.doc.Paragraphs.Count + 1):
        if text in b.doc.Paragraphs(number).Range.Text:
            return number
    raise KeyError(text)


def annual_report(b: Builder) -> None:
    b.setup("Georgia", 10.5)
    b.add(
        ("Annual Sustainability Report", "Title"),
        ("Fiscal Year 2025, Harrow & Vane Logistics", "Subtitle"),
        "Contents",
        "TOCHERE",
        ("Executive Summary", "Heading 1"),
        "Harrow & Vane cut its direct emissions by **twelve percent** in fiscal 2025, the third consecutive year of reduction. This report sets out what changed, what it cost and what comes next.",
        "Three programs produced most of the reduction:",
        "Replacing diesel vans in six urban depots with electric vehicles",
        "Installing rooftop solar at the Tilbury and Hull warehouses",
        "Rerouting night freight to reduce empty running",
        ("Emissions Performance", "Heading 1"),
        ("Direct Emissions", "Heading 2"),
        "Direct emissions fell from 48,200 tonnes to 42,400 tonnes of carbon dioxide equivalent. Fleet electrification accounted for roughly two thirds of the fall.",
        "CHARTHERE",
        "CHARTEND",
        "The chart above shows the direct emissions recorded in each of the last three fiscal years.",
        ("Energy Use by Site", "Heading 2"),
        "Electricity use varied widely by site. The table below shows the five largest sites, which together account for most of the total.",
    )
    b.plain_list("Replacing diesel vans", 3, "bulleted")
    at = b.index("CHARTHERE")
    data = json.dumps({"2023": 53.1, "2024": 48.2, "2025": 42.4})
    b.s.wl(
        "insert-chart",
        "--anchor-id",
        f"para:{at}",
        "--kind",
        "bar",
        "--data",
        data,
        "--title",
        "Direct emissions by year",
    )
    # The chart lands at the start of the next paragraph, so that paragraph is emptied to hold only it.
    b.doc.Paragraphs(b.index("CHARTHERE")).Range.Delete()
    holder = b.doc.Paragraphs(_containing(b, "CHARTEND")).Range
    b.doc.Range(holder.Start + 1, holder.End - 1).Text = ""  # after the chart, before the paragraph mark
    table = b.table(
        [
            ["Site", "Electricity (MWh)", "Change", "Renewable share"],
            ["Tilbury", "18,450", "-6.2%", "41%"],
            ["Hull", "12,310", "-3.8%", "37%"],
            ["Leeds", "9,875", "+1.4%", "12%"],
            ["Bristol", "7,640", "-0.9%", "18%"],
            ["Glasgow", "6,205", "-2.1%", "22%"],
        ],
        style="Grid Table 4 - Accent 1",
        header=True,
    )
    table.Range.InsertCaption("Table", ": Electricity use at the five largest sites", Position=0)
    b.add(
        ("Outlook", "Heading 1"),
        "The company has committed to the following steps for fiscal 2026:",
        "Electrify a further four depots",
        "Complete an independent audit of supply chain emissions",
        "Publish quarterly progress figures",
    )
    b.plain_list("Electrify a further", 3, "numbered")
    b.footnote(
        "Direct emissions fell",
        "equivalent.",
        "Figures follow the GHG Protocol Corporate Standard, using market-based factors.",
    )
    b.doc.Paragraphs(b.index("Executive Summary")).PageBreakBefore = True
    place = b.doc.Paragraphs(b.index("TOCHERE")).Range
    place.MoveEnd(1, -1)
    place.Text = ""
    b.doc.TablesOfContents.Add(place, True, 1, 2)
    b.furniture("Harrow & Vane Logistics", "Annual Sustainability Report, page ")


def memo_findings(b: Builder) -> None:
    b.setup("Cambria", 11, "a4")
    b.add(("Internal Audit Memorandum", "Title"))
    header = b.table(
        [
            ["To:", "Audit Committee"],
            ["From:", "Priya Holloway, Head of Internal Audit"],
            ["Date:", "September 18, 2026"],
            ["Re:", "Accounts payable controls review"],
        ]
    )
    header.Borders.Enable = False
    b.add(
        ("Summary", "Heading 1"),
        "We reviewed accounts payable controls for the twelve months to June 30, 2026. Controls were generally effective, but we found three weaknesses that need action this quarter.",
        ("Findings", "Heading 1"),
        "Duplicate vendor records: 212 of 4,180 active vendors appear more than once.",
        "Approval limits are not enforced in the invoice workflow.",
        "Payment runs lack a second reviewer at two sites:",
        "Dundee, since the departure of the deputy controller",
        "Swansea, where no second reviewer was ever appointed",
        ("Exceptions by Quarter", "Heading 1"),
        "The table below shows the exceptions we recorded in each quarter.",
    )
    b.plain_list("Duplicate vendor records", 5, "bulleted")
    b.s.wl("list", "indent", "--anchor-id", f"para:{b.index('Dundee, since')}")
    b.s.wl("list", "indent", "--anchor-id", f"para:{b.index('Swansea, where')}")
    table = b.table(
        [
            ["Exception type", "2026", "", ""],
            ["", "Q1", "Q2", "Q3"],
            ["Duplicate payment", "4", "7", "2"],
            ["Missing approval", "11", "9", "13"],
            ["Late posting", "23", "18", "16"],
        ],
        header=True,
    )
    table.Cell(1, 2).Merge(table.Cell(1, 4))
    b.add(
        ("Recommendations", "Heading 1"),
        "Merge duplicate vendor records and block new duplicates at entry.",
        "Enforce approval limits in the workflow system by December 31.",
        "Appoint second reviewers at Dundee and Swansea within thirty days.",
    )
    b.plain_list("Merge duplicate vendor", 3, "numbered")
    b.footnote("Duplicate vendor records", "more than once.", "Matched on tax identifier and bank account number.")
    b.footnote("We reviewed accounts", "June 30, 2026.", "Our scope excluded the newly acquired Dublin subsidiary.")
    b.furniture("Internal Audit: Confidential", "Accounts payable review, page ")


def financial_landscape(b: Builder) -> None:
    b.setup("Arial", 10)
    b.add(
        ("Five-Year Financial Summary", "Title"),
        "All amounts are in thousands of US dollars. Fiscal years end on March 31. Figures for 2026 are unaudited.",
    )
    rows = [["Line item", "2022", "2023", "2024", "2025", "2026", "Change"]]
    lines = [
        ("Product revenue", 18240),
        ("Service revenue", 6115),
        ("Licensing revenue", 2410),
        ("Total revenue", 26765),
        ("Cost of goods sold", 11850),
        ("Gross profit", 14915),
        ("Research and development", 3920),
        ("Sales and marketing", 4310),
        ("General and administrative", 2285),
        ("Depreciation", 1140),
        ("Operating income", 3260),
        ("Interest expense", 415),
        ("Other income", 92),
        ("Income before tax", 2937),
        ("Income tax", 705),
        ("Net income", 2232),
        ("Cash and equivalents", 5120),
        ("Accounts receivable", 4385),
        ("Inventory", 3190),
        ("Total current assets", 12695),
        ("Property and equipment", 8740),
        ("Goodwill", 2100),
        ("Total assets", 23535),
        ("Accounts payable", 2910),
        ("Accrued liabilities", 1675),
        ("Long-term debt", 6200),
        ("Total liabilities", 10785),
        ("Share capital", 4000),
        ("Retained earnings", 8750),
        ("Total equity", 12750),
        ("Operating cash flow", 3380),
        ("Capital expenditure", 1425),
        ("Free cash flow", 1955),
        ("Dividends paid", 600),
        ("Employees at year end", 214),
        ("Sites", 7),
    ]
    for name, base in lines:
        values = [base * (100 + 6 * year) // 100 for year in range(5)]
        change = round((values[-1] - values[0]) * 100 / values[0], 1)
        rows.append([name, *[f"{value:,}" for value in values], f"{change}%"])
    b.s.wl("page-setup", "--section", "1", "--orientation", "landscape")
    table = b.table(rows, header=True)
    table.Rows(1).HeadingFormat = True
    for column in range(2, 8):
        for row in range(1, len(rows) + 1):
            table.Cell(row, column).Range.ParagraphFormat.Alignment = WD_ALIGN_RIGHT
    b.add(
        "Total revenue includes the licensing business acquired in fiscal 2023 on a pro forma basis for all years shown."
    )
    b.furniture("Kestrel Ridge Manufacturing Inc.", "Financial summary, page ")


def figures_captions(b: Builder) -> None:
    b.add(
        ("Warehouse Automation Pilot", "Title"),
        ("Background", "Heading 1"),
        "The pilot ran for six months at the Corby distribution center, using autonomous carts on two picking aisles.",
        ("Results", "Heading 1"),
        "Pick rates rose steadily through the pilot, as the chart below shows.",
    )
    b.picture("pick-rates")
    b.doc.InlineShapes(1).Range.InsertCaption("Figure", ": Picks per hour during the pilot", Position=1)
    b.add(
        "Error rates fell by a third. Staff reported less walking and fewer strains, although the first month was disruptive while routes were being mapped out.",
        ("Cost", "Heading 1"),
        "Running costs came in below the estimate, as the next chart shows. The carts needed less charging infrastructure than the vendor had predicted, and there were no major repairs during the six months of the pilot.",
    )
    b.picture("running-costs", wrap="square", width=160.0)
    b.add(
        "We recommend extending the pilot to the remaining aisles at Corby in the first quarter, and reviewing the results before committing to any other site. The vendor has agreed to hold its current price until the end of the year, which gives us time to complete that review without any added cost.",
        ("Next Steps", "Heading 1"),
        "The following table shows the planned rollout.",
    )
    table = b.table(
        [
            ["Phase", "Scope", "Start"],
            ["Two", "Remaining Corby aisles", "January"],
            ["Three", "Review and decision", "April"],
        ],
        header=True,
    )
    table.Range.InsertCaption("Table", ": Planned rollout", Position=0)
    b.furniture("Corby Pilot Report", "Page ")


def vendor_form(b: Builder) -> None:
    b.setup("Arial", 10)
    b.add(
        ("Vendor Registration Form", "Title"),
        "Complete all sections in ink or electronically. Return to the procurement office within ten business days.",
    )
    sections = [
        (
            "Section A: Company Details",
            [
                ["Legal name", "", "Trading name", ""],
                ["Registered address", "", "City", ""],
                ["State or province", "", "Postal code", ""],
                ["Tax ID", "", "Phone", ""],
            ],
        ),
        (
            "Section B: Bank Details",
            [
                ["Bank name", "", "Branch", ""],
                ["Account name", "", "Account number", ""],
                ["Routing number", "", "SWIFT code", ""],
            ],
        ),
    ]
    for title, rows in sections:
        b.add((title, "Heading 2"))
        table = b.table(rows)
        for row in range(1, len(rows) + 1):
            for column in (1, 3):
                table.Cell(row, column).Shading.BackgroundPatternColor = 0xE6E6E6
                table.Cell(row, column).Range.Font.Bold = True
    b.add(
        ("Section C: Business Type", "Heading 2"),
        "☐ Corporation    ☐ Partnership    ☐ Sole proprietor    ☐ Non-profit",
        "Do you hold a current certificate of insurance?    ☐ Yes    ☐ No",
        "If yes, insurer: ______________________    Expiry date: ____ / ____ / ______",
        ("Section D: Declaration", "Heading 2"),
        "I declare that the information given on this form is true and complete to the best of my knowledge.",
        "Signature: ______________________    Date: ______________",
    )
    b.furniture("Form PR-104 (Rev. 03/2026)", "For office use only. Page ")


def application_controls(b: Builder) -> None:
    b.setup("Verdana", 10)
    b.add(
        ("Membership Application", "Title"),
        "Thornbury Community Rowing Club. Please answer every question. Fields marked with an asterisk are required.",
        ("Your Details", "Heading 1"),
    )
    for label in ["Full name*", "Date of birth*", "Street address*", "Email address", "Emergency contact*"]:
        b.add(f"{label}:\t")
        paragraph = b.doc.Paragraphs(b.doc.Paragraphs.Count)
        paragraph.TabStops.Add(432, 0, TAB_LEADER_LINES)
    b.add(("Membership Type", "Heading 1"), "Choose one of the following:")
    for option in ["Junior (under 18)", "Adult", "Family", "Coach or volunteer"]:
        b.add(f"  {option}")
        paragraph = b.doc.Paragraphs(b.doc.Paragraphs.Count).Range
        b.doc.ContentControls.Add(CONTROL_CHECKBOX, b.doc.Range(paragraph.Start, paragraph.Start))
    b.add(
        ("Experience", "Heading 1"),
        "Describe any rowing experience you have, including the clubs you rowed with and any qualifications you hold.",
        "COMMENTBOX",
    )
    place = b.doc.Paragraphs(b.index("COMMENTBOX")).Range
    place.MoveEnd(1, -1)
    place.Text = ""
    box = b.table([[""]])
    box.Rows(1).Height = 72
    b.add(
        ("Declaration", "Heading 1"),
        "I agree to follow the club's safety rules and confirm that I can swim at least fifty meters in light clothing.",
        "Signature:\t",
    )
    b.doc.Paragraphs(b.doc.Paragraphs.Count).TabStops.Add(432, 0, TAB_LEADER_LINES)
    b.furniture("Thornbury Community Rowing Club", "Membership application, page ")


def invoice(b: Builder) -> None:
    b.setup("Tahoma", 10)
    letterhead = b.table(
        [
            ["Fennimore Print Works", "INVOICE"],
            ["12 Lantern Yard, Portland, OR 97205", "No. 20648"],
            ["accounts@fennimore.example", "October 2, 2026"],
        ]
    )
    letterhead.Borders.Enable = False
    for row in range(1, 4):
        letterhead.Cell(row, 2).Range.ParagraphFormat.Alignment = WD_ALIGN_RIGHT
    letterhead.Cell(1, 1).Range.Font.Bold = True
    letterhead.Cell(1, 2).Range.Font.Bold = True
    b.add("Bill to: Ostler & Wren Publishing, 88 Quarry Street, Eugene, OR 97401")
    items = b.table(
        [
            ["Description", "Quantity", "Unit price", "Amount"],
            ["Offset printing, 48-page catalog", "2,500", "$1.84", "$4,600.00"],
            ["Saddle-stitch binding", "2,500", "$0.22", "$550.00"],
            ["Pre-press and proofs", "1", "$380.00", "$380.00"],
            ["Freight to Eugene", "1", "$215.00", "$215.00"],
        ],
        header=True,
    )
    for row in range(1, 6):
        for column in (2, 3, 4):
            items.Cell(row, column).Range.ParagraphFormat.Alignment = WD_ALIGN_RIGHT
    b.add("Thank you for your business.")
    totals = b.table([["Subtotal", "$5,745.00"], ["Sales tax", "$0.00"], ["Total due", "$5,745.00"]])
    totals.Borders.Enable = False
    totals.Cell(3, 1).Range.Font.Bold = True
    totals.Cell(3, 2).Range.Font.Bold = True
    b.add("Payment is due within thirty days of the invoice date. Please quote the invoice number on your payment.")
    b.furniture("Fennimore Print Works", "Invoice 20648, page ")


def survey_matrix(b: Builder) -> None:
    b.add(
        ("Staff Engagement Survey", "Title"),
        "Your answers are anonymous. For each statement, mark one box to show how much you agree.",
        ("About Your Work", "Heading 1"),
    )
    box = "☐"
    table = b.table(
        [
            ["Statement", "Agreement", "", "", ""],
            ["", "Strongly agree", "Agree", "Disagree", "Strongly disagree"],
            ["I have the tools I need to do my job", box, box, box, box],
            ["My workload is manageable", box, box, box, box],
            ["I understand how my work contributes", box, box, box, box],
            ["I get useful feedback from my manager", box, box, box, box],
            ["I would recommend this company to a friend", box, box, box, box],
        ],
        header=True,
    )
    table.Cell(1, 2).Merge(table.Cell(1, 5))
    b.add(
        ("About You", "Heading 1"),
        "Department: ______________________    Years of service: ______",
        ("Anything Else", "Heading 1"),
        "Please tell us anything else you would like us to know about working here.",
    )
    b.furniture("People Team", "Survey, page ")


def plain_prose(b: Builder) -> None:
    b.add(
        ("A Short History of the Canal", "Title"),
        ("Construction", "Heading 1"),
        "Work on the canal began in the spring of 1794, when a company of local merchants raised enough money to cut the first three miles of the route. Progress was slow because the ground was wet and the money ran out twice.",
        "The engineers lined the channel with puddled clay to stop it leaking. By the summer of 1801 the first boats could reach the town wharf, carrying coal in one direction and grain in the other.",
        ("Decline", "Heading 1"),
        "Traffic held up well until the railway arrived in 1848. Within twenty years the company had cut its tolls by half, and by the end of the century only a few coal boats still used the upper reaches.",
        "The last commercial cargo passed through the locks in 1936, after which the water was kept in only to feed the mills further down the valley.",
        ("Restoration", "Heading 1"),
        "A group of volunteers began clearing the towpath in 1971. They reopened the first restored lock nine years later, and the whole route has been navigable again since the summer of 2004.",
    )


CASES: tuple[Case, ...] = (
    Case(
        "control",
        "plain-prose",
        "Title, headings and plain paragraphs in one column, with no numbering, tables, notes or page furniture. If this scores badly, the lane is wrong.",
        plain_prose,
        Expect(headings=("A Short History of the Canal", "Construction", "Decline", "Restoration")),
        control=True,
    ),
    Case(
        "contract",
        "msa-auto-numbered",
        "Real multilevel Word numbering (1. / 1.1 / (a)) with numbered headings, a fee table, a borderless signature block, a footnote and a page header and footer.",
        msa_numbered,
        Expect(
            headings=(
                "Master Services Agreement",
                "Definitions",
                "Term and Termination",
                "Fees and Payment",
                "Limitation of Liability",
                "Confidentiality",
                "Governing Law",
                "Schedule 1: Services and Fees",
            ),
            tables=((5, 3), (4, 2)),
            footnotes=1,
            markers=(
                "1.",
                "1.1",
                "1.2",
                "(a)",
                "(b)",
                "(c)",
                "2.",
                "2.1",
                "2.2",
                "(a)",
                "(b)",
                "2.3",
                "3.",
                "3.1",
                "3.2",
                "3.3",
                "4.",
                "4.1",
                "4.2",
                "5.",
                "5.1",
                "5.2",
                "6.",
                "6.1",
            ),
            header="CONFIDENTIAL",
            footer="Master Services Agreement, page",
        ),
    ),
    Case(
        "contract",
        "nda-typed-numbers",
        "Clause numbers typed by hand with tabs and hanging indents, justified text, and bold capitals instead of heading styles. Common in the wild, and there is no list or heading to find.",
        nda_typed,
        Expect(headings=("Mutual Non-Disclosure Agreement",), header="Mutual NDA", footer="Page"),
    ),
    Case(
        "contract",
        "lease-articles",
        "Heading numbering carried by the style (Article 1.), a borderless key-terms table, recitals, a numbered list of defaults, typed signature lines and an exhibit on a new page.",
        lease_articles,
        Expect(
            headings=(
                "Commercial Lease",
                "Basic Terms",
                "Rent",
                "Use of Premises",
                "Maintenance",
                "Default",
                "Exhibit A: Floor Plan Notes",
            ),
            tables=((6, 2),),
            markers=(
                "Article 1.",
                "Article 2.",
                "Article 3.",
                "Article 4.",
                "Article 5.",
                "1.",
                "2.",
                "3.",
                "Article 6.",
            ),
            header="Suite 310 Lease",
            footer="Lease, page",
        ),
    ),
    Case(
        "contract",
        "terms-two-column",
        "Small print in two justified columns below a one-column title, in a continuous section.",
        terms_two_column,
        Expect(
            headings=("Terms and Conditions of Sale",),
            header="Brindlewood Supply Co.",
            footer="Terms of Sale, page",
            columns=2,
        ),
    ),
    Case(
        "report",
        "annual-report",
        "A cover page, a table of contents, heading levels, a vector chart, a styled table with a caption, bullets, a numbered list and a footnote.",
        annual_report,
        Expect(
            headings=(
                "Annual Sustainability Report",
                "Executive Summary",
                "Emissions Performance",
                "Direct Emissions",
                "Energy Use by Site",
                "Outlook",
            ),
            tables=((6, 4),),
            footnotes=1,
            pictures=1,
            header="Harrow & Vane Logistics",
            footer="Annual Sustainability Report, page",
        ),
    ),
    Case(
        "report",
        "memo-findings",
        "A borderless memo header, nested bullets, a table with a merged header cell, a numbered list and two footnotes.",
        memo_findings,
        Expect(
            headings=("Internal Audit Memorandum", "Summary", "Findings", "Exceptions by Quarter", "Recommendations"),
            tables=((4, 2), (5, 4)),
            footnotes=2,
            header="Internal Audit: Confidential",
            footer="Accounts payable review, page",
        ),
    ),
    Case(
        "report",
        "financial-landscape",
        "A wide numeric table on landscape pages, running across pages with a repeating header row.",
        financial_landscape,
        Expect(
            headings=("Five-Year Financial Summary",),
            tables=((37, 7),),
            header="Kestrel Ridge Manufacturing Inc.",
            footer="Financial summary, page",
        ),
    ),
    Case(
        "report",
        "figures-captions",
        "An inline picture with a numbered caption, a floating picture with text wrapped around it, and a table with a caption.",
        figures_captions,
        Expect(
            headings=("Warehouse Automation Pilot", "Background", "Results", "Cost", "Next Steps"),
            tables=((3, 3),),
            pictures=2,
            header="Corby Pilot Report",
            footer="Page",
        ),
    ),
    Case(
        "form",
        "vendor-registration",
        "Grid tables of shaded labels and empty answer cells, typed checkboxes and underscore answer lines.",
        vendor_form,
        Expect(
            headings=(
                "Vendor Registration Form",
                "Section A: Company Details",
                "Section B: Bank Details",
                "Section C: Business Type",
                "Section D: Declaration",
            ),
            tables=((4, 4), (3, 4)),
            header="Form PR-104",
            footer="For office use only.",
        ),
    ),
    Case(
        "form",
        "application-controls",
        "Answer lines drawn with tab leaders, real checkbox content controls and an empty comment box.",
        application_controls,
        Expect(
            headings=("Membership Application", "Your Details", "Membership Type", "Experience", "Declaration"),
            tables=((1, 1),),
            header="Thornbury Community Rowing Club",
            footer="Membership application, page",
        ),
    ),
    Case(
        "form",
        "invoice",
        "A borderless letterhead table, a line-item table with right-aligned numbers and a borderless totals table.",
        invoice,
        Expect(tables=((3, 2), (5, 4), (3, 2)), header="Fennimore Print Works", footer="Invoice 20648, page"),
    ),
    Case(
        "form",
        "survey-matrix",
        "A matrix of checkbox columns under a merged header cell.",
        survey_matrix,
        Expect(
            headings=("Staff Engagement Survey", "About Your Work", "About You", "Anything Else"),
            tables=((7, 5),),
            header="People Team",
            footer="Survey, page",
        ),
    ),
)
