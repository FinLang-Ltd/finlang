# 🤝 Contributing to FinLang

Thank you for your interest in contributing to **FinLang** — the deterministic financial rules engine.

Your contributions help us improve the FinLang ecosystem for everyone.  
This guide explains how to contribute safely, legally, and efficiently.

---

## 📜 Contributor Licence Agreement (CLA)

Before we can accept your contributions, you must agree to the  
[**FinLang Ltd Contributor Licence Agreement (CLA)**](docs/legal/CLA.md).

### Why a CLA?
FinLang Ltd maintains **dual licensing**:
- **Community Edition:** GNU AGPL-3.0-only  
- **Commercial Editions:** Proprietary licences (Solo, Team, Business, Enterprise)

The CLA allows your code to appear in **both** editions while you **retain copyright**.

### How to Accept
You only need to sign once.

- **Individuals:** Submitting your first Pull Request counts as acceptance.  
  Your GitHub username and timestamp act as your electronic signature.
- **Corporate contributors:**  
  Have an authorised signatory email a signed PDF of `docs/legal/CLA.md` to  
  `legal@finlang.io` before your first contribution.

> ⚖️ You keep your copyright.  
> FinLang Ltd receives permission to include your contribution in both open-source and commercial editions.

---

## 🧭 Contribution Workflow

### 1. Fork the Repository
Click **Fork** on GitHub and clone your fork:

```bash
git clone https://github.com/<your-username>/finlang.git
cd finlang
```

### 2. Create a Feature Branch
```bash
git checkout -b feature/my-enhancement
```

### 3. Make Your Changes
- Follow existing code style and documentation format.
- Add tests for any new functionality.
- Update relevant `.md` files if flags, syntax, or outputs change.

### 4. Verify and Test
Run the standard checks before committing:

```bash
pytest
python -m benchmarks.bench_finlang_harness --mode quick
finlang --rules examples/rules.demo.fin --input examples/sample.csv --output /dev/null --audit-mode none --headless
```

### 5. Commit and Push
```bash
git add -A
git commit -m "feat: <short summary of change>"
git push origin feature/my-enhancement
```

### 6. Open a Pull Request
Submit a PR to the **main** branch.  
A bot (or maintainer) will verify your CLA status.

Your PR should:
- Clearly describe the problem and solution.
- Include tests or examples where possible.
- Pass all CI checks.

---

## 🧱 Code Standards

- **Language:** Python ≥ 3.10  
- **Formatting:** `black` and `isort`  
- **Linting:** `flake8`  
- **Tests:** `pytest`  
- **Docs:** Markdown (`.md`) in `/docs`

Keep code **deterministic, testable, and auditable** — that’s FinLang’s ethos.

---

## 🧩 Reporting Issues

Before creating a new issue:
1. Search existing issues.
2. Include details: OS, Python version, FinLang version, and command used.
3. Attach minimal reproducible examples.

---

## 🧪 Pull Request Checklist

- [ ] I have read and accepted the [FinLang CLA](docs/legal/CLA.md).
- [ ] My contribution is my original work or I have rights to submit it.
- [ ] All tests pass locally.
- [ ] Documentation updated where relevant.
- [ ] I have added or confirmed changelog entries if applicable.

---

## 🧾 Governance & Licensing

- **Copyright:** You retain ownership.
- **Licensing:** FinLang Ltd may use your contributions in AGPL and commercial editions.
- **Attribution:** You will be credited in release notes and/or code comments.
- **No automatic compensation:** Contributions are voluntary.

---

## 📨 Contact

**Email:** [legal@finlang.io](mailto:legal@finlang.io)  
**Company:** FinLang Ltd  
**Jurisdiction:** Scotland, United Kingdom

---

Thank you for helping make FinLang stronger, safer, and faster for everyone.
