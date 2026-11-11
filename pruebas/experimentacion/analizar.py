import csv, glob, os, statistics
rows=[]
for esc in csv.DictReader(open("scenarios.csv")):
    f=f"resultados/{esc['id']}.jtl"
    if not os.path.exists(f): continue
    r=list(csv.DictReader(open(f)))
    t=sorted(int(x["elapsed"]) for x in r)
    ts=[int(x["timeStamp"]) for x in r]; dur=(max(ts)-min(ts))/1000 or 1
    err=sum(x["success"]!="true" for x in r)
    rows.append([esc["id"],esc["descripcion"],len(r),round(len(r)/dur,2),round(statistics.mean(t),1),t[int(len(t)*.95)-1],max(t),round(100*err/len(r),2)])
with open("resultados/resumen.csv","w",newline="") as o:
    w=csv.writer(o); w.writerow(["id","descripcion","muestras","throughput_req_s","media_ms","p95_ms","max_ms","error_pct"]); w.writerows(rows)
print("id | muestras | req/s | media | p95 | max | %err")
for x in rows: print(x[0],x[1],*x[2:],sep=" | ")
