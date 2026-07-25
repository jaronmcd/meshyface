# Hello plugin

This plugin package is the minimal reference example for Meshyface
**Scripts (Alpha)**. It is bundled with Meshyface and discovered independently
of the configured local plugin directory when the Scripts runtime is enabled.

It starts disabled. Enable the `hello` plugin, then restart Meshyface:

```bash
python mesh_dashboard.py --plugin-enable hello
```

Send `!hello` to receive a sender-specific visit count.

See [`docs/plugins.md`](../../../docs/plugins.md) for the trust model,
configuration, deployment, and troubleshooting.
