# app-error

Core error hierarchy, structured advisories, and multi-channel formatting protocols for `app-common`.

## Features
- **Zero external dependencies**: Pure Python standard library (`dataclasses`, `enum`).
- **Agent Advisory Protocol**: `Actor`, `Retry`, `ActionMode`, and `Advisory` structures indicating who should act, whether retrying is safe, target files, and fix commands.
- **Multi-view formatting**: Native renderers for CLI stderr, MCP tool context, and dictionary serialization.
