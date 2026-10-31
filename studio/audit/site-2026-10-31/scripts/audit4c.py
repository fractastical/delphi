import json,re,sys
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:18990/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r4"
res={}
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--use-gl=swiftshader","--enable-unsafe-swiftshader"])
    for vp,(w,h) in {"desktop":(1440,1000),"mobile":(390,844)}.items():
        ctx=b.new_context(viewport={"width":w,"height":h},has_touch=(vp=="mobile")); pg=ctx.new_page(); cons=[]
        pg.on("console",lambda m,c=cons: c.append((m.type,m.text[:160])) if m.type in("error","warning") else None); pg.on("pageerror",lambda e,c=cons: c.append(("pageerror",str(e)[:160])))
        pg.goto(BASE+"#/home",wait_until="load"); pg.wait_for_timeout(7000)
        v=pg.evaluate("""()=>{const r=document.querySelector('#fish-viewer');if(!r)return {present:false,route:location.hash};const c=r.querySelector('canvas');return {present:true,text:r.innerText.replace(/\\s+/g,' ').slice(0,500),canvas:!!c,box:c?[Math.round(c.getBoundingClientRect().width),Math.round(c.getBoundingClientRect().height)]:null,tab:c?c.tabIndex:null,label:c?(c.getAttribute('aria-label')||c.getAttribute('role')):null,buttons:[...r.querySelectorAll('button')].map(b=>b.innerText.slice(0,26)).slice(0,12),tables:r.querySelectorAll('table').length}}""")
        pg.screenshot(path=f"{OUT}/R4c_{vp}_home_glb.png",full_page=False)
        out={"viewer":v,"console":cons[:4]}
        if v.get("canvas"):
            try:
                c=pg.locator("#fish-viewer canvas").first; c.scroll_into_view_if_needed(); bx=c.bounding_box()
                (pg.mouse.click(bx["x"]+bx["width"]/2,bx["y"]+bx["height"]/2) if vp=="desktop" else c.tap(position={"x":bx["width"]/2,"y":bx["height"]/2})); pg.wait_for_timeout(1500)
                t=pg.evaluate("()=>document.querySelector('#fish-viewer').innerText.replace(/\\s+/g,' ')")
                out["after_click"]=t[:500]; pg.screenshot(path=f"{OUT}/R4c_{vp}_glb_click.png",full_page=False)
                pg.keyboard.press("Tab"); out["focus_after_tab"]=pg.evaluate("()=>(document.activeElement.getAttribute('aria-label')||document.activeElement.innerText||document.activeElement.tagName).slice(0,60)")
                btns=pg.locator("#fish-viewer button"); out["n_buttons"]=btns.count()
            except Exception as e: out["interaction_error"]=str(e)[:150]
        res[vp]=out; ctx.close()
    b.close()
json.dump(res,open(f"{OUT}/audit4c.json","w"),indent=1); print(json.dumps(res,indent=1)[:2600])
