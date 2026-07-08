# Emoji Catalog Generation

This repository bundles `meshdash/assets/chat_emoji_catalog.min.json` for chat emoji search/picker support.

## Current bundled artifact

- Output file: `meshdash/assets/chat_emoji_catalog.min.json`
- Payload version field: `17.0`
- Payload date field: `2025-08-04, 20:55:31 GMT`
- SHA-256:
  - `d0404c336af8b6ba5a38f3c1f0dd1b72af4f20645f6d582bf2ee59d5cfc3f722`

## Input sources

- Input file name: `emoji-test.txt`
  - Default Unicode source path used by the generator:
    - `https://unicode.org/Public/emoji/latest/emoji-test.txt`
  - Expected payload version: `17.0`
  - Default input SHA-256:
    - `1d8a944f88d7952f7ef7c5167fef3c67995bcae24543949710231b03a201acda`
- Search keyword annotations: Unicode CLDR English annotations
  - CLDR git ref:
    - `dc25cedd74edaea2c7f8dcd84eeee634f74e1867`
  - `https://raw.githubusercontent.com/unicode-org/cldr/dc25cedd74edaea2c7f8dcd84eeee634f74e1867/common/annotations/en.xml`
    - SHA-256: `091807d3ec993e2bde057c39f75ce3a051764c2a12a6a96204c475c8f3fea817`
  - `https://raw.githubusercontent.com/unicode-org/cldr/dc25cedd74edaea2c7f8dcd84eeee634f74e1867/common/annotationsDerived/en.xml`
    - SHA-256: `c3d08ed66d4f840ba8b1202a5c7f6c4336e3c65363c08144811dc3f587e92a80`
- The generator treats these hashes and the expected emoji version as the
  reproducibility pin. The CLDR URLs are immutable commit URLs. If the Unicode
  `latest` emoji-test URL changes, the build fails instead of silently drifting.
- If CLDR annotation fetching, hash validation, or XML parsing fails, the
  default `--keyword-cache meshdash/assets/chat_emoji_catalog.min.json` reuses
  the bundled expanded keyword maps. Use `--keyword-cache ""` together with
  `--allow-missing-annotations` only when intentionally rebuilding with reduced
  name-derived keywords.

## Regeneration command

From repo root:

```bash
python scripts/build_emoji_catalog.py \
  --output meshdash/assets/chat_emoji_catalog.min.json
```

## Post-generation verification

```bash
sha256sum meshdash/assets/chat_emoji_catalog.min.json
```

## License notice linkage

Unicode Data Files (including CLDR annotation data) are licensed under Unicode License v3 unless otherwise indicated by Unicode. The required copyright and permission notice is included in:

- `third_party/licenses/unicode-license-v3.txt`
