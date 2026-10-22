# Frontend design refresh — research and decisions

## Goals

KisanSaathi serves farmers who may be using a phone, may be working in Hindi, and may have inconsistent connectivity. The visual refresh prioritizes recognisable tasks, readable type, touch-friendly controls, clear data dates, and low page weight over novelty for its own sake.

## What changed

- Replaced the six-card, same-shape home grid with three task pathways: **Keep the crop healthy**, **Choose with evidence**, and **Sell with more confidence**. This groups tools by the farmer's immediate job rather than by an internal feature list.
- Kept every existing feature reachable: Crop Doctor, Irrigation Planner, Next Season Planner, Crop Insights, Mandi Prices, and Sell & Buy.
- Moved the live-price card into the hero visual so the price summary complements the primary action instead of competing with another large panel.
- Created `frontend/assets/field-morning.svg`, a small, original vector illustration stored locally. It loads without an image CDN, does not require a third-party script, and works offline. Three secondary illustrations give each workflow a distinct cue.
- Changed the brand system from blue/indigo to forest green, sage, warm paper white, and restrained harvest-gold accents. Green is used for primary action and positive context; gold is used as a small accent rather than as long-form text on white.
- Kept the existing Mukta and Tiro Devanagari Hindi fonts and expanded all new home copy in both English and Hindi.
- Added active navigation styling based on the current page, visible keyboard focus, mobile layouts, and larger control targets. The layout uses no new frontend framework or external icon library.
- Applied the new semantic colour tokens across every page through `css/redesign.css`; existing page scripts, forms, API routes and workflows are preserved.

## Why these choices

### Design for the task, not for the component library

Generic generated prototypes often repeat a small set of fashionable components (same-size cards, pills, light gradients, a large hero plus feature grid) while having little visual identity. Nielsen Norman Group describes the tendency for AI-generated designs to converge on common component-library patterns and appear homogeneous. The answer is not simply to add decoration; it is to make information hierarchy match the actual task, use real domain language, create a distinct and consistent visual language, and remove UI that doesn't help a farmer act.

Reference: https://www.nngroup.com/articles/ai-prototyping/

### Farmer usability and access

The GSMA AgriTech UX Design Guidebook specifically addresses digital agriculture services for people with low digital literacy and recommends designing around their context and access constraints. The redesign therefore uses action-based labels, brief descriptions, one obvious primary CTA, consistent navigation, bilingual wording, custom visual cues and a light, local illustration rather than relying on remote images or an external component runtime.

Reference: https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/gsma_resources/agritech-ux-design-guidebook/

### Accessibility basics

WCAG 2.2 calls for at least 4.5:1 contrast for normal text, visible keyboard focus, predictable navigation and appropriately sized pointer targets. Major button and language-control targets are kept at or above 44 CSS pixels where practical, exceeding WCAG 2.2's 24-by-24 CSS pixel minimum in most of the key actions. The interface remains responsive and keeps text as text instead of baking important words into images.

Reference: https://www.w3.org/TR/wcag/

### India-specific quality expectations

The Government of India's Guidelines for Indian Government Websites and Apps (GIGW) call out quality, accessibility, mobile optimisation, readable and relevant content, efficient loading, clear form labels, and support for users who do not understand English. These are appropriate benchmarks for a farmer-facing hackathon prototype as well.

Reference: https://guidelines.india.gov.in/focus-areas/

## Avoiding an “AI-template” appearance

There is no reliable visual test that proves a frontend was or was not made with AI. For this project, we avoid the commonly perceived template signals rather than making a claim about authorship:

- no six identical feature cards or oversized blank feature panel;
- no arbitrary gradients, floating glass panels everywhere, rainbow status badges, or decorative numbers without meaning;
- no generic “AI-powered” claims when the feature is a rules-based estimate;
- no made-up market, weather or profit figures; show report dates, source and uncertainty in the existing feature pages;
- no stock-photo requirement that adds another remote dependency; the home illustration is locally bundled and purpose-drawn for this product;
- clear separation of plant care, planning and market access tasks;
- consistent language and navigation across tools without making every content block visually identical.

## Validation performed

- Parsed all seven HTML pages with Python's HTML parser.
- Checked that all `data-i18n`, placeholder, ARIA and alt-text keys referenced by the HTML exist in both language dictionaries; English and Hindi dictionaries contain matching key counts.
- Parsed the custom illustration as XML.
- Checked local CSS, JavaScript and asset references exist.
- Ran `node --check` across all frontend JavaScript files.
- Ran the backend regression suite unchanged after the frontend-only update.

Visual browser screenshot automation was blocked by the execution environment's browser navigation policy, so a human visual pass on the target laptop/phone remains recommended before the hackathon submission.

## Suggested final manual QA

1. Start FastAPI at `http://localhost:8000` and verify every section from the header and mobile bottom bar.
2. Toggle Hindi/English on every page, not just the homepage.
3. Test the homepage at 1440px desktop, ~768px tablet, and 360–390px phone widths; check for horizontal overflow and that the mandi overlay never obscures the primary message.
4. Use keyboard Tab/Shift+Tab to confirm the focus outline remains visible.
5. Test no-data and stale-data API states so missing reports are not presented as current facts.
6. Confirm the page remains usable if the model, weather provider or mandi provider is unavailable.
