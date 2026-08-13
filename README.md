# Remote Control Center

A networked fleet-management system where a single **Controller** GUI remotely monitors and controls multiple **Agent** machines in real time over raw TCP sockets. A stateless **Server** routes messages between them.

```
   [Controller GUI]
         │
         │  TCP + JSON (newline-framed)
         ▼
   ┌───────────────┐
   │ Central Server│  ← pure router, no business logic
   └───────────────┘
         │
   ┌─────┼──────────────┐
   ▼     ▼              ▼
[Agent] [Agent]  ...  [Agent]
```

## Install

```
pip install -r requirements.txt
```

Requires Python 3.10+.

## Run (localhost demo)

Open four separate terminals in the project directory.

**Terminal 1 — Server**
```
python server.py
```
Listens on `0.0.0.0:9999` by default. Override with `--host` and `--port`.

**Terminal 2 & 3 (& 4) — Agents**
```
python agent.py --host 127.0.0.1 --port 9999
```
Each process generates its own `agent-XXXXXXXX` ID. Run two or three for the demo.

**Terminal 4 — Controller GUI**
```
python controller.py
```
A login window appears. Enter `127.0.0.1`, port `9999`, password `controller123`, then click **Connect**.

> **LAN usage:** replace `127.0.0.1` with the server machine's LAN IP on agents and the controller.

## Whitelisted commands

The agent executes only these commands (first token, case-insensitive):

```
cat  date  dir  echo  hostname  ifconfig  ipconfig
ls   ping  systeminfo  tasklist  type  whoami
```

Any other command returns `"Command not permitted"` with exit code `-1`.

## Kill-process demo note

Before demonstrating process kill, launch a harmless dummy process first:

- **Windows:** open Notepad (`notepad.exe`) or run `start notepad` in a terminal.
- **Linux/macOS:** run `sleep 9999 &` in a terminal.

Then use the Controller's **Process List → Refresh → Kill Process** flow to terminate it.  
**Never target a system-critical PID** during the demo.

## File transfer

The Controller's **Send File** panel rejects files larger than 10 MB before sending.  
Received files are saved on the agent under `received/` relative to its working directory.

## Architecture notes

| Concern | Choice |
|---|---|
| Language | Python 3.10+ |
| Networking | `socket` + `threading` |
| Server concurrency | `ThreadPoolExecutor` (one thread per connection) |
| System metrics | `psutil` |
| Command execution | `subprocess` (whitelisted only) |
| GUI | `customtkinter` dark theme |
| Wire protocol | newline-delimited JSON over TCP |
| Logging | `logging` with timestamps |

All state lives in memory; restarting the server clears every registry.
