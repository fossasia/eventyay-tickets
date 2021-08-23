# Load test results

## 2021-08-24 docker compose gunicorn on single CPX51

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

Run 2:
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
