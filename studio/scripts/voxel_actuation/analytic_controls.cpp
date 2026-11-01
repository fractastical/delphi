// analytic_controls.cpp -- positive controls and must-fail mutants for the Voxelyze
// soft-actuation comparison. Links Voxelyze @ 4287e365e11416dd108f2f361e9ec4c5a011a16c
// (LGPL-3.0-or-later per its source headers). Our code, distributed as source.
//
// mode=expansion : free thermal expansion against the upstream zero-stress law
//                  baseSize = size*(1+temp*alphaCTE)   [VX_Voxel.h:88]
//                  gate: |L_measured/L_expected - 1| <= tol
// mode=cantilever: end-loaded cantilever against Euler-Bernoulli delta = F L^3/(3 E I),
//                  I = s^4/12, L = (n-1)*s. Justified by reading the upstream link law
//                  [VX_MaterialLink.cpp:126-131]: _a1=EL (EA/L), _b1=EL (12EI/L^3),
//                  _b2=EL^2/2 (6EI/L^2), _b3=EL^3/6 (2EI/L) -- i.e. each link IS an
//                  Euler-Bernoulli element of length s with I=s^4/12, so a chain of n-1
//                  of them should reproduce the closed form EXACTLY, not approximately.
//                  BOTH gates must hold: deflection ratio AND a settling-residual bound.
//                  Without the settling bound a slow, still-ringing long beam reads as a
//                  model mismatch: measured here at n=12/simT=3s, ratio 0.057.
//
// --mutate=sign      expansion: compare against (1 - alpha*T)        -> gate MUST fail
// --mutate=none_law  expansion: compare against unexpanded length    -> gate MUST fail
// --mutate=stiffness cantilever: back-solve with 10x E               -> gate MUST fail

#include "Voxelyze.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <string>

int main(int argc,char**argv){
    std::string mode="expansion", mutate="none", out="ctrl";
    int n=12; double s=0.01; float E=1e5f, rho=1e3f, nu=0.0f, zetaInt=1.0f, zetaGlob=2.0f;
    float cte=0.01f, T=10.0f; double tol=0.02, tolSettle=1e-3, simT=3.0, dtScale=0.4;
    double F=3.472e-4;
    for(int i=1;i<argc;i++){ std::string a=argv[i]; size_t eq=a.find('='); if(eq==std::string::npos) return 2;
        std::string k=a.substr(2,eq-2), v=a.substr(eq+1);
        if(k=="mode")mode=v; else if(k=="mutate")mutate=v; else if(k=="out")out=v;
        else if(k=="n")n=atoi(v.c_str()); else if(k=="s")s=atof(v.c_str());
        else if(k=="E")E=atof(v.c_str()); else if(k=="nu")nu=atof(v.c_str());
        else if(k=="cte")cte=atof(v.c_str()); else if(k=="T")T=atof(v.c_str());
        else if(k=="F")F=atof(v.c_str()); else if(k=="tol")tol=atof(v.c_str()); else if(k=="tolSettle")tolSettle=atof(v.c_str());
        else if(k=="simT")simT=atof(v.c_str()); else if(k=="dtScale")dtScale=atof(v.c_str());
        else { fprintf(stderr,"unknown key %s\n",k.c_str()); return 2; } }

    CVoxelyze vx(s);
    CVX_Material* m = vx.addMaterial(E,rho);
    m->setPoissonsRatio(nu); m->setInternalDamping(zetaInt); m->setGlobalDamping(zetaGlob);
    CVX_Voxel* first=NULL; CVX_Voxel* last=NULL;
    for(int i=0;i<n;i++){ CVX_Voxel* v=vx.setVoxel(m,i,0,0); if(i==0)first=v; if(i==n-1)last=v; }
    first->external()->setFixedAll();
    vx.setGravity(0.0f); vx.enableFloor(false); vx.enableCollisions(false);
    if(mode=="expansion"){ m->setCte(cte); for(int i=0;i<vx.voxelCount();i++) vx.voxel(i)->setTemperature(T); }
    else if(mode=="cantilever"){ m->setCte(0.0f); last->external()->setForce(0,0,(float)-F); }
    else { fprintf(stderr,"unknown mode\n"); return 2; }

    float rec=vx.recommendedTimeStep(); double dt=dtScale*rec; long steps=(long)(simT/dt);
    double measured=0, atNinety=0; bool diverged=false;
    for(long k=0;k<steps;k++){
        if(mode=="expansion") for(int i=0;i<vx.voxelCount();i++) vx.voxel(i)->setTemperature(T);
        if(!vx.doTimeStep((float)dt)){ diverged=true; break; }
        if(k==(long)(steps*0.9)) atNinety = (mode=="expansion") ? (last->position().x-first->position().x)
                                                               : (first->position().z-last->position().z);
    }
    measured = (mode=="expansion") ? (last->position().x-first->position().x)
                                   : (first->position().z-last->position().z);
    double settleDrift = (measured!=0)? std::fabs(measured-atNinety)/std::fabs(measured) : 1.0;

    double L1=(n-1)*s, L2=n*s;
    double I=std::pow(s,4)/12.0, EI=(double)E*I;
    bool pass=false; double expected=0, ratio=0, Leff=0; const char* gate="";
    if(mode=="expansion"){
        double a=cte;
        if(mutate=="sign")      expected=L1*(1.0-a*T);
        else if(mutate=="none_law") expected=L1;
        else                    expected=L1*(1.0+a*T);
        ratio=measured/expected; pass = std::fabs(ratio-1.0)<=tol;
        gate="|L_meas/L_expected - 1| <= tol";
    } else {
        double Eu = (mutate=="stiffness") ? 10.0*(double)E : (double)E;
        Leff = std::pow(3.0*EI*measured/F, 1.0/3.0);
        expected = F*std::pow(L1,3)/(3.0*Eu*I); ratio=measured/expected;
        pass = std::fabs(ratio-1.0)<=tol;
        gate="|delta_meas/delta_EulerBernoulli - 1| <= tol  AND settle_drift <= tolSettle";
    }
    bool settled = (settleDrift <= tolSettle) && !diverged;
    pass = pass && settled;
    bool mustFail = (mutate!="none");
    bool controlVerdictOk = mustFail ? (!pass && settled) : pass;  // a mutant must fail ON THE LAW,
                                                                   // not by being unsettled or crashed

    std::string jp=out+".json"; FILE* f=fopen(jp.c_str(),"w");
    fprintf(f,"{\n  \"schema\":\"frontier.voxelyze-analytic-control/1\",\n");
    fprintf(f,"  \"engine\":{\"name\":\"Voxelyze\",\"commit\":\"4287e365e11416dd108f2f361e9ec4c5a011a16c\"},\n");
    fprintf(f,"  \"mode\":\"%s\",\"mutate\":\"%s\",\"must_fail\":%s,\n",mode.c_str(),mutate.c_str(),mustFail?"true":"false");
    fprintf(f,"  \"params\":{\"n_voxels\":%d,\"voxel_m\":%g,\"E_Pa\":%g,\"poisson\":%g,\"cte_per_C\":%g,"
              "\"temp_C\":%g,\"tip_force_N\":%g,\"tol\":%g,\"tol_settle\":%g,\"sim_time_s\":%g,\"dt_s\":%.9g,\"steps\":%ld},\n",
            n,s,(double)E,(double)nu,(double)cte,(double)T,F,tol,tolSettle,simT,dt,steps);
    fprintf(f,"  \"geometry\":{\"L_centre_to_centre_m\":%g,\"L_outer_m\":%g,\"I_m4\":%.6g,\"EI_N_m2\":%.6g},\n",L1,L2,I,EI);
    fprintf(f,"  \"measured\":{\"value_m\":%.9g,\"value_at_90pct_time_m\":%.9g,\"settle_drift_frac\":%.4g,\"diverged\":%s},\n",
            measured,atNinety,settleDrift,diverged?"true":"false");
    fprintf(f,"  \"analytic\":{\"expected_m\":%.9g,\"ratio_measured_over_expected\":%.6f,\"L_eff_backsolved_m\":%.9g},\n",
            expected,ratio,Leff);
    fprintf(f,"  \"gate\":{\"rule\":\"%s\",\"settled\":%s,\"passed\":%s,\"control_verdict_ok\":%s}\n",gate,
            settled?"true":"false", pass?"true":"false", controlVerdictOk?"true":"false");
    fprintf(f,"}\n"); fclose(f);
    printf("%-28s mode=%-10s mutate=%-9s meas=%-11.5g expect=%-11.5g ratio=%8.4f settled=%d pass=%d verdict_ok=%d drift=%.2g\n",
           out.c_str(),mode.c_str(),mutate.c_str(),measured,expected,ratio,settled?1:0,pass?1:0,controlVerdictOk?1:0,settleDrift);
    return controlVerdictOk ? 0 : 1;
}
