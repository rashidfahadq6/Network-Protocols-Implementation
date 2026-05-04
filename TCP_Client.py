import socket
import struct

def calculate_checksum(segment):
    """Compute a 16-bit one's complement checksum to detect transmission errors."""
    sum = 0
    for i in range(0, len(segment), 2):
        value = (segment[i] & 0xFF) << 8
        if i + 1 < len(segment):
            value |= (segment[i + 1] & 0xFF)
        sum += value
        if (sum & 0xFFFF0000) != 0:
            sum = (sum & 0xFFFF) + (sum >> 16)
    return ~sum & 0xFFFF

def recv_exactly(sock, size):
    """Ensure we receive exactly `size` bytes before proceeding."""
    data = b""
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            return None  # Connection closed
        data += part
    return data

def receive_file(file_name, client_socket):
    """Receive file segments and store them in the correct order."""
    segments = {}

    while True:
        try:
            print("[CLIENT] Waiting to receive segment...")
            
            # **Ensure we receive exactly 10 bytes for the header**
            header = recv_exactly(client_socket, 10)
            if not header:
                print("[CLIENT] ERROR: Connection closed while receiving header.")
                break  # Stop if header is incomplete
            
            sequence_number, received_checksum, segment_size = struct.unpack('!I H I', header)

            # **Check for End-of-Transmission Signal**
            if segment_size == -1:
                print("[CLIENT] End-of-transmission signal received. Stopping file reception.")
                break

            print(f"[CLIENT] Sequence Number: {sequence_number}")
            print(f"[CLIENT] Received Checksum: {received_checksum}")
            print(f"[CLIENT] Segment Size: {segment_size}")

            # **Ensure we receive the full segment**
            segment = recv_exactly(client_socket, segment_size)
            if not segment:
                print("[CLIENT] ERROR: Connection closed while receiving segment.")
                break

            calculated_checksum = calculate_checksum(segment)

            print(f"[CLIENT] Received Segment {sequence_number} with size {segment_size} and checksum {received_checksum}")
            print(f"[CLIENT] Fully read segment {sequence_number} with size {segment_size}")
            print(f"[CLIENT] Calculated checksum for segment {sequence_number}: {calculated_checksum}")

            if calculated_checksum == received_checksum:
                print(f"[CLIENT] Segment {sequence_number} received correctly, sending ACK.")
                client_socket.sendall(b'ACK')
                segments[sequence_number] = segment
            else:
                print(f"[CLIENT] Checksum mismatch for segment {sequence_number}, sending NACK.")
                client_socket.sendall(b'NACK')
        except Exception as e:
            print(f"[CLIENT] ERROR: {e}")
            break

    with open("received_" + file_name, "wb") as file:
        for key in sorted(segments.keys()):
            file.write(segments[key])

    print("[CLIENT] File received successfully.")

def main():
    server_ip = input("Enter Server IP: ")
    server_port = 8473  
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((server_ip, server_port))
            print(client_socket.recv(1024).decode())  # Receive initial server message
            
            while True:
                file_name = input("Enter File Name: ")
                if not file_name:
                    print("File name cannot be empty.")
                    continue
                
                client_socket.sendall(file_name.encode())
                
                response = client_socket.recv(1024).decode()
                print(f"Server response: {response}")
                if response.startswith("ERROR"):
                    print(response)
                else:
                    receive_file(file_name, client_socket)
    except Exception as e:
        print("Server is down, please try again later.")
        print(e)

if __name__ == "__main__":
    main()