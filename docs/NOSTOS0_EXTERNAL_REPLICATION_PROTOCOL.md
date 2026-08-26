# NOSTOS-0 external replication protocol

**Protocol:** `nostos-external-replication/1.0`

**Scope:** independent execution of the data-free frozen foundation

**Claim boundary:** this protocol does not validate tissue biology, diagnosis, mechanics or clinical use.

## Eligibility

The operator must not use the author's existing environment or generated output directory. A different person should run the challenge from a fresh clone or release archive on a computer they control. Report any assistance received.

## Procedure

```powershell
git clone --branch v0.3.0-rc5 https://github.com/RonnieHappy/NOSTOS.git
cd NOSTOS
uv sync --extra dev --frozen
uv run nostos replication-challenge `
  --operator "name-or-laboratory" `
  --output replication-result
```

Linux and macOS users may run the same commands without PowerShell line continuations. No microscopy data, model weights or private paths are required.

## Frozen gates

The receipt passes only when all conditions are true:

1. The synthetic protocol reports pass.
2. Nine truth constructs are registered.
3. All five primary module gates pass.
4. All 24 required module–perturbation tests pass.
5. Both mask experiments remain classified as sensitivity tests.
6. NOSTOS response-curve balanced accuracy is 1.000 on the frozen split.
7. Conventional-scalar balanced accuracy is 0.9375.
8. Naive-summary balanced accuracy is 0.9375.

## Return package

Do not edit generated files. Compress the complete `replication-result` directory and submit it through the repository's “External replication result” issue form. Include the release tag, operating system, whether the run was completely unaided and any warnings. The receipt hashes its three underlying JSON artifacts, allowing maintainers and reviewers to detect changes.

Successful execution by an eligible operator closes only the external-software-execution gate. Independent acquisition and biological annotation remain separate requirements.
