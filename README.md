# ChangeGuard

ChangeGuard is a local change-impact analyzer for Java/Spring Boot Maven services. It compares a Git base with committed and working-tree changes, maps changed Java lines to methods, traces callers to REST endpoints/configuration/tests, assigns a reviewable risk score, runs predicted Maven tests, and produces Markdown plus an offline interactive HTML graph.

## Requirements and setup

- Python 3.11 or newer
- Git
- Java and Maven for running project tests

```powershell
python -m pip install -e .
```

For running ChangeGuard's own tests, install the development extra:

```powershell
python -m pip install -e ".[dev]"
changeguard --help
```

The application code, Java parser, graph, report, and optional language explanation all run locally. The MCP server uses stdio and does not send source code to a remote service. Ollama is optional; when running locally, set `CHANGEGUARD_OLLAMA_MODEL` to select a model (default: `qwen2.5-coder`).

## CLI

Run commands from a Java Maven Git repository, or provide `--repo`:

```powershell
changeguard analyze --base main
changeguard analyze --base main --json
changeguard run-tests --base main
changeguard report --base main --output changeguard-report.html --open
changeguard explain --base main
```

`analyze` and `run-tests` print Markdown by default and accept `--output FILE` to save it for a PR comment. `run-tests` saves the last verification to `.changeguard-last-run.json`; `report` includes those results when available. ChangeGuard reports an error if no impacted test class is identified rather than silently running an empty selection.

## GitHub Copilot Agent mode (MCP)

The local `.vscode/mcp.json` registration is ignored by Git and intended only for development in this repository. For a server registered once at VS Code user level and reused from any workspace, copy [docs/mcp-user-config.example.json](docs/mcp-user-config.example.json) into your user MCP configuration and replace `<ABSOLUTE_PATH_TO>` with the directory containing the ChangeGuard virtual environment. Install ChangeGuard into that environment first.

The server selects a workspace from the `repo_path` tool argument, `CHANGEGUARD_REPO`, the client-provided MCP roots, or the server process's current working directory, in that order. The selected directory must be a Git repository containing `pom.xml`; an unresolved `${workspaceFolder}` environment value is ignored. If no workspace is discovered, pass `repo_path` explicitly. Outputs are created in the selected Java repository. Call `whoami` to inspect the detected workspace and runtime details.

The server exposes:

- `analyze_change` — impact JSON and a Markdown summary
- `run_impacted_tests` — selected Maven tests and predicted-versus-actual results
- `generate_report` — creates and opens the HTML graph
- `explain_impact` — rule-based explanation, or Ollama when available locally
- `whoami` — reports workspace resolution and runtime details

Example Copilot prompts:

- “Analyze the impact of my changes and run the impacted tests”
- “Generate the ChangeGuard report”

## Four-step sample-service demo

The sample service has a local Git history with `main` as its baseline and a feature branch containing a risky `AttributeRepository.findAll()` change that makes one existing controller test fail.

1. Open a terminal in `tests/fixtures/sample-service` (the feature branch is checked out).
2. Make a small edit in `src/main/java/example/AttributeRepository.java` (for example, change the returned attributes).
3. Analyze and run the predicted tests:

   ```powershell
   changeguard analyze --base main
   changeguard run-tests --base main
   ```

4. Generate and open the graph:

   ```powershell
   changeguard report --base main --output changeguard-report.html --open
   ```

To run the project’s own unit tests from the ChangeGuard workspace:

```powershell
python -m pytest
```

## GitHub Actions

`.github/workflows/changeguard.yml` runs analysis and impacted Maven tests on pull requests, posts the Markdown result as a PR comment, and uploads `changeguard-report.html`.

## Privacy

Everything runs locally by default. ChangeGuard reads the local Git repository and Maven test reports, and generates the report as a local file. Optional Ollama requests go only to `http://localhost:11434`; only the diff summary and structured impact data are sent, never source code. The GitHub Actions workflow runs in the repository’s configured GitHub-hosted runner.
