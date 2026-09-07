"""A git environment with the caller's `GIT_*` variables removed.

Git exports `GIT_DIR` and `GIT_INDEX_FILE` to a hook. The tracked pre-commit hook runs
`make all`, which runs this test suite, so **every test that shells out to git does so with
those variables set, pointing at the real repository.** A test that builds a scratch
repository then operates on the wrong one.

This is not hypothetical. It was diagnosed here from four observations that only fit together
once the leak was found:

- `docs/agent/orphan.md` was in the index and never on disk. The break test writes it into a
  temporary directory, so only an index entry could be real — a leaked `git add`.
- `make drift` passed locally and failed in CI. Drift reads the filesystem; CI reads the commit.
- `git rm --cached` staged the deletion, `make all` ran, and the commit recorded nothing. The
  leaked `git add` put the entry back during the gate.
- With `SKIP_GATE=1` the same deletion committed immediately.

So the defect fabricated a committed file, then re-fabricated it each time it was removed, and
the gate that exists to catch an unindexed document could not see it. Nothing reported an error
at any point.

Use `scrubbed_env()` for **every** git call in this suite, including `git init` — scrubbing only
the later calls leaves `init` re-initialising the caller's repository, which is the same defect
with a narrower blast radius and a write to a real repository still in it.
"""

from __future__ import annotations

import os


def scrubbed_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return `os.environ` without any `GIT_*` key, plus a deterministic identity.

    `extra` is applied last, so a caller that deliberately wants a `GIT_*` value set — to
    reproduce the leak in a regression test — can still ask for it.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    if extra:
        env.update(extra)
    return env


def owns_git_dir(work: os.PathLike[str] | str, reported: str) -> bool:
    """Whether `reported` is the git dir belonging to `work` itself.

    Checked instead of matching git's `warning: re-init` text. That warning depends on git
    keeping the wording, on git warning at all, and on the caller not passing `-q` — a sibling
    repository hit the same defect with `-q` set and had no output to match.
    """
    from pathlib import Path

    if not reported.strip():
        return False
    return Path(reported.strip()).resolve() == (Path(work) / ".git").resolve()
