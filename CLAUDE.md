# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository contains genealogical data in GEDCOM 5.5.1 format, exported from "Древо Жизни" (Tree of Life / Genery.com) software.

## Data File

- `tree.ged` - GEDCOM file (~24K lines, ~900KB) containing family tree data in UTF-8 encoding

## GEDCOM Format Reference

Key record types in this file:
- `INDI` - Individual person records (name, birth, death, events, photos)
- `FAM` - Family records linking spouses and children
- `OBJE` - Media objects (photos, documents, videos)

Important tags:
- `NAME` with `GIVN` (given name) and `SURN` (surname)
- `BIRT`, `DEAT` - Birth and death events with `DATE` and `PLAC`
- `RESI` - Residence records with dates and locations
- `FAMC` - Link to family where person is a child
- `FAMS` - Link to family where person is a spouse
- `MAP` with `LATI`/`LONG` - Geographic coordinates
- `NOTE` - Extended notes and descriptions
- `OBJE` with `FILE` - Attached media files

## Working with this Data

Due to file size (900KB+), use Grep for searching specific records rather than reading entire file:
```bash
# Find all individuals
grep "^0 @I" tree.ged

# Find specific person by name
grep -A5 "NAME.*Попов" tree.ged

# Find all family records
grep "^0 @F" tree.ged
```

## Language

Data is primarily in Russian. Names, places, and notes use Cyrillic text.
