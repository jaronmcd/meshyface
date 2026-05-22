# Emoji Catalog Generation

This repository bundles `meshdash/assets/chat_emoji_catalog.min.json` for chat emoji search/picker support.

## Current bundled artifact

- Output file: `meshdash/assets/chat_emoji_catalog.min.json`
- Payload version field: `17.0`
- Payload date field: `2025-08-04, 20:55:31 GMT`
- SHA-256:
  - `1aadda3e51b3180729d9e345e5abdfd247a39934c723c67577966e93ffc77ffb`

## Input source

- Input file name: `emoji-test.txt`
- Canonical Unicode source path used by the generator:
  - `https://unicode.org/Public/emoji/latest/emoji-test.txt`
- For release reproducibility, maintainers can pin to a versioned Unicode path instead of `latest` when needed.

## Regeneration command

From repo root:

```bash
python scripts/build_emoji_catalog.py \
  --input https://unicode.org/Public/emoji/latest/emoji-test.txt \
  --output meshdash/assets/chat_emoji_catalog.min.json
```

## Post-generation verification

```bash
sha256sum meshdash/assets/chat_emoji_catalog.min.json
```

## License notice linkage

Unicode Data Files are licensed under Unicode License v3 unless otherwise indicated by Unicode. The required copyright and permission notice is included in:

- `third_party/licenses/unicode-license-v3.txt`
