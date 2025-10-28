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

2. Process a product link:

   ```bash
   python -m codex_douyin.cli.process_images "<douyin-share-url>" --output processed
   ```

   The command downloads all product images, removes their backgrounds, applies upscaling, and stores the transparent PNGs in the `processed/` directory.

## Testing

Run automated tests with:

```bash
pytest
```

## Notes

- Some Douyin endpoints require authentication or may enforce rate limits. Provide valid cookies if necessary by adjusting the `DouyinProductParser` headers.
- Background removal relies on OpenCV's GrabCut; extremely complex backgrounds may need manual refinement.
