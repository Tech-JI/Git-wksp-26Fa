# Workshop tooling

`workshop.py` turns a sign-up spreadsheet into Gitea teams and repositories:
it reads the spreadsheet, groups the students, checks the accounts against
Gitea, and creates one team plus one private repository per group from a
template repository.

It is a single command line tool with one subcommand per step, and every
subcommand that talks to Gitea is read-only unless it is given `--apply` or
`--yes`.

```bash
python3 workshop.py --help
python3 workshop.py <command> --help
```

## Setup

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
cp .env.example .env && vi .env
```

`pip install -e .` from the upstream instructions does **not** work here: this
directory has no `setup.py` or `pyproject.toml`. `workshop.py` runs straight
from the source tree and imports `joint_teapot` from the same directory, so run
it from the project root.

Only the Gitea settings are needed:

| Variable | Meaning |
| --- | --- |
| `GITEA_DOMAIN_NAME` | host, must be the canonical one (see below) |
| `GITEA_SUFFIX` | `/git` |
| `GITEA_ACCESS_TOKEN` | token with organization and repository write access |
| `GITEA_ORG_NAME` | the organization the teams and repositories live in |
| `DEFAULT_BRANCH` | branch of the template repository, usually `master` |

Keep `GITEA_DOMAIN_NAME` set to the canonical host. `focs.ji.sjtu.edu.cn`
answers with a 301 redirect to `focs.gc.sjtu.edu.cn`, and HTTP clients downgrade
any non-GET request to GET when following a 301, so every write (creating a
repository, adding a collaborator) fails with `405 Method Not Allowed` if the
redirecting host is used.

## Workflow

The steps are meant to be run in this order. Steps 1 and 2 rewrite their output
files, steps 3 to 6 only read until they are told to write.

```bash
# 1. spreadsheet -> group.txt (groups) + individual.txt (students alone)
python3 workshop.py parse-excel "roster.xlsx"

# 2. cut the individuals into groups and append them to group.txt
python3 workshop.py group

# 3. sanity checks, no writes
python3 workshop.py check-accounts --out missing_users.txt
python3 workshop.py detect-typos --probe

# 4. organization membership, through a team
python3 workshop.py add-team-members --team wksp-support
python3 workshop.py add-team-members --team wksp-support --apply

# 5. one team + repository per group (dry run, then for real)
python3 workshop.py create-repos --start 1 --end 3
python3 workshop.py create-repos --yes

# 6. checks after the fact
python3 workshop.py verify-repos
python3 workshop.py check-team wksp-support

# 7. human-readable reports
python3 workshop.py report
```

## Commands

| Command | What it does | Writes |
| --- | --- | --- |
| `parse-excel [EXCEL]` | Reads the sign-up spreadsheet and writes the group and individual files. A row with a non-empty `Q5.` is a group (the account column plus `Q5`/`Q6`/`Q7`, e-mail addresses being reduced to their local part), a row without one is an individual. | `group.txt`, `individual.txt` |
| `group [INDIVIDUAL] [GROUPS]` | Cuts the individuals into groups of `--size` (default 3) and appends them to `group.txt`, then empties `individual.txt`. | `group.txt`, `individual.txt` |
| `check-accounts [FILES...]` | Lists which accounts exist on Gitea and which do not. | `--out` |
| `detect-typos [FILES...]` | Looks for mistyped accounts, see below. | no |
| `add-team-members [FILES...]` | Adds every account to an organization team. | `--apply`, `--missing-out` |
| `create-repos [GROUPS]` | Creates or reconciles one team and repository per line of `group.txt` from `--template`. | `--yes` |
| `verify-repos [GROUPS]` | Checks that each repository has exactly the collaborators of its group and the expected default branch. | no |
| `check-team [TEAM]` | Reports collaborators of the `<prefix>*` repositories that are not members of the team. | no |
| `report [GROUPS]` | Writes the grouping with names and student IDs, plus the accounts without a Gitea account. | `--out`, `--unregistered-out` |

Useful options shared by the repository commands: `--prefix` (default
`GitWksp_team`), `--start` / `--end` to work on a range of groups, and `--org`
to override `GITEA_ORG_NAME` for one run.

## Input and output files

* `group.txt` — one group per line, accounts separated by spaces. Line number
  `N` maps to the team and repository `<prefix>NN`, so line order is the group
  numbering.
* `individual.txt` — one student per line as `<account> [student_id]`. The
  student ID is optional and only used by `group`; a line without one is still
  valid, for example when the enrollment spreadsheet contributes an account.
* `groups_report.txt` — the grouping, with name, student ID and registration
  status per member, then a summary.
* `unregistered.txt` — the accounts with no Gitea user, grouped, split by
  whether the account came from the student's own login or was typed by a
  teammate, and listing the groups where nobody can be added.
* `missing_users.txt` — a plain list written by `check-accounts --out` or
  `add-team-members --missing-out`.

## Grouping rules

`group` orders the leftover students and then cuts them into groups of the
requested size:

1. **Registration first.** Accounts that already exist on Gitea are grouped
   together, accounts that still have to register are grouped together, so a
   group is never left with a member who cannot be added as a collaborator.
   The two buckets are cut separately and never mix. Use `--no-gitea` to skip
   this check and group by student ID only.
2. **Student ID next.** Inside a bucket, students are ordered by the first
   three digits of their student ID and then by the full student ID, so
   near-sequential IDs end up together. A prefix that cannot fill a group is
   topped up from the next prefix.
3. **Leftovers.** A bucket that cannot fill a whole group becomes its own
   smaller group, except a single leftover, which joins the previous group of
   the same bucket.

## Repositories and teams

For every group, `create-repos` makes sure that

* a team with the group name exists (write permission, no all-repository
  access, so it only sees the repositories explicitly added to it),
* a private repository with the same name exists, generated from
  `--template` with `DEFAULT_BRANCH` as its default branch,
* the repository is added to the team, every account of the group is a team
  member and a repository collaborator,
* branch protection on the default branch is removed.

The command is **idempotent**: running it again leaves existing teams and
repositories alone and only adds what is missing. Students register over time,
so re-run `create-repos --yes` after a registration round and the new accounts
are picked up; `verify-repos` and `check-team` then tell you whether everything
lines up. Accounts that do not exist on Gitea are reported and skipped — the
rest of their group is still created, so a group whose members are all missing
ends up as a repository with no collaborators.

`report` lists exactly those groups, so they can be chased.

## Finding mistyped accounts

An account that does not exist on Gitea is either a student who has not
registered yet or a typo. `detect-typos` collects evidence for the second case:

* whether the account comes from the student's own response (the account
  column and the e-mail address of a row are filled from the same login, so
  those cannot be typos) or was typed by a teammate,
* string similarity against every account that does exist, including the
  members of the organization,
* with `--probe`, edit-distance-1 mutations of the account — one character
  dropped, two characters swapped, a character forgotten, a confusable
  character substituted (`m`/`n`, `i`/`l`/`1`, `o`/`0`, ...), a digit moved up
  or down, trailing digits removed — each probed against Gitea. An existing
  variant is strong evidence.

Gitea's `/users/search` endpoint is not available on every instance (it answers
`404` on `focs.gc.sjtu.edu.cn`), so candidates are generated and looked up
directly instead of searched.

A candidate is only convincing when something else agrees with it: the two
accounts sharing a teammate in the spreadsheet, two teammates independently
typing the same string, or a matching name and student ID in the same row.
Similarity alone is a hint, not a verdict.

## Gitea notes

* **There is no API for adding a plain organization member.**
  `OPTIONS /orgs/{org}/members/{username}` only answers `GET, DELETE`, so the
  only way to make somebody an organization member is through a team.
  `add-team-members` therefore adds the accounts to a team, which also gives
  them whatever that team can see — for a `read` team with a single repository
  that is read access to that repository.
* **Organization membership is not required to collaborate on a repository.**
  `repo_add_collaborator` works for any Gitea user, so if the only goal is to
  let students reach their own repository, adding them to a team is optional.
* **Username lookup is case-insensitive** (`user_get("Name")` finds `name`),
  so a `404` really means the account does not exist.
* **Late registrations are normal.** Check the registration state right before
  creating repositories rather than reusing an earlier list.

## Conventions that bite

* Line order in `group.txt` is the group numbering, and the numbering is the
  repository name. Inserting or deleting a line renumbers every group after
  it, so agree on the grouping before creating repositories, and treat any
  manual edit as a numbering change.
* `parse-excel` drops a group whose members all appear again in a later group
  (the later response wins), and drops an individual who is already a member
  of a written group. A student who submitted both an individual response and
  was named as a teammate therefore ends up in exactly one group.
* A cell containing the literal text `nan` is read as a missing value by
  pandas, which is convenient but means a group row filled with `nan` produces
  no teammates at all. A student who wrote only their own account in the group
  column ends up alone; such a group either stays as it is or is merged by
  hand.
