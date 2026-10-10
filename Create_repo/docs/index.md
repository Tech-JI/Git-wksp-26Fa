# Joint Teapot

A handy tool for TAs in JI to handle works through [Gitea](https://focs.ji.sjtu.edu.cn/git/), [Canvas](https://umjicanvas.com/), and [JOJ](https://joj.sjtu.edu.cn/). Joint is related to JI and also this tool which join websites together. Teapot means to hold Gitea, inspired by [@nichujie](https://github.com/nichujie).

## Workshop tooling

This fork adds `workshop.py`: a single command line tool that turns a sign-up
spreadsheet into Gitea teams and repositories. See
[Workshop tooling](workshop.md) for the workflow, the grouping rules and the
Gitea quirks worth knowing.

```bash
python3 workshop.py --help
python3 workshop.py parse-excel "roster.xlsx"
python3 workshop.py group
python3 workshop.py create-repos --yes
```

## Getting Started

### Setup venv (Optional)

```bash
python3 -m venv env # you only need to do that once
source env/Scripts/activate # each time when you need this venv
```

### Install

```bash
pip3 install -e .
cp .env.example .env && vi .env # configure environment
joint-teapot --help
```

### For developers

```bash
pip3 install -r requirements-dev.txt
pre-commit install
pytest -svv
```
