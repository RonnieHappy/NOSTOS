# NOSTOS-0 external replication protocol

**Protocol:** `nostos-external-replication/2.0`

**Scope:** independent execution of the data-free frozen foundation

**Claim boundary:** this protocol does not validate tissue biology, diagnosis, mechanics or clinical use.

## Eligibility

The operator must not use the author's existing environment or generated output directory. A different person should run the challenge from a fresh clone or release archive on a computer they control. Report any assistance received.

## Procedure

```powershell
git clone --branch v0.3.0-rc14 https://github.com/RonnieHappy/NOSTOS.git
cd NOSTOS
uv sync --extra dev --frozen
uv run nostos replication-challenge `
  --operator "name-or-laboratory" `
  --affiliation "institution" `
  --unaided `
  --no-author-environment `
  --assistance "none" `
  --source-kind release_archive `
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
6. The historical representation benchmark receipt is regenerated without treating its small-sample accuracies as a superiority gate.

This is a conformance challenge. It asks an external operator to reproduce the registered module truths, perturbation behavior, retained benchmark outputs, hashes and abstention semantics. The obsolete 16-case accuracy values are preserved inside the historical receipt for auditability but are not headline success criteria.

## Return package

Do not edit generated files. Compress the complete `replication-result` directory and submit it through the repository's “External replication result” issue form. Include the release tag, operating system, whether the run was completely unaided and any warnings. The receipt hashes its three underlying JSON artifacts, allowing maintainers and reviewers to detect changes.

Successful execution by an eligible operator closes only the external-software-execution gate. Independent acquisition and biological annotation remain separate requirements.

The returned directory is checked without trusting the submitter's summary:

```powershell
uv run nostos verify-replication replication-result/replication_receipt.json
```

The verifier recomputes every artifact hash, requires all frozen gates, rejects anonymous operators and requires an explicit unaided fresh-clone or release-archive attestation. A locally operated run can be integrity-checked with `--allow-author-run`, but that result is not eligible to close the external-user gate.
