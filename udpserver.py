import socket
import random
from threading import Thread, Lock
import struct

class UDPServer:
    def __init__(self, host='0.0.0.0', port=54321):
        # 创建UDP socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((host, port))  # 绑定到指定地址和端口
        self.drop_rate = 0.3  # 丢包率=30%
        self.connections = {}  # 用于存储客户端连接状态的字典
        self.conn_locks = {}   # 为每个客户端单独管理线程锁

    def handle_client(self, data, client_addr):
        # 解包数据头（类型1B 序列号2B 确认号2B 数据长度2B）
        header = struct.unpack('!BHHH', data[:7])
        pkt_type = header[0]  # 获取数据包类型

        # 处理SYN包
        if pkt_type == 1:
            print(f"收到来自 {client_addr} 的连接请求")
            # 打包SYN-ACK响应包（类型2 序列号0 确认号=客户端序列号+1 数据长度0）
            syn_ack = struct.pack('!BHHH', 2, 0, header[1] + 1, 0)
            self.server_socket.sendto(syn_ack, client_addr)
            # 初始化连接状态，记录期望的序列号和上一次确认的序列号，期望序号从1开始
            self.connections[client_addr] = {'status': 'connected', 'expected_seq': 1, 'last_ack': 0, 'out_of_order_ack': False}
            self.conn_locks[client_addr] = Lock()

        # 处理数据包
        elif pkt_type == 4:
            seq_num = header[1]  # 序列号
            data_len = header[3]  # 数据长度
            payload = data[7:7 + data_len]  # 有效数据

            if client_addr not in self.conn_locks:
                return

            with self.conn_locks[client_addr]:
                conn = self.connections.get(client_addr)
                expected_seq = conn['expected_seq']

                # 随机决定是否丢包
                if random.random() < self.drop_rate:
                    print(f"丢包：来自 {client_addr} 的数据包 #{seq_num}")
                    return

                if seq_num == expected_seq:
                    print(f"收到来自 {client_addr} 的数据包 #{seq_num}")
                    # 打包ACK响应包（类型3 序列号=收到的序列号 确认号=收到的序列号 数据长度0）
                    ack = struct.pack('!BHHH', 3, seq_num, seq_num, 0)
                    self.server_socket.sendto(ack, client_addr)
                    # 更新连接状态
                    conn['expected_seq'] += 1
                    conn['last_ack'] = seq_num
                    conn['out_of_order_ack'] = False
                else:
                    if not conn.get('out_of_order_ack', False):
                        print(f"收到乱序包#{seq_num}，期望#{expected_seq}，发送ACK#{conn['last_ack']}")
                        # 发送乱序包引起的ACK
                        ack = struct.pack('!BHHH', 3, conn['last_ack'], conn['last_ack'], 0)
                        self.server_socket.sendto(ack, client_addr)
                        conn['out_of_order_ack'] = True
                    else:
                        print(f"收到乱序包#{seq_num}，期望#{expected_seq}")

    def start(self):
        print("UDP服务启动...")
        while True:
            # 接收客户端数据
            data, addr = self.server_socket.recvfrom(1024)
            # 为每个客户端请求创建新线程
            Thread(target=self.handle_client, args=(data, addr)).start()

if __name__ == '__main__':
    # 创建服务器实例并启动
    server = UDPServer()
    server.start()
