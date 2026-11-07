# Contributing

Thank you for helping improve the Checkmk FortiAnalyzer Plugin. Bug reports,
documentation corrections and focused pull requests are welcome. Follow the
[Code of Conduct](CODE_OF_CONDUCT.md) in all project discussions.

## Reporting bugs and suggesting changes

Check existing issues before opening a new one. For a bug report, include:

- The plugin version and the Checkmk and FortiAnalyzer versions you use.
- The relevant configuration, including whether optional SSH collection is
  enabled, without credentials or other sensitive information.
- Steps to reproduce the problem, expected behavior and actual behavior.
- Relevant error messages and a minimal, sanitized response example if needed.

Remove passwords, API tokens, session cookies, serial numbers, internal host
addresses and customer information before sharing logs or API responses.
For substantial changes, open an issue to discuss the intended behavior first.

## Documentation

Start with the [README](README.md). Detailed guides cover
[installation](docs/installation.md), [authentication and API access](docs/authentication.md),
[monitoring](docs/monitoring.md) and [development, tests and releases](docs/development.md).
Keep these guides aligned with the implementation; preserve the README's short
service comparison and update the relevant detailed page when behavior changes.

## Local setup and validation

Fork the repository and create a branch for your change. From the project
directory, use a virtual environment and install the test dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install 'paramiko==4.0.0'
python3 -B -m unittest discover -s tests -v
python3 -B build_mkp.py
```

The offline tests use Checkmk API doubles and mocked device connections.
Paramiko is required for the SSH transport tests. No appliance credentials are
needed. Offline tests do not replace installation, discovery and monitoring
checks in a real Checkmk site. See [Tested environments](README.md#tested-environments)
for the maintainer's tested versions.

## Making changes

- Follow the existing Python style and keep changes focused on one problem.
- Keep service names, plugin IDs and exported metrics compatible where possible.
- Preserve valid zero measurements and report missing or invalid data explicitly.
- Keep credentials and raw sensitive responses out of process arguments,
  exceptions, logs and service output.
- Add or update meaningful tests when changing behavior. Documentation-only
  changes normally need no new tests.
- Update the README comparison and relevant documentation guides when
  configuration, services or behavior change.

Sources live under `cmk_addons_plugins/fortianalyzer/`. The
`cmk_addons/plugins` symlink supports local imports; edit the source files
rather than replacing the symlink. Generated MKPs and Python caches must not
be committed.

## Pull requests and releases

Open a pull request against `main`. Explain the problem, the resulting behavior
and how you validated it. Include any compatibility impact or checks that you
could not perform. Sanitize all examples and screenshots.

GitHub Actions runs the offline tests and builds the MKP. After changes reach
`main`, CI manages release versions, tags and MKP release assets. Do not create
release tags or change package versions solely for a normal contribution.

## Contribution license and AI assistance

By submitting a contribution, you agree to license it under
**GPL-2.0-or-later**, the same license as this project. You must have the rights
needed to submit it. Preserve applicable copyright and license notices, and
identify any third-party code and its license in the pull request.

AI-assisted contributions are welcome. Review and understand the submitted
code, verify its behavior and check any third-party licensing obligations.
Mention substantial AI assistance in the pull request description. Contributors
remain responsible for their submissions.
