import socket
import threading
import time
import os
import platform
import subprocess
import random
import string

import psutil
import protocol as proto

# podesavanja - promijeni ovo ako server nije lokalno
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9999

# generisi random ID za ovog agenta
AGENT_ID = "agent-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
hostname = socket.gethostname()
os_name = platform.system() + " " + platform.release()

sock = None
running = True


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


local_ip = get_local_ip()


def send_msg(data):
    global sock
    if sock is not None:
        try:
            proto.send_message(sock, data)
        except:
            pass


def heartbeat_loop():
    while running:
        send_msg({"type": proto.MSG_HEARTBEAT, "sender": AGENT_ID})
        time.sleep(5)


def metrics_loop():
    cpu_high_count = 0
    while running:
        try:
            cpu = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()

            if os.name == "nt":
                dk = psutil.disk_usage("C:\\")
            else:
                dk = psutil.disk_usage("/")

            ram_used = round(vm.used / 1000000000, 2)
            ram_total = round(vm.total / 1000000000, 2)
            disk_used = round(dk.used / 1000000000, 2)
            disk_total = round(dk.total / 1000000000, 2)

            send_msg({
                "type": proto.MSG_METRICS,
                "sender": AGENT_ID,
                "cpu": cpu,
                "ram_used": ram_used,
                "ram_total": ram_total,
                "disk_used": disk_used,
                "disk_total": disk_total
            })

            # upozorenje ako je CPU previsok
            if cpu > 90:
                cpu_high_count += 1
                if cpu_high_count == 3:
                    send_msg({
                        "type": proto.MSG_ALERT,
                        "sender": AGENT_ID,
                        "level": "warning",
                        "message": f"CPU upotreba visoka: {cpu:.1f}%"
                    })
            else:
                cpu_high_count = 0

        except Exception as e:
            print(f"[AGENT] Greska u metrics loopu: {e}")

        time.sleep(2)


def handle_command(msg):
    command = msg.get("command", "").strip()
    print(f"[AGENT] Primljena komanda: {command}")

    if not proto.is_command_allowed(command):
        send_msg({
            "type": proto.MSG_COMMAND_RESULT,
            "sender": AGENT_ID,
            "target": "controller",
            "command": command,
            "output": "Komanda nije dozvoljena.",
            "exit_code": -1
        })
        return

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        output = "Komanda je trajala predugo (timeout)."
        exit_code = -1
    except Exception as e:
        output = f"Greska: {e}"
        exit_code = -1

    send_msg({
        "type": proto.MSG_COMMAND_RESULT,
        "sender": AGENT_ID,
        "target": "controller",
        "command": command,
        "output": output,
        "exit_code": exit_code
    })


def handle_process_list(msg):
    procs = []
    try:
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                info = p.info
                mem = 0
                if info["memory_info"]:
                    mem = round(info["memory_info"].rss / 1000000, 2)
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"] or "",
                    "cpu": info["cpu_percent"] or 0.0,
                    "memory": mem
                })
            except:
                pass

        # sortiraj po memoriji i uzmi top 30
        procs.sort(key=lambda x: x["memory"], reverse=True)
        procs = procs[:30]

    except Exception as e:
        print(f"[AGENT] Greska pri dohvatanju procesa: {e}")

    send_msg({
        "type": proto.MSG_PROCESS_LIST,
        "sender": AGENT_ID,
        "target": "controller",
        "processes": procs
    })


def handle_kill(msg):
    pid = msg.get("pid")
    success = False
    message = ""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        success = True
        message = f"Proces {pid} ugasen."
        print(f"[AGENT] Ugasen PID {pid}")
    except psutil.NoSuchProcess:
        message = f"Proces {pid} ne postoji."
    except psutil.AccessDenied:
        message = f"Pristup odbijen za PID {pid}."
    except Exception as e:
        message = f"Greska: {e}"

    send_msg({
        "type": proto.MSG_KILL_RESULT,
        "sender": AGENT_ID,
        "target": "controller",
        "pid": pid,
        "success": success,
        "message": message
    })


def handle_file(msg):
    filename = msg.get("filename", "fajl")
    b64_data = msg.get("data", "")
    try:
        saved = proto.decode_file(b64_data, "received", filename)
        print(f"[AGENT] Fajl sacuvan: {saved}")
        send_msg({
            "type": proto.MSG_FILE_ACK,
            "sender": AGENT_ID,
            "target": "controller",
            "filename": filename,
            "saved_path": saved
        })
    except Exception as e:
        print(f"[AGENT] Greska pri prijemu fajla: {e}")
        send_msg({
            "type": proto.MSG_FILE_ACK,
            "sender": AGENT_ID,
            "target": "controller",
            "filename": filename,
            "saved_path": "",
            "error": str(e)
        })


def receive_loop(conn):
    buf = b""
    while running:
        try:
            data = conn.recv(4096)
            if not data:
                print("[AGENT] Server zatvorio konekciju.")
                break
            msgs, buf = proto.recv_messages(buf, data)
            for msg in msgs:
                msg_type = msg.get("type", "")
                if msg_type == proto.MSG_COMMAND:
                    threading.Thread(target=handle_command, args=(msg,), daemon=True).start()
                elif msg_type == proto.MSG_PROCESS_LIST_REQUEST:
                    threading.Thread(target=handle_process_list, args=(msg,), daemon=True).start()
                elif msg_type == proto.MSG_KILL_PROCESS:
                    threading.Thread(target=handle_kill, args=(msg,), daemon=True).start()
                elif msg_type == proto.MSG_FILE:
                    threading.Thread(target=handle_file, args=(msg,), daemon=True).start()
        except Exception as e:
            if running:
                print(f"[AGENT] Greska u receive loopu: {e}")
            break


def main():
    global sock, running

    print(f"Agent ID: {AGENT_ID}")
    print(f"Hostname: {hostname}")
    print(f"OS: {os_name}")
    print(f"Lokalni IP: {local_ip}")
    print(f"Server: {SERVER_HOST}:{SERVER_PORT}")
    print("Pritisni Ctrl+C za zaustavljanje.\n")

    # inicijalizacija CPU brojaca
    psutil.cpu_percent(interval=None)

    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=metrics_loop, daemon=True).start()

    try:
        while running:
            try:
                print(f"[AGENT] Povezivanje na {SERVER_HOST}:{SERVER_PORT}...")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((SERVER_HOST, SERVER_PORT))

                proto.send_message(sock, {
                    "type": proto.MSG_REGISTER,
                    "role": "agent",
                    "agent_id": AGENT_ID,
                    "hostname": hostname,
                    "os": os_name,
                    "ip": local_ip
                })
                print("[AGENT] Uspjesno konektovan!")

                receive_loop(sock)

            except ConnectionRefusedError:
                print("[AGENT] Server nije dostupan. Pokusavam ponovo za 5 sekundi...")
            except Exception as e:
                print(f"[AGENT] Greska: {e}")
            finally:
                if sock:
                    try:
                        sock.close()
                    except:
                        pass
                sock = None

            if running:
                print("[AGENT] Rekonektovanje za 5 sekundi...")
                time.sleep(5)

    except KeyboardInterrupt:
        running = False
        print("[AGENT] Agent zaustavljen.")


if __name__ == "__main__":
    main()
