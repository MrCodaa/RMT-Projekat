import socket
import threading
import time

import protocol as proto

HOST = "0.0.0.0"
PORT = 9999
PASSWORD = "controller123"

# globalne varijable
agents = {}  # agent_id -> info dict
controller_conn = None
lock = threading.Lock()


def send_to_controller(msg):
    global controller_conn
    with lock:
        conn = controller_conn
    if conn:
        try:
            proto.send_message(conn, msg)
        except:
            pass


def push_agent_list():
    with lock:
        lista = []
        for agent_id in agents:
            info = agents[agent_id]
            lista.append({
                "agent_id": agent_id,
                "hostname": info["hostname"],
                "os": info["os"],
                "ip": info["ip"],
                "status": info["status"],
                "last_heartbeat": info["last_heartbeat"]
            })
    send_to_controller({"type": proto.MSG_AGENT_LIST, "agents": lista})


def send_to_agent(agent_id, msg):
    with lock:
        info = agents.get(agent_id)
    if info and info["status"] == "online":
        try:
            proto.send_message(info["conn"], msg)
            return True
        except:
            remove_agent(agent_id, "greska pri slanju")
    return False


def remove_agent(agent_id, reason="veza prekinuta"):
    with lock:
        info = agents.pop(agent_id, None)
    if info:
        try:
            info["conn"].close()
        except:
            pass
        print(f"[SERVER] Agent {agent_id} diskonektovan: {reason}")
        send_to_controller({"type": proto.MSG_AGENT_OFFLINE, "agent_id": agent_id, "reason": reason})
        push_agent_list()


def route_message(msg, sender_id):
    msg_type = msg.get("type", "")
    target = msg.get("target", "")

    if msg_type == proto.MSG_HEARTBEAT:
        with lock:
            if sender_id in agents:
                agents[sender_id]["last_heartbeat"] = time.time()
                agents[sender_id]["status"] = "online"
        return

    if msg_type == proto.MSG_METRICS or msg_type == proto.MSG_ALERT:
        send_to_controller(msg)
        return

    if target == "controller":
        send_to_controller(msg)
    elif target != "":
        with lock:
            postoji = target in agents
        if postoji:
            send_to_agent(target, msg)
        else:
            print(f"[SERVER] Agent {target} nije pronadjen")
    else:
        print(f"[SERVER] Poruka bez targeta, tip={msg_type}")


def handle_controller(conn, addr, buf, pending):
    global controller_conn
    print(f"[SERVER] Controller konektovan sa {addr}")
    push_agent_list()

    try:
        for msg in pending:
            route_message(msg, "controller")

        while True:
            data = conn.recv(4096)
            if not data:
                break
            msgs, buf = proto.recv_messages(buf, data)
            for msg in msgs:
                route_message(msg, "controller")
    except:
        pass
    finally:
        with lock:
            if controller_conn is conn:
                controller_conn = None
        try:
            conn.close()
        except:
            pass
        print("[SERVER] Controller diskonektovan")


def handle_agent(conn, addr, reg, buf, pending):
    agent_id = reg["agent_id"]
    print(f"[SERVER] Agent {agent_id} konektovan sa {addr}")

    with lock:
        agents[agent_id] = {
            "conn": conn,
            "hostname": reg.get("hostname", "unknown"),
            "os": reg.get("os", "unknown"),
            "ip": reg.get("ip", addr[0]),
            "last_heartbeat": time.time(),
            "status": "online"
        }
    push_agent_list()

    try:
        for msg in pending:
            if msg.get("type") != proto.MSG_HEARTBEAT:
                msg["sender"] = agent_id
            route_message(msg, agent_id)

        while True:
            data = conn.recv(4096)
            if not data:
                break
            msgs, buf = proto.recv_messages(buf, data)
            for msg in msgs:
                if msg.get("type") != proto.MSG_HEARTBEAT:
                    msg["sender"] = agent_id
                route_message(msg, agent_id)
    except:
        pass
    finally:
        remove_agent(agent_id, "veza prekinuta")


def handle_connection(conn, addr):
    global controller_conn
    buf = b""
    reg = None
    pending = []

    try:
        while reg is None:
            data = conn.recv(4096)
            if not data:
                conn.close()
                return
            msgs, buf = proto.recv_messages(buf, data)
            for i in range(len(msgs)):
                msg = msgs[i]
                if msg.get("type") == proto.MSG_REGISTER:
                    reg = msg
                    pending = msgs[i + 1:]
                    break

        role = reg.get("role", "")

        if role == "controller":
            password = reg.get("password", "")
            if password != PASSWORD:
                proto.send_message(conn, {"type": "error", "message": "Pogresna lozinka"})
                conn.close()
                return
            with lock:
                if controller_conn is not None:
                    proto.send_message(conn, {"type": "error", "message": "Controller je vec konektovan"})
                    conn.close()
                    return
                controller_conn = conn
            handle_controller(conn, addr, buf, pending)

        elif role == "agent":
            agent_id = reg.get("agent_id", "")
            if not agent_id:
                conn.close()
                return
            handle_agent(conn, addr, reg, buf, pending)

        else:
            print(f"[SERVER] Nepoznata rola: {role}")
            conn.close()

    except Exception as e:
        print(f"[SERVER] Greska sa {addr}: {e}")
        try:
            conn.close()
        except:
            pass


def watchdog():
    while True:
        time.sleep(5)
        now = time.time()

        with lock:
            timed_out = []
            for agent_id in agents:
                info = agents[agent_id]
                if info["status"] == "online" and now - info["last_heartbeat"] > 15:
                    timed_out.append(agent_id)

        for agent_id in timed_out:
            print(f"[SERVER] Agent {agent_id} nije slao heartbeat, oznacen offline")
            with lock:
                if agent_id in agents:
                    agents[agent_id]["status"] = "offline"
            send_to_controller({
                "type": proto.MSG_AGENT_OFFLINE,
                "agent_id": agent_id,
                "reason": "heartbeat timeout"
            })
            push_agent_list()


def main():
    threading.Thread(target=watchdog, daemon=True).start()

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(64)
    print(f"[SERVER] Slusam na {HOST}:{PORT}")

    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=handle_connection, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("[SERVER] Gasim server...")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()
