# 🧠 AI Toolbox

This repository contains an AI/ML toolkit powered by Python and Poetry.  
It uses `pyproject.toml` for dependency and environment management.

---

## ⚙️ Prerequisites

- Python ≥ 3.9.7 and < 3.15 (recommended: 3.12)
- [Poetry](https://python-poetry.org/) (for managing virtual environments & dependencies)
- Git (to clone this repo)

---

## 🚀 Installation Steps

### 1️⃣ Install Python

| OS      | Installation Instructions |
|---------|----------------------------|
| **macOS** | Install via Homebrew:<br>```brew install python@3.12``` |
| **Linux** | Use your package manager or install manually:<br>```sudo apt install python3.12 python3.12-venv``` |
| **Windows** | Download Python 3.12 from [python.org](https://www.python.org/downloads/) and check "Add to PATH" during install |

> ✅ After install, verify:
> ```bash
> python3 --version
> ```

---

### 2️⃣ Install Poetry

Run this in your terminal or shell (works for all OS):

```bash
curl -sSL https://install.python-poetry.org | python3 -
````

> After install, ensure `~/.local/bin` or equivalent is in your PATH:

#### Add to PATH:

| OS                         | Add this to your shell config                                               |
| -------------------------- | --------------------------------------------------------------------------- |
| **macOS/Linux (zsh/bash)** | Add to `~/.zshrc` or `~/.bashrc`:<br>`export PATH="$HOME/.local/bin:$PATH"` |
| **Windows (PowerShell)**   | Add `%USERPROFILE%\.local\bin` to Environment Variables                     |

Then restart your terminal and verify:

```bash
poetry --version
```

---

### 3️⃣ Clone and Set Up the Project

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

Poetry will read `pyproject.toml` and set up the virtual environment automatically:

```bash
poetry install
```

---

### 4️⃣ Activate the Virtual Environment

To run commands or Python files inside the virtual environment:

```bash
poetry shell
```

Then:

```bash
python script.py
```

To deactivate:

```bash
exit
```

---

### 5️⃣ Installing New Dependencies

To add a new library (e.g. `numpy`):

```bash
poetry add numpy
```

This will:

* Add it to `pyproject.toml`
* Lock its version in `poetry.lock`
* Install it in the virtualenv

---

## 🔍 Useful Commands

| Task                         | Command                       |
| ---------------------------- | ----------------------------- |
| Check which Python is used   | `poetry run which python`     |
| Show active virtualenv info  | `poetry env info`             |
| Add a dev dependency         | `poetry add --dev black`      |
| Run without activating shell | `poetry run python script.py` |

---

## ✅ Troubleshooting

* If `poetry` is not found, make sure `~/.local/bin` is in your `$PATH`
* If virtualenv isn't working, try deleting `.venv` or cached env and run `poetry install` again

---

## 📦 Packaging and Publishing (Optional)

If you're distributing this as a package:

```bash
poetry build
```

This will generate a `dist/` folder with a `.whl` and `.tar.gz`.

---