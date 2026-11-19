---
name: integrations
description: Use when the user wants to combine Aria data and Project Aria Tools with open-source models from the research community — metric depth from the Aria Gen 2 stereo cameras (FoundationStereo), or building a visual map and relocalizing Aria images or the SLAM rig against it (HLOC). Also relevant when the user asks what ready-made examples exist for running third-party models on Aria recordings or live streams. Does NOT cover reading VRS or MPS outputs on their own (use the `projectaria-tools` skill) or Meta-released models like EgoBlur and Boxer (use the `aria-knowledge` skill).
---

# Aria Integrations

Integrations are example repositories that pair Aria data and Project Aria Tools with open-source models from the research community. Each one lives in its own GitHub repository.

> **Single source of truth** for each integration is **its GitHub repository** (table below) — setup, dependencies, CLI arguments, code and tutorials.
>
> This skill encodes only the stable concept. Fetch the repository for anything specific. **Never guess install steps or script names.**

## Current integrations

| Integration | What it does | Repository |
|---|---|---|
| **Depth from Stereo** ([FoundationStereo](https://github.com/NVlabs/FoundationStereo)) | Rectifies the front stereo fisheye pair into a pinhole pair using device calibration, estimates disparity, and converts it to metric depth using the stereo baseline. With MPS, each depth map is paired with its camera pose. | https://github.com/facebookresearch/projectaria_gen2_depth_from_stereo |
| **Visual Relocalization** ([HLOC](https://github.com/cvg/Hierarchical-Localization)) | Triangulates a sparse metric map from MPS poses, then localizes an RGB frame or the four-camera SLAM rig with retrieval, feature matching and PnP. The resulting 6DoF fixes anchor Aria VIO to the map, on recordings or live streams. | https://github.com/facebookresearch/projectaria_hloc_example |

Newer integrations may be listed on the docs index page before this table is updated: https://facebookresearch.github.io/projectaria_tools/gen2/research-tools/integrations

## Shared pattern

Each integration uses the same Aria building blocks:

- **Device calibration** to undistort or rectify the fisheye cameras into the pinhole model the third-party model expects.
- **MPS poses** to place per-frame results in a consistent world frame.

## Related plugin skills

- **`projectaria-tools`** — reading VRS, calibration and MPS outputs that the integrations consume.
- **`mps`** — producing the SLAM poses the integrations rely on.
- **`client-sdk`** — live streaming, for integrations that run on streamed data.
