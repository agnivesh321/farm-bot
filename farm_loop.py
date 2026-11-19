import requests, hashlib, hmac, time, datetime, math, os, json

K=os.environ['BINANCE_API_KEY']
S=os.environ['BINANCE_API_SECRET']

def sign(p):
    q='&'.join(f'{k}={v}' for k,v in sorted(p.items()))
    return q+'&signature='+hmac.new(S.encode(),q.encode(),hashlib.sha256).hexdigest()

def price(sym):
    for _ in range(3):
        r=requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={sym}',timeout=8)
        d=r.json()
        if 'price' in d: return float(d['price'])
        time.sleep(1)
    return 0.0

def bal(amt):
    p={'timestamp':int(time.time()*1000),'recvWindow':5000}
    d=requests.get('https://api.binance.com/api/v3/account?'+sign(p),headers={'X-MBX-APIKEY':K},timeout=8).json()
    for a in d['balances']:
        if a['asset']==amt and float(a['free'])>1e-9: return float(a['free'])
    return 0.0

def order(sym,side,qty):
    p={'symbol':sym,'side':side,'type':'MARKET','quantity':str(qty),'newOrderRespType':'FULL','timestamp':int(time.time()*1000),'recvWindow':5000}
    return requests.post('https://api.binance.com/api/v3/order?'+sign(p),headers={'X-MBX-APIKEY':K},timeout=10).json()

def log(line):
    print(line,flush=True)

step={'DOGEUSDT':1.0,'SHIBUSDT':1.0}

# load state
try:
    with open('state.json') as f: state=json.load(f)
except:
    state={'hold':'DOGE','ref':{'DOGE':price('DOGEUSDT'),'SHIB':price('SHIBUSDT')}}

hold=state['hold']
ref=state['ref']
d_price=price('DOGEUSDT')
s_price=price('SHIBUSDT')
d_gain=(d_price/ref['DOGE']-1)*100
s_gain=(s_price/ref['SHIB']-1)*100
qty=bal(hold)

log(f"{datetime.datetime.utcnow().strftime('%H:%M:%S')} UTC | {hold} {qty:.4f} | DOGE {d_price} ({d_gain:+.3f}%) SHIB {s_price} ({s_gain:+.3f}%) | USDT banked {bal('USDT'):.4f}")

if hold=='DOGE' and s_gain>d_gain+0.05 and qty>=1:
    r=order('DOGEUSDT','SELL',math.floor(qty/step['DOGEUSDT']))
    if r.get('status')=='FILLED':
        got=float(r['cummulativeQuoteQty'])
        nq=math.floor(got/s_price/step['SHIBUSDT'])
        r2=order('SHIBUSDT','BUY',nq)
        if r2.get('status')=='FILLED':
            hold='SHIB'
            state={'hold':'SHIB','ref':{'DOGE':d_price,'SHIB':s_price}}
            log(f"{datetime.datetime.utcnow().strftime('%H:%M:%S')} UTC | FLIP -> SHIB {nq} | USDT banked {bal('USDT'):.4f}")
elif hold=='SHIB' and d_gain>s_gain+0.05 and qty>=1:
    r=order('SHIBUSDT','SELL',math.floor(qty/step['SHIBUSDT']))
    if r.get('status')=='FILLED':
        got=float(r['cummulativeQuoteQty'])
        nq=math.floor(got/d_price/step['DOGEUSDT'])
        r2=order('DOGEUSDT','BUY',nq)
        if r2.get('status')=='FILLED':
            hold='DOGE'
            state={'hold':'DOGE','ref':{'DOGE':d_price,'SHIB':s_price}}
            log(f"{datetime.datetime.utcnow().strftime('%H:%M:%S')} UTC | FLIP -> DOGE {nq} | USDT banked {bal('USDT'):.4f}")

# save state
with open('state.json','w') as f: json.dump(state,f)