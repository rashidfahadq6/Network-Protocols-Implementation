import socket
import struct
import os
import threading

class TCPServer:
    PORT = 8473  # Port for the server to listen on
    SEGMENT_SIZE = 500  # Size of each segment in bytes
    MAX_RETRIES = 5  # Maximum number of retries for failed segments

    def __init__(self, host="0.0.0.0"):
        """Initialize the server socket and bind it to the specified port."""
        self.host = host
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.PORT))
        self.server_socket.listen()
        print(f"Server is listening on {self.host}:{self.PORT}")

    def calculate_checksum(self, segment):
        """Compute a 16-bit one's complement checksum to detect transmission errors."""
        checksum = 0
        for i in range(0, len(segment), 2):
            value = (segment[i] << 8) + (segment[i + 1] if i + 1 < len(segment) else 0)
            checksum += value
            checksum = (checksum & 0xFFFF) + (checksum >> 16)
        return ~checksum & 0xFFFF

    def send_file(self, filename, conn):
        """Send a file in segmented form, ensuring exactly 4 segments are transmitted."""
        try:
            file_size = os.path.getsize(filename)
            if file_size < 2000:
                conn.sendall(b"ERROR: File too small (must be >= 2000 bytes)")
                return
            
            with open(filename, 'rb') as f:
                sequence_number = 0
                total_segments = 4  # Ensuring exactly 4 segments
                
                while sequence_number < total_segments:
                    segment = f.read(self.SEGMENT_SIZE)
                    if not segment:
                        print("[SERVER] ERROR: File ended before all 4 segments were sent.")
                        break  

                    sequence_number += 1
                    checksum = self.calculate_checksum(segment)
                    retries = 0
                    segment_sent = False
                    
                    while not segment_sent and retries < self.MAX_RETRIES:
                        packet = struct.pack('!I H I', sequence_number, checksum, len(segment)) + segment
                        
                        print(f"[SERVER] Sending segment {sequence_number}/4 with size {len(segment)} and checksum {checksum}")
                        try:
                            conn.sendall(packet)
                            conn.settimeout(5)  # Prevent infinite waiting
                            response = conn.recv(1024).decode()
                            print(f"[SERVER] Received response for segment {sequence_number}: {response}")

                            if response == "ACK":
                                print(f"[SERVER] Segment {sequence_number} acknowledged.")
                                segment_sent = True
                        except (socket.timeout, ConnectionResetError):
                            print(f"[SERVER] ERROR: Client disconnected while waiting for ACK on segment {sequence_number}. Stopping transmission.")
                            return  # Stop sending if client disconnects
                        except Exception as e:
                            print(f"[SERVER] ERROR: {e}")
                            return

                    if retries == self.MAX_RETRIES:
                        print(f"[SERVER] Segment {sequence_number} failed after {self.MAX_RETRIES} retries.")
                        conn.sendall(b"File transfer failed.")
                        return

            # **CHECK IF CLIENT IS STILL CONNECTED BEFORE SENDING END-OF-TRANSMISSION SIGNAL**
            try:
                conn.sendall(b"CHECK_CONNECTION")  # Dummy message to check connection
            except (socket.error, ConnectionResetError):
                print("[SERVER] Client disconnected before end-of-transmission signal. Avoiding error.")
                return  # Avoid sending the end signal if the client is gone

            # **SEND END-OF-TRANSMISSION SIGNAL (Fixed)**
            end_signal = struct.pack('!I H i', 0, 0, -1)
            conn.sendall(end_signal)
            print("[SERVER] End-of-transmission signal sent.")
            
            print("[SERVER] File transfer completed successfully.")
        except FileNotFoundError:
            conn.sendall(f"ERROR: The file '{filename}' does not exist.".encode())
    
    def handle_client(self, conn, addr):
        """Handles client requests and manages file transfer operations."""
        print(f"New client connected from {addr}")
        conn.sendall(f"Connected to server {self.host}:{self.PORT}".encode())
        try:
            while True:
                file_name = conn.recv(1024).decode().strip()
                print(f"Received request for file: {file_name}")
                if not file_name:
                    break
                if file_name.lower() == "quit":
                    print("Client requested termination.")
                    break
                
                if not os.path.exists(file_name):
                    print(f"File {file_name} not found!")
                    conn.sendall(f"ERROR: The file '{file_name}' does not exist.".encode())
                else:
                    print(f"Starting file transfer for: {file_name}")
                    conn.sendall(b"Start transfer")
                    self.send_file(file_name, conn)
        except ConnectionResetError:
            print("Client disconnected abruptly.")
        finally:
            conn.close()
            print("Client disconnected.")

    def run(self):
        """Start the server and continuously listen for incoming connections."""
        while True:
            conn, addr = self.server_socket.accept()
            client_thread = threading.Thread(target=self.handle_client, args=(conn, addr))
            client_thread.start()

if __name__ == "__main__":
    server = TCPServer()
    server.run()