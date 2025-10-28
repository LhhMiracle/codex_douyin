# Codex Douyin Image Toolkit

Utilities for fetching Douyin product imagery, removing backgrounds, and exporting HD-ready assets.

## Features

- Resolve Douyin share/product links and extract image assets
- Download and cache original product media
- Remove backgrounds automatically via GrabCut segmentation
- Upscale and export transparent PNGs ready for catalog usage
- Command-line interface for end-to-end processing

## Quick start

1. Install dependencies:

   ```bash
   pip install .[test]
   ```

2. Process a product input (short link, long link, or full share text):

   ```bash
   python -m codex_douyin.cli.process_images "<短链或整段文案>" --output processed
   ```

   The command downloads all product images, removes their backgrounds, applies upscaling, and stores the transparent PNGs in the `processed/` directory.

   - Supply cookies explicitly with `--cookies "<raw-cookie>"`, or define `DY_COOKIES` in your environment / `.env` file for automatic loading.
   - Use `--dry-run` to only normalize the input and display the resolved URL and product ID without downloading assets.
   - If a short link does not land on a product detail page, switch to a long link containing the `product_id`, or retry with valid cookies so the parser can inspect the HTML fallback.

## Testing

Run automated tests with:

```bash
pytest
```

## Notes

- Some Douyin endpoints require authentication or may enforce rate limits. Supply valid cookies with `--cookies` (or set `DY_COOKIES` via environment variables / `.env`) when HTML fallback parsing fails.
- Background removal relies on OpenCV's GrabCut; extremely complex backgrounds may need manual refinement.
