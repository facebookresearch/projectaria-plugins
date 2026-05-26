<!--
Thanks for sending a pull request! Please fill in the sections below.
-->

## Summary

<!-- What does this PR do? Why? -->

## Type of change

- [ ] New plugin
- [ ] New skill in an existing plugin
- [ ] Update to an existing skill
- [ ] Documentation / README / metadata
- [ ] CI / repo tooling
- [ ] Other (please describe)

## Checklist

- [ ] I have read [CONTRIBUTING.md](../CONTRIBUTING.md).
- [ ] I have completed the [Meta CLA](https://code.facebook.com/cla).
- [ ] If I added or modified a plugin, I updated
      `.claude-plugin/marketplace.json` accordingly.
- [ ] If I added a new skill, its `SKILL.md` has a valid YAML frontmatter
      (`name`, `description`) and the directory name matches `name`.
- [ ] `python scripts/validate_marketplace.py` passes locally.
- [ ] `python scripts/validate_skills.py` passes locally.
- [ ] Markdown is linted (`markdownlint-cli2 "**/*.md"`).

## Related issues

<!-- e.g. Fixes #123 -->
