import socket
# On simule l'ESP32 depuis le PC lui-même
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(b"1000,500", ("127.0.0.1", 9091))