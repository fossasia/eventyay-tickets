# Load test results

Newest result first.

## 2021-08-27 docker compose gunicorn on single CPX51

Changes:
- fixed missing body in chat message

### Run 1

- joining clients: 33.3/s
- mean time to chat message: 15s
- silent users: 99%

```
chat_message_time.......: avg=3.52s    min=-8000000ns med=1.03s  max=59.71s   p(90)=9.15s  p(95)=14.66s
checks..................: 74.67% ✓ 10489       ✗ 3557   
✗ { ping:no-timeout }...: 89.84% ✓ 7067        ✗ 799    
concurrent_clients......: 2333   33.310459/s
data_received...........: 519 MB 7.4 MB/s
data_sent...............: 22 MB  317 kB/s
ping_time...............: avg=3.54s    min=0s         med=1.06s  max=34.34s   p(90)=10s    p(95)=11.22s
request_response_time...: avg=797.08ms min=2ms        med=229ms  max=44.34s   p(90)=1.55s  p(95)=3.26s  
vus.....................: 2333   min=33        max=2333
vus_max.................: 10000  min=10000     max=10000
ws_connecting...........: avg=7.58ms   min=1.72ms     med=3.93ms max=475.49ms p(90)=13.8ms p(95)=21.48ms
ws_msgs_received........: 570400 8144.143055/s
ws_msgs_sent............: 300606 4292.037635/s
ws_sessions.............: 2333   33.310459/s
```

### Run 2

- joining clients: 33.3/s
- mean time to chat message: 15s
- silent users: 99%

```
chat_message_time.......: avg=3.5s    min=-5000000ns med=820ms  max=46.8s    p(90)=11.17s  p(95)=14.76s
checks..................: 73.62% ✓ 8359        ✗ 2995   
✗ { ping:no-timeout }...: 89.80% ✓ 5745        ✗ 652    
concurrent_clients......: 2065   33.282602/s
data_received...........: 428 MB 6.9 MB/s
data_sent...............: 20 MB  319 kB/s
ping_time...............: avg=3.49s   min=0s         med=1.23s  max=30.67s   p(90)=10s     p(95)=11.44s
request_response_time...: avg=845.5ms min=2ms        med=230ms  max=40.67s   p(90)=1.91s   p(95)=3.36s  
vus.....................: 2066   min=33        max=2066
vus_max.................: 10000  min=10000     max=10000
ws_connecting...........: avg=7.21ms  min=1.79ms     med=3.91ms max=776.16ms p(90)=12.45ms p(95)=17.12ms
ws_msgs_received........: 490509 7905.770416/s
ws_msgs_sent............: 260448 4197.766185/s
ws_sessions.............: 2065   33.282602/s
```

### Run 3

- joining clients: 16.6/s
- mean time to chat message: 15s
- silent users: 99%


```
chat_message_time.......: avg=11.1s   min=-1000000ns med=2.06s  max=2m56s p(90)=34.43s  p(95)=57.95s
checks..................: 64.75%  ✓ 32862       ✗ 17888
✗ { ping:no-timeout }...: 89.94%  ✓ 24515       ✗ 2742  
concurrent_clients......: 3999    16.659082/s
data_received...........: 2.0 GB  8.5 MB/s
data_sent...............: 86 MB   359 kB/s
ping_time...............: avg=4.76s   min=0s         med=2.57s  max=2m2s  p(90)=10s     p(95)=11.95s
request_response_time...: avg=2.68s   min=2ms        med=697ms  max=2m12s p(90)=7s      p(95)=11.67s
vus.....................: 3999    min=16        max=3999
vus_max.................: 5000    min=5000      max=5000
ws_connecting...........: avg=12.15ms min=1.8ms      med=4.38ms max=1.48s p(90)=19.09ms p(95)=33.41ms
ws_msgs_received........: 2240602 9333.926402/s
ws_msgs_sent............: 1163549 4847.126232/s
ws_sessions.............: 3999    16.659082/s
```

## 2021-08-25 docker compose gunicorn on single CPX51

Changes:
- added more realistic stage join behaviour (fetches chat logs and user profiles)
- lowered ping timeout threshold to 0.9

### Run 1

- joining clients: 33.3/s
- mean time to chat message: 15s

```
     chat_message_time.......: avg=2.6s     min=-6000000ns med=967ms  max=37.68s   p(90)=6.48s   p(95)=11.94s
     checks..................: 76.79% ✓ 6756        ✗ 2041   
     ✗ { ping:no-timeout }...: 89.95% ✓ 4506        ✗ 503    
     concurrent_clients......: 1799   33.260349/s
     data_received...........: 282 MB 5.2 MB/s
     data_sent...............: 13 MB  238 kB/s
     ping_time...............: avg=3.08s    min=0s         med=868ms  max=26.85s   p(90)=10s     p(95)=10.18s
     request_response_time...: avg=704.33ms min=2ms        med=206ms  max=36.85s   p(90)=1.27s   p(95)=2.97s  
     vus.....................: 1799   min=33        max=1799
     vus_max.................: 10000  min=10000     max=10000
     ws_connecting...........: avg=9.81ms   min=1.79ms     med=6.01ms max=318.09ms p(90)=15.13ms p(95)=20.07ms
     ws_msgs_received........: 324629 6001.819755/s
     ws_msgs_sent............: 173393 3205.731875/s
     ws_sessions.............: 1799   33.260349/s
```

### Run 2

- joining clients: 16.6/s
- mean time to chat message: 15s

```
     chat_message_time.......: avg=12.35s  min=-17000000ns med=2.98s  max=2m58s p(90)=38s     p(95)=55.64s
     checks..................: 63.27%  ✓ 33054       ✗ 19188
     ✗ { ping:no-timeout }...: 89.98%  ✓ 25283       ✗ 2813  
     concurrent_clients......: 4099    16.659273/s
     data_received...........: 1.9 GB  7.6 MB/s
     data_sent...............: 74 MB   299 kB/s
     ping_time...............: avg=5.07s   min=0s          med=2.9s   max=2m6s  p(90)=10s     p(95)=12.2s  
     request_response_time...: avg=3.02s   min=2ms         med=864ms  max=2m16s p(90)=7.54s   p(95)=12.62s
     vus.....................: 4099    min=16        max=4099
     vus_max.................: 5000    min=5000      max=5000
     ws_connecting...........: avg=15.93ms min=1.83ms      med=6.03ms max=2.62s p(90)=21.36ms p(95)=31.91ms
     ws_msgs_received........: 1922707 7814.320581/s
     ws_msgs_sent............: 1004104 4080.908091/s
     ws_sessions.............: 4099    16.659273/s
```

## 2021-08-24 docker compose gunicorn on single CPX51

### Run 1

- joining clients: 33.3/s
- mean time to chat message: 500ms

```
     chat_message_time.......: avg=1.37s    min=-1000000ns med=385ms  max=18.69s   p(90)=3.99s   p(95)=6.24s
     checks..................: 96.34%  ✓ 22458        ✗ 853    
     ✓ { ping:no-timeout }...: 98.14%  ✓ 11756        ✗ 222    
     concurrent_clients......: 2732    33.276468/s
   ✗ connection_errors.......: 2       0.024361/s
     data_received...........: 1.5 GB  18 MB/s
     data_sent...............: 36 MB   433 kB/s
     iteration_duration......: avg=40.08s   min=40s        med=40.08s max=40.16s   p(90)=40.14s  p(95)=40.15s
     iterations..............: 2       0.024361/s
     ping_time...............: avg=504.22ms min=0s         med=52ms   max=25.51s   p(90)=549.8ms p(95)=2.22s
     request_response_time...: avg=2.34s    min=9ms        med=715ms  max=35.5s    p(90)=6.5s    p(95)=10.46s
     vus.....................: 2733    min=33         max=2733
     vus_max.................: 10000   min=10000      max=10000
     ws_connecting...........: avg=22.43ms  min=1.77ms     med=7.51ms max=813.25ms p(90)=61.65ms p(95)=89ms  
     ws_msgs_received........: 2202449 26826.399368/s
     ws_msgs_sent............: 237069  2887.561833/s
     ws_session_duration.....: avg=40.08s   min=40s        med=40.08s max=40.16s   p(90)=40.14s  p(95)=40.15s
     ws_sessions.............: 2734    33.300828/s
```

### Run 2
- joining clients: 33.3/s
- mean time to chat message: 15s

```
     chat_message_time.......: avg=5.4s    min=-4000000ns med=1.54s   max=58.04s p(90)=16.6s    p(95)=23.22s  
     checks..................: 93.32%  ✓ 85734        ✗ 6131   
     ✗ { ping:no-timeout }...: 94.98%  ✓ 45523        ✗ 2403   
     concurrent_clients......: 6461    33.260619/s
     data_received...........: 4.5 GB  23 MB/s
     data_sent...............: 11 MB   56 kB/s
     ping_time...............: avg=1.56s   min=0s         med=101ms   max=1m47s  p(90)=3.63s    p(95)=10s     
     request_response_time...: avg=9.82s   min=7ms        med=2.66s   max=1m58s  p(90)=29.79s   p(95)=45.33s  
     vus.....................: 6466    min=33         max=6466
     vus_max.................: 10000   min=10000      max=10000
     ws_connecting...........: avg=51.07ms min=1.62ms     med=22.41ms max=1.53s  p(90)=123.31ms p(95)=165.84ms
     ws_msgs_received........: 5714263 29416.486916/s
     ws_msgs_sent............: 109861  565.554065/s
     ws_sessions.............: 6461    33.260619/s
```
