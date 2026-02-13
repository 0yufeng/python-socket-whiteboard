import socket
import threading
import json

# 所有網卡(local host、Wi-Fi IP、有線網路IP)
HOST = "0.0.0.0"
PORT = 5001

all_strokes = {}  
# stroke_id -> stroke dict
# 存畫面狀態

def get_local_wifi_ip():
    """
    取得本機在 Wi-Fi / LAN 上的 IP
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


lock = threading.Lock()
clients = {}  # conn -> {"id": 1/2, "addr": (ip,port)}

def send_json(conn: socket.socket, obj: dict):
    data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
    conn.sendall(data)

def safe_send(conn, obj):
    try:
        send_json(conn, obj)
    except:
        pass

# 轉發 Relay
# 收到的內容轉播給另個
def broadcast(except_conn, obj):
    data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
    with lock:
        for c in list(clients.keys()):
            if c is except_conn:
                continue
            try:
                c.sendall(data)
            except:
                pass

def update_partner_status():
    """Send partner status to each client: partner_online True/False"""
    with lock:
        ids = [info["id"] for info in clients.values()]
        online_1 = 1 in ids
        online_2 = 2 in ids

        for conn, info in list(clients.items()):
            cid = info["id"]
            partner_online = online_2 if cid == 1 else online_1
            safe_send(conn, {"type": "status", "state": "paired" if partner_online else "waiting",
                             "partner_online": partner_online})

# 新增，用來處理畫畫可以存
def handle_message(conn, msg):
    global all_strokes

    t = msg.get("type")

    if t == "stroke_begin":
        sid = msg["stroke_id"]
        all_strokes[sid] = {
            "id": sid,
            "owner": msg["owner"],
            "shape": msg.get("shape", "line"),
            "color": msg.get("color"),
            "w": msg.get("w"),
            "size": msg.get("size"),
            "points": [(msg["x"], msg["y"])]
        }

    elif t == "stroke_point":
        sid = msg["stroke_id"]
        if sid in all_strokes:
            all_strokes[sid]["points"].append((msg["x"], msg["y"]))

    elif t == "delete_stroke":
        sid = msg["stroke_id"]
        all_strokes.pop(sid, None)

    elif t == "clear":
        all_strokes.clear()


def handle_client(conn: socket.socket, addr):
    try:
        buf = b""
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                # 任何 client 的事件都轉發給另一位
                msg = json.loads(line)
                handle_message(conn, msg)
                broadcast(conn, msg)
    except:
        pass
    finally:
        with lock:
            info = clients.pop(conn, None)
        try:
            conn.close()
        except:
            pass
        print(f"[-] Disconnected {addr} (id={info['id'] if info else None})")
        update_partner_status()

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # 建立連線
        # AF_INET->IPv4
        # SOCK_STREAM->TCP
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        wifi_ip = get_local_wifi_ip()

        print("======================================")
        print(" Two-Player Painter Server Started ")
        print("======================================")
        print(f" Wi-Fi IP : {wifi_ip}")
        print(f" Port     : {PORT}")
        print("--------------------------------------")
        print(f" Clients should connect to:")
        print(f"   {wifi_ip}:{PORT}")
        print("======================================")

        #print(f"Server listening on {HOST}:{PORT}")

        while True:
            # Client connect() → Server accept()
            # 產生專用通道conn
            # 一個client對應一個socket
            conn, addr = s.accept()
            with lock:
                if len(clients) >= 2:
                    safe_send(conn, {"type": "error", "msg": "Server full (max 2)"})
                    conn.close()
                    print("[!] Reject: server full")
                    continue

                assigned = 1 if 1 not in [v["id"] for v in clients.values()] else 2
                clients[conn] = {"id": assigned, "addr": addr}

            print(f"[+] Connected {addr}, assigned id={assigned}")
            safe_send(conn, {"type": "hello", "client_id": assigned})
            # 把目前畫面狀態送給新 client
            safe_send(conn, {
                "type": "full_state",
                "strokes": list(all_strokes.values())
            })
            update_partner_status()

            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
