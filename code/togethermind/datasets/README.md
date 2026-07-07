# US Corridor Auditor — Datasets

## Files

### `reference_landing_pages.json` (Real Data)
Structured analysis of 5 strong US enterprise SaaS landing pages (Stripe, Linear, Vercel, Notion, Plaid). Each entry contains pre-analyzed messaging patterns, pricing structures, and trust signals that serve as benchmarks for the audit.

**Source:** Manually analyzed from live public websites.  
**Purpose:** Reference corpus for the comparison step of the multi-agent audit.

### `sample_urls.txt` (Real URLs)
A curated list of real Indian SaaS company URLs (Chargebee, Freshworks, Zoho, Postman, etc.) and US enterprise benchmark URLs.

**Source:** Publicly available company websites.  
**Purpose:** The auditor tool fetches these live at runtime — no pre-scraped content needed.

## How the Auditor Uses Data

1. **At runtime:** The tool fetches the target URL (from `sample_urls.txt` or user input) and parses the live HTML
2. **For comparison:** The 3 critic agents compare the fetched content against the reference corpus in `reference_landing_pages.json`
3. **No pre-cached audits:** Every audit is fresh — the pipeline fetches, parses, and evaluates each time
