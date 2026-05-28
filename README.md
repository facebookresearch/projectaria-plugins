# Project Aria Plugins

[![Validate](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/validate.yml/badge.svg)](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/validate.yml)
[![Lint](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/lint.yml/badge.svg)](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/lint.yml)
[![Link check](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/link-check.yml/badge.svg)](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/link-check.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)

Official AI coding assistant plugin marketplace for
[Project Aria](https://www.projectaria.com/) smart glasses development.

This repository hosts a collection of AI coding assistant plugins that help
developers build with Project Aria. Each plugin bundles skills, tools, and
references for a specific surface of the Aria developer ecosystem.

## Installation

### Claude Code

Add this marketplace:

```bash
claude plugin marketplace add https://github.com/facebookresearch/projectaria-plugins.git
```

Then install any plugin from it, for example:

```bash
claude plugin install aria-ark@projectaria-plugins
```

### Codex

Add this marketplace:

```bash
codex plugin marketplace add https://github.com/facebookresearch/projectaria-plugins.git
```

Then open Codex chat, run `/plugin`, choose the Project Aria Plugins
marketplace, and install any plugin from it, e.g.`aria-ark`.

### Gemini CLI

Install as a Gemini CLI extension:

```bash
gemini extensions install https://github.com/facebookresearch/projectaria-plugins.git
```

The extension loads the `GEMINI.md` context file at session start, which
includes a tool mapping table and imports all ARK skill content.

## Plugins

| Plugin | Description |
|--------|-------------|
| [aria-ark](./projectaria_ark_plugin) | Aria Research Kit (ARK) skills — VRS data processing, MPS, calibration, and real-time webapp development (WebSocket streaming, 3D visualization, voice pipeline). |

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). All contributors are expected to
follow our [Code of Conduct](./CODE_OF_CONDUCT.md). Security issues should be
reported per [SECURITY.md](./SECURITY.md).

### Local validation

Before opening a PR, run the same checks CI runs:

```bash
pip install -r scripts/requirements.txt
python scripts/validate_marketplace.py
python scripts/validate_skills.py
python scripts/check_required_files.py
npx -y markdownlint-cli2 "**/*.md"
codespell
```

## License

Project Aria Plugins is licensed under the Apache License, Version 2.0. See
[LICENSE](./LICENSE) for the full text.

## Links

- [Project Aria](https://www.projectaria.com/)
- [Project Aria Documentation](https://facebookresearch.github.io/projectaria_tools/gen2/)
