import json,re,sys
from playwright.sync_api import sync_playwright
BASE="https://frontier.morphoswarm.ai/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r5"
CONTRAST=open('/tmp/claude-1000/-data-worktrees-delphi-evolve-rethink-critic/45bfe973-0b4e-4c5b-9d70-43d8c4aa8801/scratchpad/audit.py').read().split('CONTRAST="""')[1].split('"""')[0]
res={}
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox"])
    for vp,(w,h) in {"desktop":(1440,1000),"mobile":(390,844)}.items():
        ctx=b.new_context(viewport={"width":w,"height":h},has_touch=(vp=="mobile")); pg=ctx.new_page(); out={}
        tap=lambda l,**k: (l.tap(**k) if vp=="mobile" else l.click(**k))
        pg.goto(BASE+"#/generative",wait_until="load"); pg.wait_for_timeout(3000)
        n=pg.locator("[data-gen-stage]").count(); stg=[]
        for i in range(n):
            tap(pg.locator("[data-gen-stage]").nth(i)); pg.wait_for_timeout(500)
            r=pg.evaluate("""()=>{const eq=document.querySelector('.about-equation');const k=eq?eq.querySelector('.katex'):null;const d=eq?eq.querySelector('.katex-display')||eq:null;
              return {pressed:[...document.querySelectorAll('[data-gen-stage]')].map(b=>b.getAttribute('aria-pressed')).join(','),katex:!!k,err:eq?eq.querySelectorAll('.katex-error').length:null,eqW:d?d.scrollWidth:null,boxW:d?d.clientWidth:null,clipped:d?d.scrollWidth>d.clientWidth+2:null,status:(document.querySelector('.about-detail,.gen-detail')||{innerText:''}).innerText.slice(0,30),eqText:eq?eq.innerText.replace(/\\s+/g,' ').slice(0,90):null,h3:(document.querySelector('.about-equation')?.parentElement?.querySelector('h3')||{}).innerText}}""")
            stg.append(r)
            if i in (0,3,5): pg.screenshot(path=f"{OUT}/R5b_{vp}_generative_stage{i}.png")
        out["generative_stages"]=stg
        # keyboard on stepper
        pg.locator("[data-gen-stage]").first.focus(); pg.keyboard.press("ArrowRight"); out["gen_arrow_key_focus"]=pg.evaluate("()=>(document.activeElement.innerText||'').slice(0,20)"); pg.keyboard.press("Enter"); pg.wait_for_timeout(300); out["gen_enter_pressed"]=pg.evaluate("()=>[...document.querySelectorAll('[data-gen-stage]')].map(b=>b.getAttribute('aria-pressed')).join(',')")
        for tb in ["built","connect"]:
            pg.goto(BASE+f"#/work?tab={tb}",wait_until="load"); pg.wait_for_timeout(3500)
            t=re.sub(r'\s+',' ',pg.evaluate("()=>document.getElementById('main').innerText"))
            st=pg.evaluate("""()=>({h:document.documentElement.scrollHeight,ox:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,h2:[...document.querySelectorAll('main h2,main h3')].map(h=>h.innerText.slice(0,44)).slice(0,14),tables:document.querySelectorAll('main table').length,details:document.querySelectorAll('main details').length,detailsOpen:document.querySelectorAll('main details[open]').length,pre:[...document.querySelectorAll('main pre')].map(p=>p.innerText.length),
              tableOverflow:[...document.querySelectorAll('main .tablewrap')].filter(w=>w.scrollWidth>w.clientWidth+2).length,ext:[...document.querySelectorAll('main a[href^=http]')].map(a=>[a.href.slice(0,60),a.rel]).slice(0,6),extNoRel:[...document.querySelectorAll('main a[target=_blank]')].filter(a=>!/noopener/.test(a.rel)).length})""")
            out[tb]=st|{"len":len(t),"bad":sorted(set(m.group(0) for m in re.finditer(r"\[object |undefined|\bNaN\b|\{\{|\}\}",t))),"score_words":re.findall(r'(?i).{0,40}\b(?:score|rank(?:ed|ing)?|winner|best|first-ever|solved|proven)\b.{0,40}',t)[:4],"contrast_n":len(pg.evaluate(CONTRAST)),"head":t[:160]}
            pg.screenshot(path=f"{OUT}/R5b_{vp}_work_{tb}.png",full_page=(vp=="mobile" and False))
        res[vp]=out; ctx.close()
    b.close()
json.dump(res,open(f"{OUT}/audit5b.json","w"),indent=1); print(json.dumps(res,indent=1)[:5200])
