# Contributing to Project Aria Plugins

We want to make contributing to this project as easy and transparent as
possible.

## Our Development Process

This project is developed internally at Meta and synced to GitHub. Changes are
made internally first and then pushed to the public repository. We welcome
contributions from the community through pull requests on GitHub, which will be
reviewed and merged back into our internal source of truth.

This repository hosts the Project Aria Claude Code marketplace and contains
one or more plugins under top-level directories (e.g. `projectaria_ark_plugin/`).
Each plugin has its own `.claude-plugin/plugin.json` and `skills/` tree, and is
registered in the marketplace via `.claude-plugin/marketplace.json` at the repo
root.

## Pull Requests

We actively welcome your pull requests.

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. If you've added or modified a plugin, update
   `.claude-plugin/marketplace.json` accordingly.
5. Ensure the test suite passes.
6. Make sure your code lints.
7. If you haven't already, complete the Contributor License Agreement ("CLA").

## Contributor License Agreement ("CLA")

In order to accept your pull request, we need you to submit a CLA. You only need
to do this once to work on any of Meta's open source projects.

Complete your CLA here: <https://code.facebook.com/cla>

## Issues

We use GitHub issues to track public bugs. Please ensure your description is
clear and has sufficient instructions to be able to reproduce the issue.

Meta has a [bounty program](https://bugbounty.meta.com/) for the safe
disclosure of security bugs. In those cases, please go through the process
outlined on that page and do not file a public issue.

## Coding Style

* 2 spaces for indentation rather than tabs
* 80 character line length where practical
* Follow existing conventions in the file you're editing
* For skill files (`SKILL.md`), follow the structure of existing skills under
  each plugin's `skills/` directory

## License

By contributing to Project Aria Plugins, you agree that your contributions will
be licensed under the Apache License, Version 2.0, as found in the LICENSE file
in the root directory of this source tree.
