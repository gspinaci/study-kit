# Publishing checklist

## 1. Set your username

Replace the `OWNER` placeholder everywhere (README badges and links, `plugin.json`, `CITATION.cff`, issue template, `FUNDING.yml`):

```bash
grep -rl OWNER . --exclude-dir=.git | xargs sed -i 's/OWNER/your-username/g'
git commit -am "Set repository owner"
```

On macOS use `sed -i ''`.

## 2. Create the repository

On <https://github.com/new>:

| Field | Value |
|---|---|
| Repository name | `study-kit` |
| Description | Agent skill that turns a book into a grounded study website and a styled Anki deck — objectives, map, quiz, notebook, glossary, readings, videos — validated, link-checked, never an invented curriculum. |
| Visibility | Public |
| Initialize | **Nothing** (no README, .gitignore or license: they are in this repo) |

Then push:

```bash
git remote add origin git@github.com:your-username/study-kit.git
git push -u origin main --tags
```

Pushing the `v0.3.0` tag triggers the release workflow, which publishes `study-kit-skill.zip`, the example deck and the example site as release assets.

## 3. Repository settings

**About** (gear icon on the repo page)

- Website: `https://your-username.github.io/study-kit/`
- Topics: `agent-skills` `claude-code` `claude-skills` `anthropic` `skill-md` `anki` `spaced-repetition` `flashcards` `study-tools` `learning` `education` `static-site` `jupyter` `digital-humanities`
- Tick: Releases. Untick: Packages, Deployments (optional).

**Settings → General → Features**

- Issues: on · Discussions: on (the issue template links to it) · Wiki: off · Projects: off
- Pull requests: allow squash merging only; tick "Automatically delete head branches"

**Settings → Pages**

- Build and deployment → Source: **GitHub Actions**. The `ci` workflow deploys the example site on every push to `main`.

**Settings → Actions → General**

- Workflow permissions: "Read repository contents" (the workflows request what they need).

**Settings → Branches → Add rule** (or a ruleset) for `main`

- Require a pull request before merging (optional for a solo project)
- Require status checks to pass: `check`

**Settings → Code security**

- Dependabot alerts and security updates: on (`.github/dependabot.yml` is included)

## 4. Optional

- **Zenodo DOI**: log in at <https://zenodo.org> with GitHub, enable the repository under *GitHub*, then publish a new release; add the DOI badge to the README (placeholder comment at the top) and `CITATION.cff` (`doi:`).
- **Sponsors**: enable GitHub Sponsors and uncomment `.github/FUNDING.yml`.
- **Social preview**: Settings → General → Social preview → upload `docs/home-light.png` (crop to 1280×640).
- **Directories**: once public with a release, the repo is picked up by skills.sh after the first `npx skills add your-username/study-kit`.
