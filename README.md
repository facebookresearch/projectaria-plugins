# Project Aria Plugins

[![Validate](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/validate.yml/badge.svg)](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/validate.yml)
[![Lint](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/lint.yml/badge.svg)](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/lint.yml)
[![Link check](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/link-check.yml/badge.svg)](https://github.com/facebookresearch/projectaria-plugins/actions/workflows/link-check.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)

Official [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
marketplace for [Project Aria](https://www.projectaria.com/) smart glasses
development.

This repository hosts a collection of AI coding assistant plugins that help
developers build with Project Aria. Each plugin bundles skills, tools, and
references for a specific surface of the Aria developer ecosystem.

## Installation

Add this marketplace to Claude Code:

```bash
claude plugin marketplace add github.com/facebookresearch/projectaria-plugins
```

Then install any plugin from it:

```bash
claude plugin install aria-ark@projectaria-plugins
```

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
- [Claude Code Plugins](https://docs.claude.com/en/docs/claude-code/plugins)
