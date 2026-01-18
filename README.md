# Genealogy Analyzer Skill for Claude Code

A Claude Code skill for analyzing GEDCOM genealogy files with focus on finding anomalies in marriages, births, and deaths. Specialized for Russian Orthodox traditions (pre-1917).

## Features

- Analyze marriage dates against Orthodox wedding traditions
- Detect marriages in forbidden periods (fasting seasons)
- Find atypical wedding dates (summer, harvest time)
- Check first child birth dates relative to marriage
- Support for Julian calendar dates

## Installation

### As a Claude Code Skill

1. Clone this repository:
```bash
git clone https://github.com/USERNAME/genealogy-analyzer.git
```

2. Create a symlink in your Claude Code skills directory:
```bash
ln -s /path/to/genealogy-analyzer ~/.claude/skills/genealogy-analyzer
```

Or copy files directly:
```bash
cp -r genealogy-analyzer ~/.claude/skills/
```

3. The skill will be automatically available in Claude Code.

## Usage

The skill activates when you:
- Ask to analyze a GEDCOM file for anomalies
- Want to find atypical marriage dates
- Ask about dates matching Orthodox traditions
- Request investigation of specific families

### Example Prompts

- "Analyze my GEDCOM file for anomalies"
- "Find atypical marriage dates in tree.ged"
- "Check if this marriage date follows Orthodox traditions"
- "Find marriages in forbidden periods before 1930"

### Standalone Scripts

#### Analyze Marriage Dates
```bash
python3 analyze_marriages.py tree.ged
python3 analyze_marriages.py tree.ged --before 1920
python3 analyze_marriages.py tree.ged --before 1930 --output report.txt
```

#### Check First Child Birth Dates
```bash
python3 check_first_child.py tree.ged
```

## Orthodox Wedding Traditions

### Allowed Wedding Periods

1. **Winter Wedding Season** (~66% of marriages)
   - From Epiphany (Jan 7/19-20) to Maslenitsa week

2. **Spring Wedding Season** (~12%)
   - From Krasnaya Gorka (1st Sunday after Easter) to Trinity

3. **Autumn Wedding Season** (~22%)
   - From Pokrov (Oct 1/14) to Philip's Fast (Nov 14/27)

### Forbidden Periods

- Great Lent (48 days before Easter)
- Peter's Fast (after Trinity to Jun 29)
- Assumption Fast (Aug 1-14)
- Christmas Fast (Nov 15 - Dec 24)

## Data Privacy

**IMPORTANT:** Never commit GEDCOM files with real genealogical data to public repositories. The `.gitignore` file excludes `*.ged` files by default.

## GEDCOM Format Support

Supports GEDCOM 5.5.1 format with:
- Julian calendar dates (`@#DJULIAN@`)
- Approximate dates (ABT, BEF, AFT)
- Standard date formats

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
