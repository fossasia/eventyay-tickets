sysctl -w fs.file-max=12000500
sysctl -w fs.nr_open=20000500
ulimit -n 4000000
sysctl -w net.ipv4.tcp_mem='10000000 10000000 10000000'
sysctl -w net.ipv4.tcp_rmem='1024 4096 16384'
sysctl -w net.ipv4.tcp_wmem='1024 4096 16384'
sysctl -w net.ipv4.ip_local_port_range="1024 64000"
sysctl -w net.core.rmem_max=16384
sysctl -w net.core.wmem_max=16384
