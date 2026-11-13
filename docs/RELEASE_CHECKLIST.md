# Release checklist — ComfyUI_RH_API fork

## Distribution channels

- **GitHub clone (current target):** public `https://github.com/ZiYao00/ComfyUI_RH_API`, then users install requirements and set a private API key. This does not need Comfy Registry publisher credentials.
- **ComfyUI Manager / Registry (NOT YET configured for this fork):** the upstream author's PublisherId must not be reused. Register your own publisher at https://registry.comfy.org/, set `[tool.comfy]` to the actual approved PublisherId, configure `REGISTRY_ACCESS_TOKEN` as a GitHub Actions repository secret and `COMFY_REGISTRY_ENABLED=true` as a repository variable, then manually dispatch the publish workflow. Do not auto-publish on a README or `pyproject.toml` change. Registry versions are immutable; select and validate a new version for that channel.

## Source and install gate

- [ ] Ensure `main` is the intended release branch and review `git status`/diff; preserve unrelated edits.
- [ ] Confirm `config.json`, `config.local.json`, task-history, browser profiles and backups are not tracked; do not commit secrets. Also inspect Git history if a credential may have been exposed, and rotate only keys actually affected.
- [ ] Confirm `README.md`, `README_CN.md`, `docs/INSTALL.md`, `docs/INSTALL_CN.md`, `config.json.example`, `requirements.txt`, `__init__.py`, `nodes/`, `js/`, and `LICENSE` are present.
- [ ] Run `python -B tests/run_tests.py`, `node --test tests/native_migration.test.mjs`, `python -m compileall -q nodes tests`, and `git diff --check`.
- [ ] Verify GitHub CI passes for the selected commit.
- [ ] Test a **fresh clone** in a clean ComfyUI environment using its own Python: install `requests` from `requirements.txt`, place an independently created private `config.json`, restart, verify core nodes appear. This must not reuse a local Junction to development code.
- [ ] Confirm `RH Config` reads international `.ai` config when the node URL is blank; confirm saved explicit `.cn` values remain explicit. Verify that an untrusted imported `base_url` is rejected before it receives any local API Key; custom HTTPS proxies require private-config trust.
- [ ] Without paid RH jobs: check startup logs, node registration and basic graph editing/save/reload. Check version-sensitive VIDEO/AUDIO behavior on the targeted Core/Frontend.
- [ ] Only with separate approval for remote credit usage: smoke-test one known low-cost RH workflow and download/convert its result. Text/Image/Audio/Video external integrations are **not** proven by the local unit suite.
- [ ] Confirm the documentation accurately distinguishes this fork from the upstream Manager listing.

## Release controls

- [ ] Do not `git commit`, `git push`, tag, create a GitHub Release, or dispatch a Registry publication unless separately authorized.
- [ ] For a GitHub release after authorization: review changed files, commit, push, confirm remote SHA, CI pass, and public README/clone behavior. Tag/release notes are optional but useful for stable distribution.
- [ ] For Registry: register the publisher, update metadata, enable the manual workflow only when ready, check namespace/name collision, and verify successful Registry publication before advertising Manager install.
