// soft_actuation.cpp -- Xenobot-inspired soft-voxel actuation comparison.
//
// Links Voxelyze (jonhiller/Voxelyze @ 4287e365e11416dd108f2f361e9ec4c5a011a16c),
// whose source headers declare LGPL-3.0-or-later. This file is OUR code and is
// distributed as source with a build recipe; no linked binary is redistributed.
//
// Scope: GENERIC soft-body voxel mechanics. Nothing here is calibrated to Xenopus
// tissue, frog cells, cilia, or any measured organism. "Xenobot-inspired" names the
// design pattern (voxel body + volumetric actuation + ground friction), not biology.
//
// Governing relations actually used, read from upstream source at the pin:
//   zero-stress voxel size  : baseSize = size * (1 + temp * alphaCTE)     [VX_Voxel.h:88]
//   per-voxel temperature   : temp = T(t)                                 [VX_Voxel.cpp:108]
//   integration             : explicit Euler, diverges if axialStrain>100 [Voxelyze.cpp:251]
// Actuation we impose (OUR choice, not upstream):
//   T_i(t) = A * sin(2*pi*f*t + phi_i),  phi_i set by the named pattern.

#include "Voxelyze.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include <map>

static const double kPi = 3.14159265358979323846;

struct Cfg {
    int nx=5, ny=3, nz=3;
    double voxel=0.01;          // m          (voxcraft demos/basic/base.vxa Lattice_Dim)
    float E=1e5f;               // Pa         (base.vxa Elastic_Mod)
    float rho=1e3f;             // kg/m^3     (base.vxa Density)
    float nu=0.35f;             // -          (base.vxa Poissons_Ratio)
    float muS=1.0f;             // -          (base.vxa uStatic)
    float muK=0.8f;             // -          (base.vxa uDynamic)
    float zetaInt=1.0f;         // -          ASSUMED (Voxelyze doc "recommended value: 1.0")
    float zetaGlob=0.1f;        // -          ASSUMED
    float zetaColl=0.8f;        // -          ASSUMED
    float cte=0.01f;            // 1/degC     ASSUMED
    float ampC=10.0f;           // degC rel   ASSUMED -> 10% peak linear strain
    float freq=4.0f;            // Hz         ASSUMED
    double settle=0.25;         // s
    double measure=1.25;        // s  (= 5 cycles at 4 Hz)
    double dtScale=0.5;         // fraction of recommendedTimeStep
    int recordEvery=0;          // 0 => auto (~240 COM samples over the whole run)
    int dumpVoxels=0;           // 1 => also dump every voxel position at each record
    bool gravity=true, floorOn=true, collisions=true;
    std::string pattern="longitudinal";
    std::string out="run";
};

static double phaseFor(const std::string& p, int x, int y, int z, const Cfg& c) {
    if (p=="uniform")       return 0.0;
    if (p=="longitudinal")  return (x < c.nx/2) ? 0.0 : kPi;              // split along travel axis
    if (p=="lateral")       return (y < c.ny/2) ? 0.0 : kPi;
    if (p=="dorsoventral")  return (z < c.nz/2) ? 0.0 : kPi;
    if (p=="travelling")    return 2.0*kPi*(double)x/(double)c.nx;        // retrograde wave along x
    if (p=="checker")       return ((x+y+z)%2) ? kPi : 0.0;
    fprintf(stderr,"unknown pattern %s\n", p.c_str()); exit(2);
}

struct Com { double x,y,z; };
static Com comOf(CVoxelyze& v){  // equal nominal mass per voxel -> arithmetic mean of centres
    Com c={0,0,0}; int n=v.voxelCount();
    for(int i=0;i<n;i++){ Vec3D<double> p=v.voxel(i)->position(); c.x+=p.x; c.y+=p.y; c.z+=p.z; }
    if(n){ c.x/=n; c.y/=n; c.z/=n; } return c;
}

int main(int argc, char** argv){
    Cfg c;
    for(int i=1;i<argc;i++){
        std::string a=argv[i]; size_t eq=a.find('=');
        if(a.rfind("--",0)!=0 || eq==std::string::npos){ fprintf(stderr,"bad arg %s\n",a.c_str()); return 2; }
        std::string k=a.substr(2,eq-2), v=a.substr(eq+1);
        if(k=="nx")c.nx=atoi(v.c_str()); else if(k=="ny")c.ny=atoi(v.c_str()); else if(k=="nz")c.nz=atoi(v.c_str());
        else if(k=="voxel")c.voxel=atof(v.c_str()); else if(k=="E")c.E=atof(v.c_str());
        else if(k=="rho")c.rho=atof(v.c_str()); else if(k=="nu")c.nu=atof(v.c_str());
        else if(k=="muS")c.muS=atof(v.c_str()); else if(k=="muK")c.muK=atof(v.c_str());
        else if(k=="zetaInt")c.zetaInt=atof(v.c_str()); else if(k=="zetaGlob")c.zetaGlob=atof(v.c_str());
        else if(k=="zetaColl")c.zetaColl=atof(v.c_str()); else if(k=="cte")c.cte=atof(v.c_str());
        else if(k=="amp")c.ampC=atof(v.c_str()); else if(k=="freq")c.freq=atof(v.c_str());
        else if(k=="settle")c.settle=atof(v.c_str()); else if(k=="measure")c.measure=atof(v.c_str());
        else if(k=="dtScale")c.dtScale=atof(v.c_str()); else if(k=="recordEvery")c.recordEvery=atoi(v.c_str());
        else if(k=="dumpVoxels")c.dumpVoxels=atoi(v.c_str());
        else if(k=="gravity")c.gravity=atoi(v.c_str()); else if(k=="floor")c.floorOn=atoi(v.c_str());
        else if(k=="collisions")c.collisions=atoi(v.c_str());
        else if(k=="pattern")c.pattern=v; else if(k=="out")c.out=v;
        else { fprintf(stderr,"unknown key %s\n",k.c_str()); return 2; }
    }

    CVoxelyze vx(c.voxel);
    CVX_Material* mat = vx.addMaterial(c.E, c.rho);
    mat->setPoissonsRatio(c.nu);
    mat->setStaticFriction(c.muS); mat->setKineticFriction(c.muK);
    mat->setInternalDamping(c.zetaInt); mat->setGlobalDamping(c.zetaGlob); mat->setCollisionDamping(c.zetaColl);
    mat->setCte(c.cte);

    std::vector<CVX_Voxel*> vox; std::vector<double> phi;
    for(int x=0;x<c.nx;x++) for(int y=0;y<c.ny;y++) for(int z=0;z<c.nz;z++){
        vox.push_back(vx.setVoxel(mat,x,y,z));
        phi.push_back(phaseFor(c.pattern,x,y,z,c));
    }
    vx.setGravity(c.gravity?1.0f:0.0f);
    vx.enableFloor(c.floorOn);
    vx.enableCollisions(c.collisions);

    float rec = vx.recommendedTimeStep();
    double dt = c.dtScale*rec;
    long nSettle=(long)(c.settle/dt), nMeas=(long)(c.measure/dt), nTot=nSettle+nMeas;
    int every = c.recordEvery>0 ? c.recordEvery : (int)std::max(1L, nTot/240);

    std::string comPath=c.out+"-com.csv";
    FILE* fcom=fopen(comPath.c_str(),"w");
    fprintf(fcom,"phase,step,t_s,com_x_m,com_y_m,com_z_m,T_drive_C\n");
    FILE* fvox=NULL;
    if(c.dumpVoxels){ std::string vp=c.out+"-voxels.csv"; fvox=fopen(vp.c_str(),"w");
        fprintf(fvox,"step,t_s,vox,ix,iy,iz,x_m,y_m,z_m,temp_C\n"); }

    bool diverged=false; long divergedAt=-1; double t=0.0;
    Com cStart={0,0,0}, cEnd={0,0,0};
    double pathLen=0.0; Com prev=comOf(vx);
    double zMinSeen=1e9, extXmin=1e9, extXmax=-1e9;

    for(long s=0;s<nTot;s++){
        bool measuring = (s>=nSettle);
        double tm = measuring ? (t - c.settle) : 0.0;
        double Tdrive = measuring ? c.ampC : 0.0;
        for(size_t i=0;i<vox.size();i++){
            float T = measuring ? (float)(c.ampC*std::sin(2.0*kPi*c.freq*tm + phi[i])) : 0.0f;
            vox[i]->setTemperature(T);
        }
        if(s==nSettle) cStart=comOf(vx);
        if(!vx.doTimeStep((float)dt)){ diverged=true; divergedAt=s; break; }
        t+=dt;
        if(s%every==0){
            Com cm=comOf(vx);
            pathLen += std::sqrt((cm.x-prev.x)*(cm.x-prev.x)+(cm.y-prev.y)*(cm.y-prev.y)); prev=cm;
            fprintf(fcom,"%s,%ld,%.6f,%.9f,%.9f,%.9f,%.4f\n", measuring?"measure":"settle", s,t,cm.x,cm.y,cm.z,
                    measuring? c.ampC*std::sin(2.0*kPi*c.freq*tm) : 0.0);
            if(cm.z<zMinSeen) zMinSeen=cm.z;
            if(fvox) for(size_t i=0;i<vox.size();i++){ Vec3D<double> p=vox[i]->position();
                int ix=(int)(i/(c.ny*c.nz)), iy=(int)((i/c.nz)%c.ny), iz=(int)(i%c.nz);
                fprintf(fvox,"%ld,%.6f,%zu,%d,%d,%d,%.9f,%.9f,%.9f,%.4f\n",s,t,i,ix,iy,iz,p.x,p.y,p.z,vox[i]->temperature()); }
        }
        for(size_t i=0;i<vox.size();i++){ double px=vox[i]->position().x;
            if(px<extXmin)extXmin=px; if(px>extXmax)extXmax=px; }
        (void)Tdrive;
    }
    cEnd=comOf(vx);
    fclose(fcom); if(fvox) fclose(fvox);

    double dx=cEnd.x-cStart.x, dy=cEnd.y-cStart.y;
    double disp=std::sqrt(dx*dx+dy*dy);
    double cycles=c.measure*c.freq;
    double bodyLen=(c.nx-1)*c.voxel;

    std::string jp=c.out+".json"; FILE* fj=fopen(jp.c_str(),"w");
    fprintf(fj,"{\n");
    fprintf(fj,"  \"schema\": \"frontier.voxelyze-soft-actuation/1\",\n");
    fprintf(fj,"  \"engine\": {\"name\":\"Voxelyze\",\"repo\":\"https://github.com/jonhiller/Voxelyze\",\"commit\":\"4287e365e11416dd108f2f361e9ec4c5a011a16c\",\"lib_version_string\":\"voxelyze.0.9.92\",\"license_from_source_headers\":\"LGPL-3.0-or-later\"},\n");
    fprintf(fj,"  \"pattern\": \"%s\",\n", c.pattern.c_str());
    fprintf(fj,"  \"params\": {\"nx\":%d,\"ny\":%d,\"nz\":%d,\"voxel_m\":%g,\"E_Pa\":%g,\"rho_kg_m3\":%g,\"poisson\":%g,"
               "\"mu_static\":%g,\"mu_kinetic\":%g,\"zeta_internal\":%g,\"zeta_global\":%g,\"zeta_collision\":%g,"
               "\"cte_per_C\":%g,\"temp_amplitude_C\":%g,\"freq_Hz\":%g,\"settle_s\":%g,\"measure_s\":%g,"
               "\"gravity_g\":%d,\"floor\":%d,\"collisions\":%d},\n",
            c.nx,c.ny,c.nz,c.voxel,(double)c.E,(double)c.rho,(double)c.nu,(double)c.muS,(double)c.muK,
            (double)c.zetaInt,(double)c.zetaGlob,(double)c.zetaColl,(double)c.cte,(double)c.ampC,(double)c.freq,
            c.settle,c.measure,c.gravity?1:0,c.floorOn?1:0,c.collisions?1:0);
    fprintf(fj,"  \"numerics\": {\"recommended_dt_s\":%.9g,\"dt_scale\":%g,\"dt_s\":%.9g,\"steps_settle\":%ld,"
               "\"steps_measure\":%ld,\"record_every\":%d,\"diverged\":%s,\"diverged_at_step\":%ld,\"sim_time_s\":%.6f},\n",
            (double)rec,c.dtScale,dt,nSettle,nMeas,every,diverged?"true":"false",divergedAt,t);
    fprintf(fj,"  \"result\": {\"com_start_m\":[%.9f,%.9f,%.9f],\"com_end_m\":[%.9f,%.9f,%.9f],"
               "\"net_dx_m\":%.9f,\"net_dy_m\":%.9f,\"net_disp_m\":%.9f,\"path_len_m\":%.9f,"
               "\"cycles\":%g,\"disp_per_cycle_m\":%.9f,\"disp_in_body_lengths\":%.6f,\"body_len_m\":%g},\n",
            cStart.x,cStart.y,cStart.z,cEnd.x,cEnd.y,cEnd.z,dx,dy,disp,pathLen,cycles,
            cycles>0?disp/cycles:0.0, bodyLen>0?disp/bodyLen:0.0, bodyLen);
    fprintf(fj,"  \"files\": {\"com_csv\":\"%s\"%s},\n", comPath.c_str(),
            c.dumpVoxels? (", \"voxel_csv\":\"" + c.out + "-voxels.csv\"").c_str() : "");
    fprintf(fj,"  \"scope\": \"generic soft-voxel mechanics; no organism calibration; parameters marked ASSUMED in source are not measured\"\n");
    fprintf(fj,"}\n");
    fclose(fj);

    printf("%s pattern=%s dt=%.3e disp=%.6g m (%.4g body-lengths) diverged=%d\n",
           c.out.c_str(), c.pattern.c_str(), dt, disp, bodyLen>0?disp/bodyLen:0.0, diverged?1:0);
    return diverged ? 3 : 0;
}
