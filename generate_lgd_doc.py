"""Generate a comprehensive LGD model documentation Excel workbook."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side
)
from openpyxl.utils import get_column_letter

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY   = "1A1A2E"
BLUE   = "2563EB"
LBLUE  = "DBEAFE"
GREY   = "F3F4F6"
DGREY  = "6B7280"
WHITE  = "FFFFFF"
AMBER  = "FEF3C7"
GREEN  = "DCFCE7"
RED    = "FEE2E2"

# ── Style helpers ─────────────────────────────────────────────────────────────

def _font(bold=False, size=10, colour=None, italic=False):
    return Font(bold=bold, size=size, color=colour or "000000", italic=italic,
                name="Calibri")

def _fill(hex_colour):
    return PatternFill("solid", fgColor=hex_colour)

def _align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def _border(style="thin"):
    s = Side(style=style, color="D1D5DB")
    return Border(left=s, right=s, top=s, bottom=s)

def _hdr(ws, row, col, text, bg=NAVY, fg=WHITE, size=10, bold=True, span=1,
         wrap=False):
    cell = ws.cell(row=row, column=col, value=text)
    cell.font  = _font(bold=bold, size=size, colour=fg)
    cell.fill  = _fill(bg)
    cell.alignment = _align("center", "center", wrap=wrap)
    cell.border = _border()
    if span > 1:
        ws.merge_cells(
            start_row=row, start_column=col,
            end_row=row,   end_column=col + span - 1
        )
    return cell

def _title(ws, row, text, ncols=12):
    _hdr(ws, row, 1, text, bg=NAVY, fg=WHITE, size=14, bold=True, span=ncols)

def _section(ws, row, text, ncols=12):
    _hdr(ws, row, 1, text, bg=BLUE, fg=WHITE, size=11, bold=True, span=ncols)

def _row(ws, row, cells, bg=WHITE):
    for col, val in enumerate(cells, 1):
        c = ws.cell(row=row, column=col, value=val)
        c.fill = _fill(bg)
        c.font = _font()
        c.alignment = _align("left", "center", wrap=True)
        c.border = _border()

def _col_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def _freeze(ws, cell="A3"):
    ws.freeze_panes = cell

# ── SHEET 1 – Cover ───────────────────────────────────────────────────────────

def sheet_cover(wb):
    ws = wb.active
    ws.title = "Cover"
    ws.sheet_view.showGridLines = False

    for r in range(1, 40):
        for c in range(1, 13):
            ws.cell(r, c).fill = _fill(WHITE)

    _col_widths(ws, [3, 20, 25, 20, 20, 15, 15, 15, 15, 15, 15, 3])

    # Title block
    ws.row_dimensions[4].height = 40
    ws.row_dimensions[5].height = 30
    _hdr(ws, 4, 2, "LOSS GIVEN DEFAULT (LGD) MODEL DOCUMENTATION",
         bg=NAVY, fg=WHITE, size=16, bold=True, span=10)
    _hdr(ws, 5, 2, "Retail & Corporate Portfolios  |  IRB Advanced Approach",
         bg=BLUE, fg=WHITE, size=12, bold=False, span=10)

    meta = [
        ("Bank Name",          "Hypothetical European Bank AG"),
        ("Document ID",        "CRM-LGD-DOC-2025-001"),
        ("Version",            "3.1"),
        ("Status",             "Final – Approved"),
        ("Effective Date",     "01 January 2025"),
        ("Next Review Date",   "31 December 2025"),
        ("Model Owner",        "Credit Risk Modelling, Group Risk"),
        ("Approving Body",     "Model Risk Committee"),
        ("Approval Date",      "15 December 2024"),
        ("Regulatory Scope",   "CRR3 Art. 161-162; EBA GL/2017/16; ECB Supervisory Guide (Jul 2025)"),
    ]
    for i, (label, value) in enumerate(meta, 7):
        ws.row_dimensions[i].height = 20
        c1 = ws.cell(i, 2, label)
        c1.font  = _font(bold=True, colour=NAVY)
        c1.fill  = _fill(LBLUE)
        c1.alignment = _align("left", "center")
        c1.border = _border()
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=3)

        c2 = ws.cell(i, 4, value)
        c2.font  = _font()
        c2.fill  = _fill(GREY)
        c2.alignment = _align("left", "center")
        c2.border = _border()
        ws.merge_cells(start_row=i, start_column=4, end_row=i, end_column=11)

    # Version history
    row = 19
    _section(ws, row, "VERSION HISTORY", ncols=10)
    row += 1
    for col, h in enumerate(["Version", "Date", "Author", "Approved By", "Summary of Changes"], 2):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE, span=1)
    row += 1
    history = [
        ("1.0", "Jan 2020", "A. Schmidt", "MRC", "Initial model documentation"),
        ("2.0", "Jan 2022", "B. Müller",  "MRC", "Extended to include CRR2 downturn add-on; revised collateral haircuts"),
        ("3.0", "Jan 2024", "C. Dupont",  "MRC", "Full redevelopment; alignment with EBA GL/2019/03; extended lookback"),
        ("3.1", "Dec 2024", "C. Dupont",  "MRC", "CRR3 alignment; updated MoC calculation; new validation evidence"),
    ]
    for i, h in enumerate(history):
        bg = GREY if i % 2 else WHITE
        for col, val in enumerate(h, 2):
            c = ws.cell(row + i, col, val)
            c.fill = _fill(bg)
            c.font = _font()
            c.alignment = _align(wrap=True)
            c.border = _border()

# ── SHEET 2 – Scope & Governance ─────────────────────────────────────────────

def sheet_governance(wb):
    ws = wb.create_sheet("1. Scope & Governance")
    ws.sheet_view.showGridLines = False
    _col_widths(ws, [3, 30, 55, 20, 10, 10, 10, 10, 10, 10, 10, 3])
    _freeze(ws, "A3")

    row = 1
    _title(ws, row, "1. SCOPE AND GOVERNANCE")
    row += 2

    # 1.1 Scope
    _section(ws, row, "1.1  Model Scope and Applicability")
    row += 1
    _row(ws, row, ["", "Parameter", "Description"], bg=DGREY)
    ws.cell(row, 2).font = _font(bold=True, colour=WHITE)
    ws.cell(row, 3).font = _font(bold=True, colour=WHITE)
    row += 1
    scope_rows = [
        ("Model Name",           "LGD Advanced IRB Model v3.1"),
        ("Risk Parameter",       "Loss Given Default (LGD) — fraction of EAD expected to be lost given a default event"),
        ("Regulatory Framework", "CRR3 Articles 161-162; EBA Guidelines EBA/GL/2017/16; ECB Supervisory Guide for Internal Models (July 2025), Chapter 17"),
        ("Portfolio Coverage",   "Retail Mortgage, Retail Other (qualifying revolving, other non-mortgage), SME Retail, Corporate (non-financial, financial institutions, sovereign excluded)"),
        ("Excluded Exposures",   "Sovereign, central banks, equity, securitisation positions, defaulted exposures (separate best-estimate LGD treatment)"),
        ("Use of Model Output",  "Regulatory capital (Pillar I RWA), ICAAP, IFRS 9 Stage 1/2 expected credit loss, risk-based pricing, limit setting"),
        ("Operational Entity",   "Hypothetical European Bank AG – consolidated group including all EEA subsidiaries on IRB roll-out plan"),
        ("Competent Authority",  "European Central Bank (SSM Direct Supervision)"),
    ]
    for i, (k, v) in enumerate(scope_rows):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, ["", k, v], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "1.2  Organisational Governance")
    row += 1
    gov_rows = [
        ["", "Role / Body", "Responsibility", "Reporting Line"],
        ["", "Model Owner (Credit Risk Modelling)", "Develops, maintains and monitors the LGD model; prepares model documentation; initiates model changes", "Group CRO"],
        ["", "Model Validation Unit (MVU)", "Independent validation of model methodology, data and performance; issues validation findings", "Group CRO (separate from Model Owner)"],
        ["", "Internal Audit", "Annual audit of IRB framework including LGD models; assess adequacy of controls", "Audit Committee"],
        ["", "Model Risk Committee (MRC)", "Approves models, material changes, and validation reports; sets model risk appetite", "Board Risk Committee"],
        ["", "Board Risk Committee", "Oversight of model risk framework; final approval of model risk appetite statement", "Board of Directors"],
        ["", "Credit Committee", "Uses LGD estimates in credit decisions; evidences use test", "Group CRO"],
    ]
    for i, r in enumerate(gov_rows):
        if i == 0:
            for col, val in enumerate(r[1:], 2):
                _hdr(ws, row, col, val, bg=DGREY, fg=WHITE)
        else:
            bg = GREY if i % 2 else WHITE
            _row(ws, row, r, bg=bg)
            ws.cell(row, 2).font = _font(bold=(i == 0))
        row += 1

    row += 1
    _section(ws, row, "1.3  Model Use (Use Test)")
    row += 1
    use_rows = [
        ["", "Business Process", "Frequency", "Evidence"],
        ["", "Regulatory Capital (RWA) Calculation", "Monthly", "Capital reporting pack; MRC sign-off"],
        ["", "ICAAP / Internal Capital Adequacy", "Annual", "ICAAP document submitted to ECB"],
        ["", "IFRS 9 Expected Credit Loss Provisioning", "Quarterly", "Audit-reviewed provisions schedules"],
        ["", "Risk-Based Pricing (RAROC)", "Per transaction", "Pricing tool system logs; deal approval memos"],
        ["", "Credit Limit Setting & Portfolio Management", "Monthly / On demand", "Credit Committee minutes; portfolio reviews"],
        ["", "Risk Appetite Statement Monitoring", "Quarterly", "Risk Appetite dashboard presented to BRC"],
    ]
    for i, r in enumerate(use_rows):
        if i == 0:
            for col, val in enumerate(r[1:], 2):
                _hdr(ws, row, col, val, bg=DGREY, fg=WHITE)
        else:
            bg = GREY if i % 2 else WHITE
            _row(ws, row, r, bg=bg)
        row += 1

# ── SHEET 3 – Data ────────────────────────────────────────────────────────────

def sheet_data(wb):
    ws = wb.create_sheet("2. Data")
    ws.sheet_view.showGridLines = False
    _col_widths(ws, [3, 30, 55, 15, 12, 12, 10, 10, 10, 10, 10, 3])
    _freeze(ws)

    row = 1
    _title(ws, row, "2. DATA GOVERNANCE AND SOURCES")
    row += 2

    _section(ws, row, "2.1  Data Sources")
    row += 1
    for col, h in enumerate(["", "Source", "Description", "Period", "Defaults (n)", "Obs. LGD (n)"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    sources = [
        ("Internal Workout Database", "Resolved defaults with complete recovery cashflows; primary estimation dataset", "Jan 2000 – Dec 2023", "18,420", "14,250"),
        ("Internal Ongoing Defaults",  "Defaults still open at cut-off; used for benchmarking and monitoring only", "Jan 2000 – Dec 2023", "3,201",  "N/A"),
        ("EBA Transparency Data",      "Used for benchmarking LGD estimates against peer European institutions", "2018 – 2023",         "N/A",    "N/A"),
        ("Collateral Valuation System","Forced-sale value (FSV) estimates from internal valuers; feeds haircut calibration", "2005 – 2023",  "N/A",    "N/A"),
        ("External Recovery Agent Data","Third-party workout data used to supplement thin segments (SME secured < 50k)", "2010 – 2023", "2,100",  "1,890"),
    ]
    for i, (src, desc, period, d, o) in enumerate(sources):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, ["", src, desc, period, d, o], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "2.2  Data Quality and Exclusions")
    row += 1
    for col, h in enumerate(["", "Criterion", "Rule", "Records Excluded", "Rationale"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    exclusions = [
        ("Incomplete workout", "Exclude defaults with missing recovery amounts or unresolved cashflows where imputation not possible", "1,203", "Incomplete workout cashflows cannot reliably estimate LGD"),
        ("Early repayment within 3m", "Exclude defaults resolved < 90 days with full recovery where technical default suspected", "892", "Technical defaults likely unrepresentative of true credit losses"),
        ("Data migration gaps (pre-2000)", "Exclude pre-2000 records due to inconsistent system migration fields", "4,112", "Data quality below minimum standard per EBA GL 2017/16 §110"),
        ("Write-off without recovery", "Retained but flagged; LGD = 100% unless positive recovery documented post write-off", "—", "Conservative treatment per EBA GL; no exclusion"),
        ("Restructured exposures (non-default)", "Exclude forborne exposures that never formally defaulted per DoD", "567", "Not within scope of default definition"),
    ]
    for i, (crit, rule, excl, rat) in enumerate(exclusions):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, ["", crit, rule, excl, rat], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "2.3  Reference Data Sets (Frozen Calibration Snapshots)")
    row += 1
    for col, h in enumerate(["", "Dataset ID", "Segment", "Snap Date", "Defaults", "Avg Obs LGD", "Downturn Period Included"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    rds = [
        ("RDS-LGD-2024-RM",  "Retail Mortgage",          "31 Dec 2023", "8,203", "21.4%", "Yes (2008-2012)"),
        ("RDS-LGD-2024-RO",  "Retail Other",             "31 Dec 2023", "3,102", "64.7%", "Yes (2008-2012)"),
        ("RDS-LGD-2024-SME", "SME Retail",               "31 Dec 2023", "2,945", "38.2%", "Yes (2008-2012)"),
        ("RDS-LGD-2024-COR", "Corporate (Unsecured)",    "31 Dec 2023", "1,890", "52.8%", "Yes (2008-2012)"),
        ("RDS-LGD-2024-COS", "Corporate (Secured)",      "31 Dec 2023", "1,110", "29.1%", "Yes (2008-2012)"),
    ]
    for i, r in enumerate(rds):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    ws.cell(row, 2, "Note: All reference datasets are version-controlled and stored in the Model Data Repository (MDR). Access is restricted to authorised model team members.")
    ws.cell(row, 2).font = _font(italic=True, colour=DGREY)
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=11)

# ── SHEET 4 – Methodology ─────────────────────────────────────────────────────

def sheet_methodology(wb):
    ws = wb.create_sheet("3. Methodology")
    ws.sheet_view.showGridLines = False
    _col_widths(ws, [3, 30, 60, 15, 10, 10, 10, 10, 10, 10, 10, 3])
    _freeze(ws)

    row = 1
    _title(ws, row, "3. LGD ESTIMATION METHODOLOGY")
    row += 2

    _section(ws, row, "3.1  Conceptual Framework — Workout LGD")
    row += 1
    framework = [
        ("LGD Estimation Approach",  "Workout (resolution) approach: observed recovery cashflows discounted to the date of default, divided by EAD at default. LGD_i = 1 − (PV of recoveries − PV of costs) / EAD_i"),
        ("Segmentation Principle",   "Exposures segmented by collateral type, seniority, and portfolio. Separate models for secured (real estate, financial collateral, other physical) and unsecured sub-segments"),
        ("Discount Rate",            "Contractual interest rate at time of default, floored at risk-free rate + 100bps. Per EBA GL/2017/16 §128 and ECB Supervisory Guide Para 766-767"),
        ("Observation Period",       "Minimum 7 years realised data; current dataset: Jan 2000 – Dec 2023 (24 years). Meets EBA GL §110 requirement of 5-year minimum for LGD"),
        ("Resolution Criteria",      "Case classified as resolved when: (a) write-off completed, (b) full recovery received, or (c) return to performing status with 12-month probation elapsed"),
    ]
    for i, (k, v) in enumerate(framework):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, ["", k, v], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "3.2  LGD Components")
    row += 1
    for col, h in enumerate(["", "Component", "Description", "Treatment"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    components = [
        ("Principal Recovery",   "Cash receipts from obligor repayments, asset sales, guarantor calls post-default", "Discounted to default date at contractual rate"),
        ("Collateral Realisations", "Net proceeds from forced sale of collateral (real estate, financial assets, physical assets)", "Forced-sale value (FSV) applied; haircuts per section 3.4"),
        ("Direct Workout Costs",  "Internal staff costs, legal fees, property management fees, court costs directly attributable to recovery", "Proportional allocation by workout case; capitalised if >€5k"),
        ("Indirect Costs",        "Overhead allocation for workout department", "Fixed percentage add-on: 1.5% of EAD per EBA GL §130"),
        ("Interest Collected",   "Accrued interest recovered post-default", "Included in recovery cashflows; consistent with EAD definition"),
        ("Forgiven Amounts",     "Principal or interest formally waived as part of restructuring settlement", "Treated as zero recovery in period of forgiveness"),
    ]
    for i, (comp, desc, treat) in enumerate(components):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, ["", comp, desc, treat], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "3.3  Segmentation and Model Architecture")
    row += 1
    for col, h in enumerate(["", "Segment", "Sub-Segment", "Collateral Type", "Model Type", "Min Defaults"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    segments = [
        ("Retail Mortgage",       "Owner-Occupied",      "Residential Real Estate",    "Component LGD (FSV haircut + unsecured residual)", "500"),
        ("Retail Mortgage",       "Buy-to-Let",          "Residential Real Estate",    "Component LGD",                                     "200"),
        ("Retail Other",          "Qualifying Revolving", "Unsecured",                 "Historical average LGD (direct estimate)",          "300"),
        ("Retail Other",          "Personal Loans",      "Unsecured",                  "Historical average LGD",                            "300"),
        ("SME Retail",            "Secured SME",         "Commercial Real Estate / Physical", "Component LGD",                             "150"),
        ("SME Retail",            "Unsecured SME",       "Unsecured",                  "Historical average LGD",                            "150"),
        ("Corporate",             "Large Corp Secured",  "Financial / Commercial RE",  "Component LGD",                                     "100"),
        ("Corporate",             "Large Corp Unsecured", "Unsecured",                 "Historical average LGD",                            "100"),
    ]
    for i, r in enumerate(segments):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "3.4  Collateral Haircuts (Forced-Sale Value Adjustments)")
    row += 1
    for col, h in enumerate(["", "Collateral Type", "Market Value Haircut", "Additional Forced-Sale Haircut", "Net FSV %", "Basis"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    haircuts = [
        ("Residential Real Estate (Prime)",     "5%",  "10%", "85%", "Internal valuation database (2000-2023); aligned with CRR3 Art. 229"),
        ("Residential Real Estate (Non-Prime)", "10%", "15%", "75%", "Separate haircut applied for LTV > 80% at origination"),
        ("Commercial Real Estate (Office/Retail)", "15%", "20%", "65%", "Higher volatility; calibrated on IPD index data"),
        ("Commercial Real Estate (Industrial)", "10%", "15%", "75%", ""),
        ("Financial Collateral (Cash)",         "0%",  "0%",  "100%", "Zero haircut per CRR3 Art. 197"),
        ("Financial Collateral (Listed Equities)", "15%", "0%", "85%", "CRR3 Art. 197 standard haircut"),
        ("Physical Assets (Vehicles)",          "20%", "20%", "60%", "Auction realisation data from recovery agent"),
        ("Physical Assets (Machinery)",         "25%", "30%", "45%", "High obsolescence risk; third-party appraiser data"),
        ("Guarantees (Government)",             "0%",  "0%",  "100%", "Treated as direct credit substitution"),
        ("Guarantees (Corporate/HNWI)",         "10%", "10%", "80%", "Callable guarantee; legal enforceability confirmed"),
    ]
    for i, r in enumerate(haircuts):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

# ── SHEET 5 – Downturn LGD ────────────────────────────────────────────────────

def sheet_downturn(wb):
    ws = wb.create_sheet("4. Downturn LGD")
    ws.sheet_view.showGridLines = False
    _col_widths(ws, [3, 35, 50, 15, 12, 12, 10, 10, 10, 10, 10, 3])
    _freeze(ws)

    row = 1
    _title(ws, row, "4. DOWNTURN LGD ESTIMATION")
    row += 2

    _section(ws, row, "4.1  Regulatory Requirement and Approach Selection")
    row += 1
    reqs = [
        ("Regulatory Basis",   "CRR3 Art. 181(1)(b); EBA GL/2019/03 (Downturn LGD); ECB Supervisory Guide Para 867-893 (Downturn LGD; LGD Reference Value)"),
        ("Objective",          "Estimate LGD appropriate to an economic downturn, where this is more conservative than the long-run average LGD"),
        ("Approach Selected",  "Approach 2 (Observed impact): Directly estimated from observed LGDs during identified downturn period. Used where sufficient resolved defaults are available in the downturn window"),
        ("Downturn Period",    "2008 Q1 – 2012 Q4 identified as the relevant economic downturn for all portfolios based on GDP contraction, unemployment peak, and house price index trough in the bank's operating geography"),
        ("Economic Indicators Used", "GDP growth rate, unemployment rate, national HPI (residential), IPD index (commercial), 3-month Euribor as credit environment indicator"),
    ]
    for i, (k, v) in enumerate(reqs):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, ["", k, v], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "4.2  Downturn Period Identification — Economic Indicators")
    row += 1
    for col, h in enumerate(["", "Year", "GDP Growth", "Unemployment", "HPI Change (YoY)", "IPD Change (YoY)", "Downturn Flag"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    indicators = [
        ("2006", "+3.2%", "7.1%", "+8.3%",  "+6.1%",  "No"),
        ("2007", "+2.7%", "7.4%", "+4.1%",  "+2.0%",  "No"),
        ("2008", "-0.3%", "8.2%", "-5.2%",  "-8.4%",  "Yes ▼"),
        ("2009", "-4.7%", "10.1%","-12.8%", "-22.1%", "Yes ▼▼"),
        ("2010", "+1.9%", "9.8%", "-3.1%",  "-6.2%",  "Yes ▼"),
        ("2011", "+1.5%", "9.3%", "-1.2%",  "-2.8%",  "Yes ▼"),
        ("2012", "+0.4%", "8.9%", "+0.3%",  "-1.1%",  "Yes ▼"),
        ("2013", "+1.1%", "8.4%", "+2.1%",  "+1.4%",  "No"),
        ("2014", "+1.8%", "7.9%", "+3.4%",  "+3.2%",  "No"),
    ]
    for i, r in enumerate(indicators):
        bg = AMBER if "Yes" in r[-1] else (GREY if i % 2 else WHITE)
        _row(ws, row, [""] + list(r), bg=bg)
        row += 1

    row += 1
    ws.cell(row, 2, "Downturn period: 2008 Q1 – 2012 Q4 (highlighted in amber). Confirmed by statistical test: observed LGDs in this window are significantly higher than long-run average at 95% confidence level (t-test, p<0.01 for all segments).")
    ws.cell(row, 2).font = _font(italic=True, colour=DGREY)
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=11)
    row += 2

    _section(ws, row, "4.3  Downturn LGD Estimates vs Long-Run Average LGD")
    row += 1
    for col, h in enumerate(["", "Segment", "LR Avg LGD", "Downturn LGD (Obs.)", "Downturn Add-On", "LGD Reference Value (Art. 161)", "Applied Downturn LGD", "N (Downturn Period)"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    dt_lgd = [
        ("Retail Mortgage (Owner-Occ.)",    "18.3%", "28.7%", "+10.4pp", "10%",  "28.7%", "312"),
        ("Retail Mortgage (Buy-to-Let)",     "24.1%", "36.2%", "+12.1pp", "10%",  "36.2%", "98"),
        ("Retail Other (QRRE)",              "60.2%", "72.4%", "+12.2pp", "75%",  "75.0%", "410"),
        ("Retail Other (Personal Loans)",    "62.8%", "74.1%", "+11.3pp", "75%",  "75.0%", "322"),
        ("SME Retail (Secured)",             "33.5%", "46.8%", "+13.3pp", "N/A",  "46.8%", "187"),
        ("SME Retail (Unsecured)",           "58.4%", "68.9%", "+10.5pp", "N/A",  "68.9%", "203"),
        ("Corporate (Secured)",              "25.2%", "37.4%", "+12.2pp", "N/A",  "37.4%", "142"),
        ("Corporate (Unsecured)",            "48.6%", "61.2%", "+12.6pp", "N/A",  "61.2%", "110"),
    ]
    for i, r in enumerate(dt_lgd):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        # Colour downturn add-on column
        ws.cell(row, 5).fill = _fill(AMBER)
        ws.cell(row, 7).fill = _fill(LBLUE)
        row += 1

    row += 1
    ws.cell(row, 2, "Note: For retail mortgage QRRE and personal loans, applied downturn LGD is max(observed, LGD reference value) per CRR3 Art. 161(1) and EBA GL/2019/03 §48.")
    ws.cell(row, 2).font = _font(italic=True, colour=DGREY)
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=11)

# ── SHEET 6 – MoC ─────────────────────────────────────────────────────────────

def sheet_moc(wb):
    ws = wb.create_sheet("5. Margin of Conservatism")
    ws.sheet_view.showGridLines = False
    _col_widths(ws, [3, 35, 55, 15, 12, 12, 10, 10, 10, 10, 10, 3])
    _freeze(ws)

    row = 1
    _title(ws, row, "5. MARGIN OF CONSERVATISM (MoC)")
    row += 2

    _section(ws, row, "5.1  Regulatory Basis and MoC Framework")
    row += 1
    framework = [
        ("Regulatory Basis",    "CRR3 Art. 179(1)(f); EBA GL/2017/16 §§ 36-51; ECB Supervisory Guide Para 940-947"),
        ("MoC Objective",       "Compensate for known model deficiencies, data limitations, and the upper bound of estimation error, in accordance with the principle of conservatism in risk parameter estimation"),
        ("MoC Categories",      "Type A: Data deficiencies and limitations in historical experience\nType B: Imperfections and estimation uncertainty in model methodology\nType C: Changes in lending standards, underwriting criteria, or portfolio composition"),
        ("MoC Assignment",      "Each identified deficiency is assigned to a category and quantified using: (i) direct quantification, (ii) sensitivity analysis, or (iii) expert judgement benchmarked against external data"),
        ("Aggregation",         "Add-ons are applied at segment level to the long-run average LGD estimate. Final MoC floored at zero; no offsetting of add-ons across categories"),
    ]
    for i, (k, v) in enumerate(framework):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, ["", k, v], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        ws.cell(row, 3).alignment = _align(wrap=True)
        row += 1

    row += 1
    _section(ws, row, "5.2  MoC Inventory and Quantification")
    row += 1
    for col, h in enumerate(["", "MoC ID", "Type", "Description", "Segment(s)", "Quantification Method", "Add-On (pp)", "Status"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    moc_items = [
        ("MoC-LGD-01", "A", "Limited workout data for pre-2005 period; system migration gaps reduce usable history by ~20%", "All", "Sensitivity: re-estimate excluding pre-2005; delta = 1.2pp", "1.2", "Active"),
        ("MoC-LGD-02", "A", "Low default portfolio (LDP) in Corporate Secured (<150 defaults): statistical uncertainty in LGD estimation", "Corp (Secured)", "Bootstrapped confidence interval; 80th percentile add-on = 2.8pp", "2.8", "Active"),
        ("MoC-LGD-03", "A", "External recovery agent data used for SME secured thin segment; representativeness uncertainty", "SME (Secured)", "Benchmarking vs internal workout data where available; delta = 1.5pp", "1.5", "Active"),
        ("MoC-LGD-04", "B", "Indirect cost allocation uses fixed percentage; actual costs may vary by case complexity", "All", "Internal cost study comparing fixed vs. case-by-case; maximum deviation = 0.8pp", "0.8", "Active"),
        ("MoC-LGD-05", "B", "Discount rate floored assumption may understate cost of time for long workout cases (>5 years)", "All", "Scenario analysis: 5-year + cases re-discounted at market rates; delta = 0.6pp", "0.6", "Active"),
        ("MoC-LGD-06", "C", "Tightening of underwriting standards post-2019 reduces LTV at origination; impact on future recovery unclear", "Retail Mortgage", "Expert judgement; benchmarked against EBA disclosure LGD trend; add-on = 1.0pp", "1.0", "Active"),
        ("MoC-LGD-07", "C", "Rising interest rate environment (2022-2024) may reduce property values; incomplete in dataset", "Retail Mortgage", "Scenario: HPI -15% shock; component LGD increases by 1.8pp", "1.8", "Active"),
        ("MoC-LGD-08", "A", "Missing collateral valuations (~3% of cases); last known value imputed", "Corp & SME (Secured)", "Imputation sensitivity: missing at random vs MCAR; delta = 0.5pp", "0.5", "Active"),
    ]
    for i, r in enumerate(moc_items):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "5.3  MoC Summary by Segment")
    row += 1
    for col, h in enumerate(["", "Segment", "LR Avg LGD", "Total MoC (pp)", "MoC-Adjusted LGD", "Downturn LGD (Final)", "MoC Applied To"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    moc_summary = [
        ("Retail Mortgage (Owner-Occ.)",  "18.3%", "4.4", "22.7%", "28.7%", "Long-run average"),
        ("Retail Mortgage (Buy-to-Let)",  "24.1%", "4.4", "28.5%", "36.2%", "Long-run average"),
        ("Retail Other (QRRE)",           "60.2%", "2.6", "62.8%", "75.0%", "Long-run average"),
        ("Retail Other (Personal Loans)", "62.8%", "2.6", "65.4%", "75.0%", "Long-run average"),
        ("SME Retail (Secured)",          "33.5%", "4.5", "38.0%", "46.8%", "Long-run average"),
        ("SME Retail (Unsecured)",        "58.4%", "2.6", "61.0%", "68.9%", "Long-run average"),
        ("Corporate (Secured)",           "25.2%", "5.9", "31.1%", "37.4%", "Long-run average"),
        ("Corporate (Unsecured)",         "48.6%", "2.6", "51.2%", "61.2%", "Long-run average"),
    ]
    for i, r in enumerate(moc_summary):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        ws.cell(row, 4).fill = _fill(AMBER)
        ws.cell(row, 5).fill = _fill(LBLUE)
        ws.cell(row, 6).fill = _fill(GREEN)
        row += 1

# ── SHEET 7 – Final LGD Estimates ─────────────────────────────────────────────

def sheet_estimates(wb):
    ws = wb.create_sheet("6. LGD Estimates")
    ws.sheet_view.showGridLines = False
    _col_widths(ws, [3, 30, 20, 15, 15, 15, 15, 15, 15, 15, 15, 3])
    _freeze(ws)

    row = 1
    _title(ws, row, "6. FINAL LGD ESTIMATES FOR REGULATORY CAPITAL")
    row += 2

    _section(ws, row, "6.1  LGD Estimates Summary — Calibration Year 2024")
    row += 1
    note = ("All figures are the own-estimate LGDs used in Pillar I RWA calculations from 01 Jan 2025. "
            "Downturn LGD is used as the regulatory LGD input per CRR3 Art. 181.")
    ws.cell(row, 2, note).font = _font(italic=True, colour=DGREY)
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=11)
    row += 1

    for col, h in enumerate(["", "Segment", "Sub-Segment", "LR Avg LGD", "MoC-Adj LGD", "Downturn LGD (Reg Capital)", "# Defaults Used", "Avg Workout Period (months)", "Collateral Coverage %"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    estimates = [
        ("Retail Mortgage", "Owner-Occupied",       "18.3%", "22.7%", "28.7%", "5,421", "38", "92%"),
        ("Retail Mortgage", "Buy-to-Let",            "24.1%", "28.5%", "36.2%", "2,782", "44", "100%"),
        ("Retail Other",    "QRRE",                  "60.2%", "62.8%", "75.0%", "2,105", "18", "0%"),
        ("Retail Other",    "Personal Loans",        "62.8%", "65.4%", "75.0%", "997",   "22", "0%"),
        ("SME Retail",      "Secured (<€1m)",        "33.5%", "38.0%", "46.8%", "1,834", "52", "78%"),
        ("SME Retail",      "Unsecured (<€1m)",      "58.4%", "61.0%", "68.9%", "1,111", "28", "0%"),
        ("Corporate",       "Senior Secured",        "25.2%", "31.1%", "37.4%", "643",   "67", "85%"),
        ("Corporate",       "Senior Unsecured",      "48.6%", "51.2%", "61.2%", "567",   "48", "0%"),
        ("Corporate",       "Subordinated",          "74.3%", "77.1%", "82.6%", "89",    "72", "0%"),
    ]
    for i, r in enumerate(estimates):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        ws.cell(row, 6).fill = _fill(GREEN)
        row += 1

    row += 1
    _section(ws, row, "6.2  LGD for Defaulted Exposures (BLGD)")
    row += 1
    ws.cell(row, 2, "Best-estimate LGD (BLGD) for currently defaulted exposures is estimated using an expected cash flow approach per CRR3 Art. 181(1)(h) and EBA GL/2017/16 §§ 165-173. BLGD reflects current collateral values and expected recovery timeline. Separate documentation available: CRM-BLGD-DOC-2025-001.")
    ws.cell(row, 2).font = _font(italic=True, colour=DGREY)
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=11)

# ── SHEET 8 – Validation ──────────────────────────────────────────────────────

def sheet_validation(wb):
    ws = wb.create_sheet("7. Validation")
    ws.sheet_view.showGridLines = False
    _col_widths(ws, [3, 30, 55, 15, 12, 12, 10, 10, 10, 10, 10, 3])
    _freeze(ws)

    row = 1
    _title(ws, row, "7. VALIDATION AND BACKTESTING")
    row += 2

    _section(ws, row, "7.1  Validation Framework")
    row += 1
    framework = [
        ("Validation Cycle",     "Annual full validation; quarterly monitoring. Ad hoc validation triggered by material model changes or significant portfolio events"),
        ("Independence",         "Model Validation Unit (MVU) is organisationally independent from Credit Risk Modelling (model owner). MVU reports directly to Group CRO. Separate budget and headcount"),
        ("Validation Scope",     "Data quality and representativeness, model methodology soundness, discriminatory power, calibration accuracy (backtesting), benchmarking, use test compliance, documentation completeness"),
        ("Regulatory Basis",     "ECB Supervisory Guide Para 259-333 (Credit Risk – Internal Validation); EBA GL/2017/16 §§ 192-211"),
        ("Last Validation Date", "November 2024 — Full annual validation. Outcome: Conditional Pass. 2 open findings (see 7.4)"),
    ]
    for i, (k, v) in enumerate(framework):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, ["", k, v], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "7.2  Backtesting Results — Calibration Accuracy (2024 Annual Review)")
    row += 1
    for col, h in enumerate(["", "Segment", "Obs. LGD (OOS)", "Model LGD", "Difference", "Traffic Light", "Test", "Result"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    backtest = [
        ("Retail Mortgage (OO)",    "21.8%", "22.7%", "-0.9pp", "Green",  "t-test (p=0.38)", "PASS"),
        ("Retail Mortgage (BTL)",   "27.4%", "28.5%", "-1.1pp", "Green",  "t-test (p=0.29)", "PASS"),
        ("Retail Other (QRRE)",     "60.9%", "62.8%", "-1.9pp", "Green",  "t-test (p=0.22)", "PASS"),
        ("Retail Other (PL)",       "63.5%", "65.4%", "-1.9pp", "Green",  "t-test (p=0.18)", "PASS"),
        ("SME Retail (Secured)",    "37.1%", "38.0%", "-0.9pp", "Green",  "t-test (p=0.44)", "PASS"),
        ("SME Retail (Unsecured)",  "62.3%", "61.0%", "+1.3pp", "Amber",  "t-test (p=0.09)", "MONITOR"),
        ("Corporate (Sr. Secured)", "30.2%", "31.1%", "-0.9pp", "Green",  "t-test (p=0.41)", "PASS"),
        ("Corporate (Sr. Unsec.)",  "53.1%", "51.2%", "+1.9pp", "Amber",  "t-test (p=0.07)", "MONITOR"),
        ("Corporate (Sub.)",        "80.1%", "77.1%", "+3.0pp", "Red",    "t-test (p=0.02)", "FINDING"),
    ]
    lights = {"Green": GREEN, "Amber": AMBER, "Red": RED}
    for i, r in enumerate(backtest):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        ws.cell(row, 5).fill = _fill(lights.get(r[3], WHITE))
        ws.cell(row, 6).fill = _fill(lights.get(r[3], WHITE))
        if r[-1] == "FINDING":
            ws.cell(row, 8).fill = _fill(RED)
            ws.cell(row, 8).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "7.3  Additional Validation Tests")
    row += 1
    for col, h in enumerate(["", "Test", "Method", "Result", "Threshold", "Outcome"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    tests = [
        ("Population Stability Index (PSI)", "PSI computed for key risk drivers (LTV, collateral type, geography) quarterly", "0.07 (max)", "<0.10 Green; 0.10-0.25 Amber", "Green"),
        ("Benchmarking vs EBA Transparency", "LGD estimates compared to weighted avg of EU peer banks by segment", "Within ±5pp for all segments", "±5pp tolerance", "Pass"),
        ("Rank Ordering (Gini / AUC)", "Gini coefficient on case-level LGD rank ordering", "Gini: 0.48", ">0.35 acceptable", "Pass"),
        ("Sensitivity Analysis", "LGD re-estimated under ±10% collateral value shock and ±20% recovery rate shock", "Max sensitivity: 3.2pp", "< 5pp tolerance", "Pass"),
        ("Outlier Analysis", "Cases with LGD >150% or <0% reviewed individually", "12 cases reviewed; 3 corrected", "Annual review", "Pass"),
        ("Concentration Risk Test", "Top 10 defaulted obligors contribute <15% of total LGD dataset", "9.8%", "<15%", "Pass"),
    ]
    for i, r in enumerate(tests):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "7.4  Open Validation Findings")
    row += 1
    for col, h in enumerate(["", "Finding ID", "Severity", "Description", "Segment", "Remediation", "Target Date", "Status"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    findings = [
        ("VAL-LGD-2024-01", "Amber", "Backtesting result for Corporate Subordinated debt exceeds red threshold. Observed LGD significantly above model estimate, suggesting underestimation of losses for this sub-segment.", "Corp (Sub.)", "Re-calibrate sub-segment using latest data including COVID recovery observations. Increase MoC by 3pp as interim measure.", "30 Jun 2025", "In Progress"),
        ("VAL-LGD-2024-02", "Amber", "PSI for SME Retail collateral mix shows drift toward lower-quality physical assets, reducing adequacy of current haircuts.", "SME Retail", "Review and update collateral haircuts for physical assets. Commission updated external valuation dataset.", "30 Sep 2025", "Not Started"),
    ]
    for i, r in enumerate(findings):
        bg = AMBER
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        ws.cell(row, 3).fill = _fill(AMBER)
        row += 1

# ── SHEET 9 – Change Management ───────────────────────────────────────────────

def sheet_changes(wb):
    ws = wb.create_sheet("8. Change Management")
    ws.sheet_view.showGridLines = False
    _col_widths(ws, [3, 30, 15, 20, 45, 15, 15, 12, 10, 10, 10, 3])
    _freeze(ws)

    row = 1
    _title(ws, row, "8. MODEL CHANGE MANAGEMENT")
    row += 2

    _section(ws, row, "8.1  Change Classification Framework")
    row += 1
    classes = [
        ("Major Change",    "Material change to model methodology, scope extension to new portfolio, change to definition of default, significant recalibration (>5pp shift in any segment LGD). Requires pre-implementation validation, MRC approval, ECB notification per TRIM expectations"),
        ("Moderate Change", "Recalibration with <5pp shift, update to reference dataset, revision of MoC add-ons, change to collateral haircut table. Requires MVU review and MRC approval. Regulatory notification not mandatory but considered on case-by-case"),
        ("Minor Change",    "Data correction, documentation update, system parameter fix that does not change model output. Notified to MVU; logged in change register. MRC information only"),
    ]
    for i, (cls, desc) in enumerate(classes):
        bg = [RED, AMBER, GREEN][i]
        _row(ws, row, ["", cls, desc], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

    row += 1
    _section(ws, row, "8.2  Model Change Register")
    row += 1
    for col, h in enumerate(["", "Change ID", "Type", "Date Implemented", "Description", "LGD Impact", "MVU Sign-Off", "MRC Approval", "Status"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    changes = [
        ("CHG-LGD-2024-01", "Moderate", "01 Mar 2024", "Updated collateral haircuts for CRE (Office/Retail) following revised IPD index data reflecting post-COVID structural shift", "-2.1pp Corp Secured", "Feb 2024", "Mar 2024 MRC", "Implemented"),
        ("CHG-LGD-2024-02", "Minor",    "15 Apr 2024", "Documentation update to align with ECB Supervisory Guide July 2025 references; no model change", "None", "Apr 2024", "Information", "Implemented"),
        ("CHG-LGD-2024-03", "Major",    "01 Jan 2025", "Full model redevelopment: extended data history, CRR3 alignment, new SME Retail sub-segment, updated MoC framework", "Various (see Sheet 6)", "Nov 2024", "Dec 2024 MRC", "Implemented"),
        ("CHG-LGD-2025-01", "Moderate", "Planned Q3 2025", "Re-calibration of Corporate Subordinated LGD sub-segment following VAL-LGD-2024-01 finding", "TBC (+3pp interim MoC)", "Planned Jun 2025", "Planned Sep 2025", "Planned"),
    ]
    for i, r in enumerate(changes):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, [""] + list(r), bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

# ── SHEET 10 – Regulatory References ─────────────────────────────────────────

def sheet_references(wb):
    ws = wb.create_sheet("9. Regulatory References")
    ws.sheet_view.showGridLines = False
    _col_widths(ws, [3, 25, 55, 15, 20, 10, 10, 10, 10, 10, 10, 3])
    _freeze(ws)

    row = 1
    _title(ws, row, "9. REGULATORY REFERENCES AND COMPLIANCE MAPPING")
    row += 2

    _section(ws, row, "9.1  Key Regulatory Requirements — LGD (ECB Supervisory Guide, July 2025)")
    row += 1
    for col, h in enumerate(["", "ECB Para(s)", "Topic", "Doc Section(s)", "Status"], 1):
        _hdr(ws, row, col, h, bg=DGREY, fg=WHITE)
    row += 1
    refs = [
        ("766-767",  "LGD general framework; workout approach; discount rate",           "Section 3.1, 3.2",          "Compliant"),
        ("768-774",  "Segmentation and data requirements for LGD estimation",             "Section 2, 3.3",            "Compliant"),
        ("775-781",  "Definition and treatment of defaulted exposures",                    "Section 2.2",               "Compliant"),
        ("782-791",  "LGD component: costs; indirect cost add-on",                        "Section 3.2",               "Compliant"),
        ("792-802",  "Collateral valuation and haircut methodology",                       "Section 3.4",               "Compliant"),
        ("803-815",  "Long-run average LGD; lookback period; representativeness",         "Section 2.3, 6.1",          "Compliant"),
        ("816-825",  "Calibration of LGD; validation of long-run estimates",              "Section 5, 7.2",            "Compliant"),
        ("826-840",  "Margin of conservatism framework; Types A, B, C",                   "Section 5.1, 5.2",          "Compliant"),
        ("841-850",  "LGD for defaulted exposures (BLGD / best estimate LGD)",           "Section 6.2 / BLGD doc",    "Compliant"),
        ("851-866",  "Principles specific to direct estimates of LGD",                    "Section 3.3",               "Compliant"),
        ("867-871",  "Downturn LGD — calibration based on observed impact (Approach 2)", "Section 4",                 "Compliant"),
        ("872-893",  "LGD reference value for retail (QRRE / personal loans)",           "Section 4.3",               "Compliant"),
        ("940-947",  "Model-related MoC; identification and quantification",              "Section 5",                 "Compliant"),
        ("948-962",  "Review of estimates; performance monitoring frequency",             "Section 7.1, 7.2",          "Compliant"),
        ("259-333",  "Internal validation (credit risk) — general principles and scope", "Section 7",                 "Compliant"),
        ("334-351",  "Internal audit requirements for IRB models",                        "Section 1.2",               "Compliant"),
        ("352-426",  "Model use test — embedding in business processes",                  "Section 1.3",               "Compliant"),
        ("427-466",  "Management of changes to IRB approach",                             "Section 8",                 "Compliant"),
        ("467-549",  "Data maintenance for IRB approach",                                 "Section 2",                 "Compliant"),
    ]
    for i, (para, topic, doc_ref, status) in enumerate(refs):
        bg = GREEN if status == "Compliant" else AMBER
        _row(ws, row, ["", para, topic, doc_ref, status], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        ws.cell(row, 5).font = _font(bold=True, colour="16A34A" if status == "Compliant" else "D97706")
        row += 1

    row += 1
    _section(ws, row, "9.2  Other Regulatory References")
    row += 1
    other_refs = [
        ("CRR3",             "Regulation (EU) 2024/1623", "Art. 160-167 (LGD); Art. 174-181 (IRB requirements); Art. 229 (collateral valuation)"),
        ("EBA GL/2017/16",   "Guidelines on PD estimation, LGD estimation and treatment of defaulted exposures", "All sections; specifically §§ 36-51 (MoC), §§ 110-173 (LGD), §§ 192-211 (validation)"),
        ("EBA GL/2019/03",   "Guidelines on estimation of LGD appropriate for an economic downturn", "All sections"),
        ("EBA RTS/2016/03",  "RTS on the specification of the nature, severity and duration of economic downturns", "All sections"),
        ("EBA Q&A",          "Various EBA Q&A responses on LGD estimation methodology", "Q&A 2014_1072; Q&A 2016_2618; Q&A 2018_3920"),
        ("ECB TRIM Guide",   "ECB Targeted Review of Internal Models — Credit Risk methodology", "Chapter 5 (LGD)"),
        ("BCBS 347",         "Basel Committee: Revisions to the Standardised Approach for Credit Risk", "Reference for regulatory floors"),
    ]
    for i, (ref, title, scope) in enumerate(other_refs):
        bg = GREY if i % 2 else WHITE
        _row(ws, row, ["", ref, title, scope], bg=bg)
        ws.cell(row, 2).font = _font(bold=True)
        row += 1

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    wb = Workbook()
    sheet_cover(wb)
    sheet_governance(wb)
    sheet_data(wb)
    sheet_methodology(wb)
    sheet_downturn(wb)
    sheet_moc(wb)
    sheet_estimates(wb)
    sheet_validation(wb)
    sheet_changes(wb)
    sheet_references(wb)

    out = "/home/user/ECB_Json_Parser/LGD_Model_Documentation_HEB_AG_v3.1.xlsx"
    wb.save(out)
    print(f"Saved: {out}")

if __name__ == "__main__":
    main()
