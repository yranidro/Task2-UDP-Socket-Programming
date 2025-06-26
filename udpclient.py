import socket
import time
import struct
import random
import pandas as pd
import numpy as np
import argparse


class UDPClient:
    def __init__(self, server_ip, server_port, window_size=400):
        # 创建UDP socket
        self.client_socket=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_addr=(server_ip, server_port)  # 服务器地址
        self.server_size=window_size               # 发送窗口大小
        self.timeout=0.3                           # 超时时间300ms
        self.rtt_list = []                         # 存储RTT时间的列表
        self.base_seq=1                            # 窗口基序号，从1开始
        self.next_seq=1                            # 下一个要发送的序号，从1开始
        self.packets = {}                          # 存储已发送的数据包
        self.byte_offset = 0                       # 当前总字节偏移量

    def connect(self):
        # 打包SYN包（类型1 序列号0 确认号0 数据长度0）
        syn=struct.pack('!BHHH', 1, 0, 0, 0)
        self.client_socket.sendto(syn, self.server_addr)

        try:
            # 设置socket超时
            self.client_socket.settimeout(self.timeout)
            # 等待服务器响应
            data, _ = self.client_socket.recvfrom(1024)
            # 解包响应头
            header=struct.unpack('!BHHH', data[:7])

            # 检查是否是SYN-ACK响应
            if header[0] == 2 and header[2] == syn[1]+1:
                # 打包ACK包（类型3 序列号=服务器确认号 确认号=服务器序列号+1 数据长度0）
                ack=struct.pack('!BHHH', 3, header[2], header[1]+1, 0)
                self.client_socket.sendto(ack, self.server_addr)
                print("连接建立成功")
                return True
        except socket.timeout:
            print("连接超时")
            return False

    def send_data(self, total_packets=30):
        if not self.connect():
            return

        # 初始化统计变量
        sent_packets=0          # 已发送包数
        acked_packets=0         # 已确认包数
        start_time=time.perf_counter()  # 开始时间

        while acked_packets < total_packets:
            # 滑动窗口控制：当窗口未满且还有包要发送时
            current_window_bytes = sum(
                self.packets[seq]['end_byte'] - self.packets[seq]['start_byte'] + 1
                for seq in range(self.base_seq, self.next_seq)
            )
            while current_window_bytes < self.server_size and self.next_seq <= total_packets:
                # 生成40-80字节的随机数据
                data_size=random.randint(40, 80)
                # 检查是否会超出窗口限制
                if current_window_bytes + data_size > self.server_size:
                    break
                payload=bytes([random.randint(0, 255) for _ in range(data_size)])

                # 构建数据包（类型4 序列号=next_seq 确认号0 数据长度=data_size）
                pkt=struct.pack('!BHHH', 4, self.next_seq, 0, data_size) + payload

                # 存储数据包
                self.packets[self.next_seq] = {
                    'data':pkt,               # 包数据
                    'send_time':time.perf_counter(),  # 发送时间
                    'retries':0,              # 重试次数
                    'start_byte':self.byte_offset,               # 记录当前起始字节
                    'end_byte':self.byte_offset + data_size - 1  # 记录当前结束字节
                }

                # 发送数据包
                self.client_socket.sendto(pkt, self.server_addr)
                print(f"第{self.next_seq}个（第{self.byte_offset}~{self.byte_offset + data_size - 1}字节）client端已发送")
                self.byte_offset += data_size

                sent_packets+=1
                self.next_seq+=1

                current_window_bytes += data_size

            # 接收ACK包
            try:
                self.client_socket.settimeout(self.timeout)
                data, _ = self.client_socket.recvfrom(1024)
                # 解包响应头
                header=struct.unpack('!BHHH', data[:7])

                # 处理ACK包
                if header[0] == 3:
                    ack_num=header[2]  # 确认号

                    # 如果ACK是对base_seq的确认，才移动窗口
                    if ack_num >= self.base_seq:
                        # 计算RTT
                        rtt=(time.perf_counter()-self.packets[ack_num]['send_time']) * 1000
                        self.rtt_list.append(rtt)  # 记录RTT
                        print(f"第{ack_num}个（第{self.packets[ack_num]['start_byte']}~{self.packets[ack_num]['end_byte']}字节）server端已收到，RTT 是 {rtt:.2f} ms")
                        #移动窗口基序号
                        self.base_seq=ack_num+1
                        acked_packets=ack_num

                        # 动态调整超时时间（最近5个RTT的平均值的5倍）
                        if len(self.rtt_list)>5:
                            self.timeout=5 * np.mean(self.rtt_list[-5:]) / 1000

            except socket.timeout:
                # 超时处理：重传窗口内所有未确认的包
                for seq in range(self.base_seq, self.next_seq):
                    print(f"重传第{seq}个（第{self.packets[seq]['start_byte']}~{self.packets[seq]['end_byte']}字节）数据包")
                    self.packets[seq]['send_time']=time.perf_counter()
                    self.client_socket.sendto(self.packets[seq]['data'], self.server_addr)
                    self.packets[seq]['retries']+=1

        # 传输完成后打印统计信息
        self.print_states(sent_packets, total_packets, start_time)

    def print_states(self, sent_packets, total_packets, start_time):
        total_retransmissions = sum(p['retries'] for p in self.packets.values())
        print(f"丢包率：{(total_packets / (total_packets+total_retransmissions)) * 100:.2f}%")
        if self.rtt_list:
            df=pd.DataFrame(self.rtt_list, columns=['RTT'])
            print(f"最大RTT: {df['RTT'].max():.2f}ms")
            print(f"最小RTT: {df['RTT'].min():.2f}ms")
            print(f"平均RTT: {df['RTT'].mean():.2f}ms")
            print(f"RTT标准差: {df['RTT'].std():.2f}ms")

if __name__ == '__main__':
    # 处理命令行参数
    parser=argparse.ArgumentParser()
    parser.add_argument('ip', help='服务器IP地址')
    parser.add_argument('port', type=int, help='服务器端口号')
    args=parser.parse_args()

    # 创建客户端实例并发送数据
    client=UDPClient(args.ip, args.port)
    client.send_data()
