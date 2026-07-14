# File auto-accept development fixture

This plugin is for local file-transfer testing and is disabled by default.
Configure `Allowed sender IDs` from the Script card before enabling it. The
allowlist is empty by default and accepts canonical IDs such as `!01020304`.

To test outbound file sending, copy `tests/fixtures/file_transfer_1k.png` into
the directory configured by
`--plugins-files-directory`, then direct-message `!filetest` to the node.
Only allowlisted direct requests queue a transfer. Public and non-allowlisted
requests receive a reminder and do not queue a file transfer.
