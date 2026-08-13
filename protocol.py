import json
import base64
import os

# tipovi poruka
MSG_REGISTER = "register"
MSG_AGENT_LIST = "agent_list"
MSG_AGENT_OFFLINE = "agent_offline"
MSG_HEARTBEAT = "heartbeat"
MSG_METRICS = "metrics"
MSG_ALERT = "alert"
MSG_COMMAND_RESULT = "command_result"
MSG_PROCESS_LIST = "process_list"
MSG_KILL_RESULT = "kill_result"
MSG_FILE_ACK = "file_ack"
MSG_COMMAND = "command"
MSG_PROCESS_LIST_REQUEST = "process_list_request"
MSG_KILL_PROCESS = "kill_process"
MSG_FILE = "file"

ALLOWED_COMMANDS = [
    "dir", "ls", "echo", "ping", "ipconfig", "ifconfig",
    "whoami", "hostname", "date", "tasklist", "systeminfo",
    "type", "cat"
]

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def is_command_allowed(command):
    if not command.strip():
        return False
    first_word = command.strip().split()[0].lower()
    return first_word in ALLOWED_COMMANDS


def send_message(sock, obj):
    line = json.dumps(obj) + "\n"
    sock.sendall(line.encode("utf-8"))


def recv_messages(buffer, data):
    buffer = buffer + data
    messages = []
    while b"\n" in buffer:
        line, buffer = buffer.split(b"\n", 1)
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line.decode("utf-8")))
        except:
            pass
    return messages, buffer


def encode_file(path):
    size = os.path.getsize(path)
    if size > MAX_FILE_SIZE:
        raise ValueError("Fajl je prevelik (max 10 MB)")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return data, size


def decode_file(b64_data, dest_dir, filename):
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    dest_path = os.path.join(dest_dir, filename)
    with open(dest_path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return dest_path
