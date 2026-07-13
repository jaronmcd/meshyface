# File auto-accept development fixture

This plugin is for local file-transfer testing and is disabled by default.
Edit `ALLOWED_SENDER_IDS` in `script.py` before enabling it.

To test outbound file sending, copy `tests/fixtures/file_transfer_1k.png` into
the directory configured by
`--plugins-files-directory`, then direct-message `!filetest` to the node.
Only allowlisted direct requests queue a transfer. Public and non-allowlisted
requests receive a reminder and do not queue a file transfer.
