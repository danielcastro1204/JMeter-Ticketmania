import argparse, json, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
P={"general":80000,"occidental":120000,"preferencial":180000,"vip":350000}
R={}
class H(BaseHTTPRequestHandler):
    server_version="TicketManiaSimple"
    def log_message(self,*a): pass
    def send(self,c,o):
        b=json.dumps(o).encode(); self.send_response(c)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path=="/api/salud": self.send(200,{"estado":"OK"})
        elif self.path=="/api/tarifas": self.send(200,{"tarifas":P})
        else: self.send(404,{"error":"no existe"})
    def do_POST(self):
        d=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or b"{}")
        if self.path=="/api/seleccion":
            t,c=d.get("tarifa"),d.get("cantidad")
            if t not in P or not isinstance(c,int) or c<1: return self.send(400,{"error":"datos inválidos"})
            r=uuid.uuid4().hex; R[r]=P[t]*c; self.send(200,{"reserva":r,"total":R[r]})
        elif self.path=="/api/pago":
            r=d.get("reserva")
            if r in R: R.pop(r); self.send(200,{"estado":"APROBADO"})
            else: self.send(404,{"error":"reserva no encontrada"})
        else: self.send(404,{"error":"no existe"})
if __name__=="__main__":
    a=argparse.ArgumentParser(); a.add_argument("--puerto",type=int,default=8080); a=a.parse_args()
    print(f"TicketManiaSimple escuchando en http://127.0.0.1:{a.puerto}", flush=True)
    ThreadingHTTPServer(("127.0.0.1",a.puerto),H).serve_forever()
