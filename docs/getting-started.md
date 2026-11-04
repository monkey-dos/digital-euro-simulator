# Getting started on your own computer

This guide takes you from nothing to the running control room. It was tested on macOS 26 (November 2026). Linux works the same way; Windows is not supported yet (stopping the apps uses a Unix-only call).

You need **Python 3.11 or newer** and **git**. The `python3` that ships with macOS is 3.9 and is too old.

## 1. Get Python 3.11+ with uv (recommended)

[uv](https://pypi.org/project/uv/) downloads Python into your user folder. No installer window, no admin password. (The python.org installer package can fail on recent macOS with "com.apple.installer.pagecontroller error -1"; uv avoids it.)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close the terminal completely (macOS: Cmd+Q) and open it again, then check:

```bash
uv --version          # expected: uv 0.x.y
uv python install 3.13
```

## 2. Get the code

```bash
cd ~
git clone https://github.com/monkey-dos/digital-euro-simulator.git
cd ~/digital-euro-simulator
```

On macOS, the first `git` command may open a window offering to install the "command line developer tools". That is normal: click Install, then run the command again.

## 3. Create the project environment (once)

```bash
uv venv --python 3.13 .venv
source .venv/bin/activate          # the prompt now starts with (.venv)
uv pip install -r apps/desp/requirements.txt -r apps/psp/requirements.txt -r apps/network-relay/requirements.txt
python3 --version                  # expected: Python 3.13.x
```

`pip` on its own is often not available on macOS; inside the environment, `uv pip` does the same job.

## 4. Start and test

```bash
python3 tools/run_local.py --control-room
```

Expected: `All apps are up: …` and `Control room: http://127.0.0.1:8100/`. Open that address in your browser.

Test: three green dots at the top right (central platform, PSP A, PSP B). Pick "Anna (PSP A) pays Ben (PSP B) 50 EUR" and press **Run scenario**. At the end Anna has 70.00 €, Ben 130.00 €, and the bookkeeping check says "Balanced".

Stop with Ctrl+C.

## Every next time

The environment only applies to the terminal window where you switched it on. In each new window:

```bash
cd ~/digital-euro-simulator
source .venv/bin/activate
python3 tools/run_local.py --control-room
```

## If something goes wrong

| You see | Why | Do this |
|---|---|---|
| `python3 --version` says `Python 3.9.6` | The environment is not switched on (new window), or it was made with the old Python | Run `cd ~/digital-euro-simulator` and `source .venv/bin/activate`. Still 3.9? `deactivate`, `rm -rf .venv`, then step 3 again |
| `command not found: pip` | macOS has no `pip` command | Use step 3 (`uv pip install …`) |
| `can't open file '…/tools/run_local.py'` | You are not in the project folder | `cd ~/digital-euro-simulator` |
| `command not found: uv` | The terminal was not reopened after installing uv | Close it with Cmd+Q and open it again |
| `Already running: …` | The apps are still running in another window | Stop them there with Ctrl+C |

Already have Python 3.11+ (for example from python.org or Homebrew)? Then `python3 -m venv .venv`, `source .venv/bin/activate` and `pip install -r …` work as well.
