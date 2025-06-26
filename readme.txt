1. 程序概述
本项目实现了一个基于UDP的可靠文件传输协议，包含以下功能：
    - 模拟TCP三次握手建立连接
    - 滑动窗口流量控制
    - 超时重传机制
    - 动态RTT估计
    - 丢包率统计

2. 运行环境
    操作系统：Windows/Linux
    Python版本：3.6及以上
    依赖库：pandas, numpy

3. 文件说明
    udpserver.py   服务器端程序
    udpclient.py    客户端程序

4. 配置选项
    参数         默认值           说明
    ip	             无         服务器IP地址
    port	     无         服务器端口号

5. 使用示例
    启动服务器：
	python udpserver.py
    启动客户端：
	python udpclient.py 127.0.0.1 54321
