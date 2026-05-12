const MSC  = {atk:'#ff4444', stm:'#00e676', fcs:'#ffd600', agi:'#00e5ff', sup:'#a855f7'};
const MSD  = {atk:'#881111', stm:'#006633', fcs:'#886600', agi:'#006688', sup:'#551188'};
const MSL  = {atk:'#ff9999', stm:'#88ffcc', fcs:'#ffee88', agi:'#88eeff', sup:'#cc88ff'};

const mDom = s => Object.entries(s).sort((a,b)=>b[1]-a[1])[0][0];
const mSec = s => Object.entries(s).sort((a,b)=>b[1]-a[1])[1][0];
const mTot = s => Object.values(s).reduce((a,b)=>a+b,0);

const _NA=['BLA','VER','LUM','ZEP','AET','KRO','PHO','TOR','MYS','NUL',
           'GLA','OBL','PYR','SOL','NEB','VEX','THA','KYR','ORM','SYX',
           'DRA','CYN','FEL','WOL','SER','AXE','BOR','CAL','DEM','ELD'];
const _NB=['ZOR','DAX','NOS','IXX','MUS','KAR','PHX','RAX','THO','GON',
           'WYN','RUL','VUN','DOX','AXS','ERN','OVA','KUS','TYR','NAX',
           'BRX','CLV','DRN','EVX','FLZ','GRV','HXN','JRK','KLM','LRX'];

function mName(s){
  const d=mDom(s),sc=mSec(s);
  return _NA[Math.floor(s[d]/3.4)%_NA.length]
       + _NB[Math.floor((s[d]+s[sc])/6.8)%_NB.length];
}

const _SPEC=[
  {l:'GODMODE',   c:'#ffffff', f:s=>mTot(s)>=460},
  {l:'LEGENDARY', c:'#ffd700', f:s=>mTot(s)>=400},
  {l:'MYTHIC',    c:'#ff55ff', f:s=>mTot(s)>=350},
  {l:'ALLROUNDER',c:'#aaffee', f:s=>Object.values(s).every(v=>v>35&&v<75)&&mTot(s)>220},
  {l:'HARMONIC',  c:'#ffffff', f:s=>{const v=Object.values(s);return Math.max(...v)-Math.min(...v)<=12&&mTot(s)>=180}},
  {l:'BERSERKER KING',c:'#ff4444',f:s=>s.atk>=95},
  {l:'FORTRESS',  c:'#00e676', f:s=>s.stm>=95},
  {l:'ALL-SEEING',c:'#ffd600', f:s=>s.fcs>=95},
  {l:'LIGHTNING', c:'#00e5ff', f:s=>s.agi>=95},
  {l:'DIVINE',    c:'#a855f7', f:s=>s.sup>=95},
  {l:'IRON GOD',  c:'#ffaa00', f:s=>s.atk>80&&s.stm>80},
  {l:'VOID WALKER',c:'#4400ff',f:s=>s.fcs>80&&s.agi>80},
  {l:'FLEDGLING', c:'#888888', f:s=>mTot(s)<80},
];
const _BASE={
  atk:{stm:'BERSERKER',fcs:'ASSASSIN',agi:'STRIKER',sup:'WARLORD',atk:'DESTROYER'},
  stm:{atk:'TANK',fcs:'SENTINEL',agi:'IRONFOOT',sup:'GUARDIAN',stm:'COLOSSUS'},
  fcs:{atk:'SNIPER',stm:'SCHOLAR',agi:'PHANTOM',sup:'ORACLE',fcs:'ENLIGHTENED'},
  agi:{atk:'DUELIST',stm:'RUNNER',fcs:'TRICKSTER',sup:'HERALD',agi:'BLUR'},
  sup:{atk:'PALADIN',stm:'MENDER',fcs:'PROPHET',agi:'BARD',sup:'ASCENDANT'},
};

function mArchetype(s){
  for(const sp of _SPEC)if(sp.f(s))return{l:sp.l,c:sp.c};
  const d=mDom(s),sc=mSec(s);
  return{l:_BASE[d]?.[sc]||'WANDERER',c:MSC[d]};
}

function mTraits(s){
  const t=[];
  if(s.atk>85)t.push({t:'RAGING',c:'#ff3333'});else if(s.atk>65)t.push({t:'FIERCE',c:'#ff7777'});else if(s.atk>40)t.push({t:'BOLD',c:'#ff9999'});
  if(s.stm>85)t.push({t:'IMMORTAL',c:'#00e676'});else if(s.stm>65)t.push({t:'STURDY',c:'#44dd88'});else if(s.stm>40)t.push({t:'TOUGH',c:'#88ddaa'});
  if(s.fcs>85)t.push({t:'ALLSEEING',c:'#ffd600'});else if(s.fcs>65)t.push({t:'SHARP',c:'#ddcc00'});else if(s.fcs>40)t.push({t:'AWARE',c:'#bbaa00'});
  if(s.agi>85)t.push({t:'HYPERSPEED',c:'#00e5ff'});else if(s.agi>65)t.push({t:'NIMBLE',c:'#44ddff'});else if(s.agi>40)t.push({t:'QUICK',c:'#88eeff'});
  if(s.sup>85)t.push({t:'DIVINE',c:'#a855f7'});else if(s.sup>65)t.push({t:'BLESSED',c:'#cc88ff'});else if(s.sup>40)t.push({t:'AURA',c:'#bb99ff'});
  if(mTot(s)>420)t.push({t:'LEGENDARY',c:'#ffd700'});
  if(Object.values(s).some(v=>v<5))t.push({t:'CURSED',c:'#445566'});
  if(Object.values(s).every(v=>v>60))t.push({t:'BALANCED',c:'#aaffee'});
  return t.slice(0,5);
}

const BODIES = {
  dragon(cx,cy,r,mc,dc,lc,s){
    const bw=r*1.1,bh=r*0.7; let o='';
    o+=`<polygon points="${cx},${cy-bh*.3} ${cx+bw*1.2},${cy+bh*.4} ${cx+bw},${cy+bh*1.3} ${cx-bw},${cy+bh*1.3} ${cx-bw*1.2},${cy+bh*.4}" fill="${dc}"/`>`;
    o+=`<polygon points="${cx},${cy-bh*.2} ${cx+bw},${cy+bh*.45} ${cx+bw*.8},${cy+bh*1.2} ${cx-bw*.8},${cy+bh*1.2} ${cx-bw},${cy+bh*.45}" fill="${mc}"/`>`;
    const ns=2+Math.floor(s.atk/25);
    for(let i=0;i<ns;i++){const sx=cx-bw*.55+i*(bw*1.1/ns),sh=r*(.1+s.atk/100*.22);
      o+=`<polygon points="${sx-r*.05},${cy-bh*.65} ${sx+r*.05},${cy-bh*.65} ${sx},${cy-bh*.65-sh}" fill="${lc}" opacity=".75"/>`;
    }
    o+=`<path d="M${cx+bw*.9},${cy+bh*.2} Q${cx+bw*1.5},${cy+bh} ${cx+bw*1.1},${cy+bh*1.3}" fill="none" stroke="${dc}" stroke-width="${r*.14}" stroke-linecap="round"/>`;
    o+=`<polygon points="${cx+bw*1.03},${cy+bh*1.22} ${cx+bw*1.17},${cy+bh*1.22} ${cx+bw*1.1},${cy+bh*1.52}" fill="${lc}"/`>`;
    o+=`<ellipse cx="${cx}" cy="${cy+bh*.7}" rx="${bw*.55}" ry="${bh*.45}" fill="${dc}" opacity=".3"/>`;
    return o;
  },

  slime(cx,cy,r,mc,dc,lc,s){
    let o='';
    o+=`<ellipse cx="${cx}" cy="${cy+r*.15}" rx="${r*1.08}" ry="${r*.92}" fill="${dc}"/>`;
    o+=`<ellipse cx="${cx}" cy="${cy}" rx="${r}" ry="${r*.85}" fill="${mc}"/>`;
    const nb=2+Math.floor(s.stm/20);
    const bp=[[-.42,.1,.22],[.3,.15,.18],[-.15,-.24,.15],[.5,-.1,.13],[0,.3,.1],[-.3,-.1,.12]];
    bp.slice(0,nb).forEach(([bx,by2,br])=>o+=`<circle cx="${cx+bx*r}" cy="${cy+by2*r}" r="${br*r}" fill="${lc}" opacity=".32"/>`);
    o+=`<ellipse cx="${cx-r*.22}" cy="${cy+r*.9}" rx="${r*.12}" ry="${r*.19}" fill="${mc}"/`>`;
    o+=`<ellipse cx="${cx+r*.35}" cy="${cy+r*.88}" rx="${r*.09}" ry="${r*.14}" fill="${mc}"/>`;
    if(s.stm>70)o+=`<ellipse cx="${cx+r*.1}" cy="${cy+r*.92}" rx="${r*.07}" ry="${r*.11}" fill="${mc}"/>`;
    return o;
  },

  mech(cx,cy,r,mc,dc,lc,s){
    const bw=r*1.05,bh=r*.72; let o='';
    o+=`<rect x="${cx-bw*1.06}" y="${cy-bh*.56}" width="${bw*2.12}" height="${bh*1.12}" rx="${r*.06}" fill="${dc}"/>`;
    o+=`<rect x="${cx-bw}" y="${cy-bh*.5}" width="${bw*2}" height="${bh}" rx="${r*.05}" fill="${mc}"/>`;
    o+=`<line x1="${cx}" y1="${cy-bh*.5}" x2="${cx}" y2="${cy+bh*.5}" stroke="${dc}" stroke-width="${r*.04}"/>`;
    o+=`<line x1="${cx-bw}" y1="${cy}" x2="${cx+bw}" y2="${cy}" stroke="${dc}" stroke-width="${r*.04}"/>`;
    const nv=2+Math.floor(s.fcs/35);
    for(let i=0;i<nv;i++)o+=`<rect x="${cx-bw*.82+(i*bw*1.5/nv)}" y="${cy+bh*.12}" width="${bw*1.2/nv}" height="${bh*.13}" rx="2" fill="${dc}"/>`;
    o+=`<circle cx="${cx}" cy="${cy-bh*.15}" r="${r*.18}" fill="${lc}" opacity="${.4+s.fcs/100*.4}"/`>`;
    o+=`<circle cx="${cx}" cy="${cy-bh*.15}" r="${r*.1}" fill="#fff" opacity="${.2+s.fcs/100*.4}"/`>`;
    for(const sd of[-1,1]){
      const ax=cx+sd*(bw+r*.05);
      o+=`<rect x="${ax-r*.13}" y="${cy-bh*.35}" width="${r*.26}" height="${bh*.7}" rx="${r*.06}" fill="${dc}"/>`;
      if(s.atk>60)o+=`<ellipse cx="${ax}" cy="${cy+bh*.28}" rx="${r*.18}" ry="${r*.1}" fill="${lc}" opacity=".6"/>`;
    }
    for(const sd of[-1,1]){const lx=cx+sd*bw*.46;
      o+=`<rect x="${lx-r*.15}" y="${cy+bh*.5}" width="${r*.3}" height="${r*.4}" rx="${r*.04}" fill="${dc}"/>`;
      o+=`<rect x="${lx-r*.2}" y="${cy+bh*.5+r*.4}" width="${r*.4}" height="${r*.12}" rx="${r*.03}" fill="${mc}"/>`;}
    return o;
  },

  serpent(cx,cy,r,mc,dc,lc,s){
    const bw=r*1.1,bh=r*.7; let o='';
    o+=`<path d="M${cx-bw},${cy+bh*1.2} Q${cx-bw*.5},${cy-bh*.2} ${cx},${cy+bh*.6} Q${cx+bw*.5},${cy+bh*1.4} ${cx+bw},${cy-bh*.1}" fill="none" stroke="${dc}" stroke-width="${bh*.55}" stroke-linecap="round"/>`;
    o+=`<path d="M${cx-bw*.85},${cy+bh*1.15} Q${cx-bw*.4},${cy-bh*.05} ${cx},${cy+bh*.55} Q${cx+bw*.4},${cy+bh*1.35} ${cx+bw*.85},${cy-bh*.05}" fill="none" stroke="${mc}" stroke-width="${bh*.38}" stroke-linecap="round"/>`;
    const ns=3+Math.floor(s.fcs/25);
    for(let i=0;i<ns;i++){const sx=cx-bw*.4+i*r*.15,sy=cy+r*.3+Math.sin(i)*r*.09;
      o+=`<ellipse cx="${sx}" cy="${sy}" rx="${r*.09}" ry="${r*.055}" fill="${lc}" opacity=".4"/>`;
    }
    if(s.atk>30){const rl=s.atk/100;o+=`<ellipse cx="${cx+bw*.88}" cy="${cy+bh*.62}" rx="${r*(.08+rl*.07)}" ry="${r*(.1+rl*.09)}" fill="${lc}"/>`;}
    return o;
  },

  insect(cx,cy,r,mc,dc,lc,s){
    let o='';
    o+=`<ellipse cx="${cx}" cy="${cy+r*.1}" rx="${r*.75}" ry="${r*.55}" fill="${dc}"/>`;
    o+=`<ellipse cx="${cx}" cy="${cy}" rx="${r*.7}" ry="${r*.5}" fill="${mc}"/>`;
    o+=`<ellipse cx="${cx}" cy="${cy-r*.45}" rx="${r*.45}" ry="${r*.35}" fill="${dc}"/>`;
    o+=`<ellipse cx="${cx}" cy="${cy-r*.5}" rx="${r*.4}" ry="${r*.3}" fill="${mc}"/>`;
    o+=`<line x1="${cx}" y1="${cy-r*.5}" x2="${cx}" y2="${cy+r*.55}" stroke="${dc}" stroke-width="${r*.05}"/>`;
    if(s.fcs>50){o+=`<ellipse cx="${cx-r*.3}" cy="${cy-r*.1}" rx="${r*.28}" ry="${r*.38}" fill="${lc}" opacity=".25" transform="rotate(-15,${cx-r*.3},${cy-r*.1})"/>`;o+=`<ellipse cx="${cx+r*.3}" cy="${cy-r*.1}" rx="${r*.28}" ry="${r*.38}" fill="${lc}" opacity=".25" transform="rotate(15,${cx+r*.3},${cy-r*.1})"/>`;}
    const pairs=s.agi>65?4:3;
    const legY=Array.from({length:pairs},(_,i)=>cy-r*.2+i*(r*.55/(pairs-1)));
    legY.forEach((ly,i)=>{[-1,1].forEach(sd=>{const lx=cx+sd*(r*.65+r*.4),lean=(i-.5)*.12*sd;
      o+=`<line x1="${cx+sd*r*.65}" y1="${ly}" x2="${lx}" y2="${ly+lean*r}" stroke="${dc}" stroke-width="${r*.06}" stroke-linecap="round"/>`;
      o+=`<line x1="${lx}" y1="${ly+lean*r}" x2="${lx+sd*r*.3}" y2="${ly+lean*r+r*.2}" stroke="${mc}" stroke-width="${r*.04}" stroke-linecap="round"/>`;
    });});
    for(const sd of[-1,1]){o+=`<line x1="${cx+sd*r*.2}" y1="${cy-r*.75}" x2="${cx+sd*r*.62}" y2="${cy-r*1.12}" stroke="${dc}" stroke-width="${r*.04}" stroke-linecap="round"/>`;o+=`<circle cx="${cx+sd*r*.62}" cy="${cy-r*1.12}" r="${r*.06}" fill="${lc}"/>`;}
    return o;
  },

  phantom(cx,cy,r,mc,dc,lc,s){
    let o='';
    o+=`<path d="M${cx-r*.8},${cy+r*.3} Q${cx-r},${cy-r*.5} ${cx},${cy-r*.9} Q${cx+r},${cy-r*.5} ${cx+r*.8},${cy+r*.3} Q${cx+r*.6},${cy+r*.8} ${cx+r*.3},${cy+r*.5} Q${cx},${cy+r*.9} ${cx-r*.3},${cy+r*.5} Q${cx-r*.6},${cy+r*.8} ${cx-r*.8},${cy+r*.3}Z" fill="${dc}"/`>`;
    o+=`<path d="M${cx-r*.75},${cy+r*.25} Q${cx-r*.9},${cy-r*.45} ${cx},${cy-r*.8} Q${cx+r*.9},${cy-r*.45} ${cx+r*.75},${cy+r*.25} Q${cx+r*.55},${cy+r*.7} ${cx+r*.25},${cy+r*.4} Q${cx},${cy+r*.85} ${cx-r*.25},${cy+r*.4} Q${cx-r*.55},${cy+r*.7} ${cx-r*.75},${cy+r*.25}Z" fill="${mc}"/`>`;
    const nw=1+Math.floor(s.sup/22);
    [[-.5,.9,.25,.4],[.4,.85,.2,.35],[0,1.05,.15,.3],[-.7,.75,.13,.25],[.6,.78,.12,.22]].slice(0,nw).forEach(([wx,wy,wr1,wr2])=>
      o+=`<ellipse cx="${cx+wx*r}" cy="${cy+wy*r}" rx="${wr1*r}" ry="${wr2*r}" fill="${mc}" opacity=".5"/>`);
    o+=`<ellipse cx="${cx}" cy="${cy-r*.15}" rx="${r*.35}" ry="${r*.4}" fill="${lc}" opacity="${.15+s.fcs/100*.25}"/`>`;
    return o;
  },

  golem(cx,cy,r,mc,dc,lc,s){
    const bw=r*1.05,bh=r*.72; let o='';
    o+=`<rect x="${cx-bw*1.06}" y="${cy-bh*.56}" width="${bw*2.12}" height="${bh*1.12}" rx="${r*.06}" fill="${dc}"/>`;
    o+=`<rect x="${cx-bw}" y="${cy-bh*.5}" width="${bw*2}" height="${bh}" rx="${r*.05}" fill="${mc}"/>`;
    if(s.stm>50){o+=`<rect x="${cx-bw*.8}" y="${cy-bh*.45}" width="${bw*1.6}" height="${r*.06}" rx="3" fill="${dc}" opacity=".35"/>`;o+=`<rect x="${cx-bw*.7}" y="${cy}" width="${bw*1.4}" height="${r*.05}" rx="3" fill="${dc}" opacity=".25"/>`;}
    const nc=Math.floor((100-s.stm)/22);
    [[cx-r*.3,cy-r*.1,cx-r*.15,cy+r*.3],[cx+r*.2,cy-r*.25,cx+r*.35,cy+r*.15],[cx,cy-r*.3,cx-r*.1,cy+r*.1],[cx+r*.05,cy+r*.05,cx+r*.25,cy+r*.28]].slice(0,nc).forEach(([x1,y1,x2,y2])=>
      o+=`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${dc}" stroke-width="${r*.04}" stroke-linecap="round"/>`);
    for(const sd of[-1,1]){o+=`<rect x="${cx+sd*(bw+r*.05)-r*.05}" y="${cy-bh*.35}" width="${r*.42}" height="${bh*.7}" rx="${r*.06}" fill="${dc}"/>`;o+=`<rect x="${cx+sd*(bw+r*.05)-r*.03}" y="${cy-bh*.32}" width="${r*.34}" height="${bh*.52}" rx="${r*.04}" fill="${mc}"/>`;}
    for(const sd of[-1,1]){const lx=cx+sd*bw*.46;o+=`<rect x="${lx-r*.15}" y="${cy+bh*.5}" width="${r*.3}" height="${r*.42}" rx="${r*.04}" fill="${dc}"/>`;o+=`<rect x="${lx-r*.2}" y="${cy+bh*.5+r*.42}" width="${r*.4}" height="${r*.12}" rx="${r*.03}" fill="${mc}"/>`;}
    return o;
  },

  phoenix(cx,cy,r,mc,dc,lc,s){
    const bw=r*1.1,bh=r*.7;
    const wspan=bw*(.85+s.agi/100*.65); let o='';
    for(const sd of[-1,1]){
      o+=`<polygon points="${cx},${cy} ${cx+sd*wspan},${cy-bh*.5} ${cx+sd*wspan*.7},${cy+bh*.42}" fill="${dc}" opacity=".85"/>`;
      o+=`<polygon points="${cx},${cy} ${cx+sd*wspan*.82},${cy-bh*.33} ${cx+sd*wspan*.58},${cy+bh*.3}" fill="${mc}" opacity=".62"/>`;
      const np=1+Math.floor(s.sup/28);
      for(let p=0;p<np;p++){const px=cx+sd*(wspan*.4+p*wspan*.14),py=cy-bh*.18-p*r*.12;
        o+=`<ellipse cx="${px}" cy="${py}" rx="${r*.08}" ry="${r*.2}" fill="${lc}" opacity=".8" transform="rotate(${sd*(-18+p*8)},${px},${py})"/>`;
      }
    }
    o+=`<ellipse cx="${cx}" cy="${cy+bh*.2}" rx="${bw*.38}" ry="${bh*.54}" fill="${dc}"/>`;
    o+=`<ellipse cx="${cx}" cy="${cy+bh*.1}" rx="${bw*.33}" ry="${bh*.48}" fill="${mc}"/>`;
    o+=`<polygon points="${cx-bw*.25},${cy+bh*.58} ${cx+bw*.25},${cy+bh*.58} ${cx},${cy+bh*1.12}" fill="${dc}"/>`;
    o+=`<polygon points="${cx-bw*.14},${cy+bh*.63} ${cx},${cy+bh*.58} ${cx-bw*.28},${cy+bh*1.07}" fill="${lc}" opacity=".7"/>`;
    o+=`<polygon points="${cx+bw*.14},${cy+bh*.63} ${cx},${cy+bh*.58} ${cx+bw*.28},${cy+bh*1.07}" fill="${lc}" opacity=".7"/>`;
    return o;
  },

  crystal(cx,cy,r,mc,dc,lc,s){
    let o='';
    o+=`<polygon points="${cx},${cy-r} ${cx+r*.45},${cy-r*.1} ${cx+r*.3},${cy+r*.62} ${cx-r*.3},${cy+r*.62} ${cx-r*.45},${cy-r*.1}" fill="${dc}"/`>`;
    o+=`<polygon points="${cx},${cy-r*.88} ${cx+r*.38},${cy-r*.08} ${cx+r*.25},${cy+r*.52} ${cx-r*.25},${cy+r*.52} ${cx-r*.38},${cy-r*.08}" fill="${mc}"/`>`;
    o+=`<polygon points="${cx},${cy-r*.88} ${cx+r*.38},${cy-r*.08} ${cx},${cy+r*.12}" fill="${lc}" opacity=".3"/>`;
    const nc=2+Math.floor(s.fcs/28);
    const sc=[[-r*.65,r*.1,r*.52,0.72],[r*.55,r*.15,r*.47,0.72],[-r*.4,-r*.28,r*.42,0.55],[r*.35,-r*.23,r*.37,0.55],[-r*.75,r*.3,r*.3,0.45],[r*.68,r*.28,r*.28,0.45]];
    sc.slice(0,nc).forEach(([ox,oy,sh,op])=>o+=`<polygon points="${cx+ox},${cy+oy-sh} ${cx+ox+sh*.3},${cy+oy+sh*.4} ${cx+ox-sh*.3},${cy+oy+sh*.4}" fill="${mc}" opacity="${op}"/`>`);
    o+=`<ellipse cx="${cx}" cy="${cy+r*.64}" rx="${r*.55}" ry="${r*.12}" fill="${dc}" opacity=".5"/>`;
    o+=`<ellipse cx="${cx}" cy="${cy-r*.3}" rx="${r*.15}" ry="${r*.35}" fill="${lc}" opacity="${.2+s.fcs/100*.35}"/`>`;
    return o;
  },

  tentacle(cx,cy,r,mc,dc,lc,s){
    let o='';
    o+=`<ellipse cx="${cx}" cy="${cy-r*.2}" rx="${r*.65}" ry="${r*.82}" fill="${dc}"/>`;
    o+=`<ellipse cx="${cx}" cy="${cy-r*.25}" rx="${r*.58}" ry="${r*.74}" fill="${mc}"/>`;
    for(const sd of[-1,1])o+=`<ellipse cx="${cx+sd*r*.55}" cy="${cy-r*.35}" rx="${r*.18}" ry="${r*.3}" fill="${dc}" opacity=".8" transform="rotate(${sd*20},${cx+sd*r*.55},${cy-r*.35})"/>`;
    if(s.fcs>40){[[-.2,.1],[.25,-.05],[0,.35],[-.3,.3]].forEach(([fx,fy])=>o+=`<circle cx="${cx+fx*r}" cy="${cy+fy*r}" r="${r*.04}" fill="${lc}" opacity=".7"/>`);}
    const nT=3+Math.floor(s.sup/18);
    for(let i=0;i<Math.min(nT,10);i++){
      const ang=(i/(Math.min(nT,10)-1)*1.3-.65)*Math.PI;
      const tx=cx+Math.sin(ang)*r*.52,ty=cy+r*.5;
      const ex=cx+Math.sin(ang)*r*(.78+i*.04),ey=cy+r*(.88+Math.abs(Math.sin(ang))*.42);
      o+=`<path d="M${tx},${ty} Q${(tx+ex)/2+Math.cos(ang)*r*.22},${(ty+ey)/2} ${ex},${ey}" fill="none" stroke="${i%2===0?dc:mc}" stroke-width="${r*(.13-i*.01)}" stroke-linecap="round"/>`;
      o+=`<circle cx="${ex}" cy="${ey}" r="${r*.062}" fill="${lc}" opacity=".72"/>`;
    }
    return o;
  },

  chimera(cx,cy,r,mc,dc,lc,s){
    const sc2=MSC[mSec(s)],scd=MSD[mSec(s)]; let o='';
    o+=`<ellipse cx="${cx-r*.28}" cy="${cy+r*.1}" rx="${r*.67}" ry="${r*.62}" fill="${dc}"/`>`;
    o+=`<ellipse cx="${cx+r*.28}" cy="${cy+r*.05}" rx="${r*.62}" ry="${r*.57}" fill="${scd}"/>`;
    o+=`<line x1="${cx}" y1="${cy-r*.58}" x2="${cx}" y2="${cy+r*.68}" stroke="${lc}" stroke-width="${r*.05}" stroke-dasharray="${r*.1} ${r*.06}" opacity=".82"/>`;
    o+=`<rect x="${cx-r*1.2}" y="${cy-r*.15}" width="${r*.38}" height="${r*.58}" rx="${r*.08}" fill="${dc}"/>`;
    o+=`<ellipse cx="${cx+r*.98}" cy="${cy+r*.15}" rx="${r*.22}" ry="${r*.36}" fill="${scd}"/>`;
    for(const sd of[-1,1]){const lx=cx+sd*r*.45;o+=`<rect x="${lx-r*.15}" y="${cy+r*.6}" width="${r*.3}" height="${r*.42}" rx="${r*.05}" fill="${sd<0?dc:scd}"/>`;}
    o+=`<line x1="${cx}" y1="${cy-r*.55}" x2="${cx}" y2="${cy+r*.65}" stroke="${lc}" stroke-width="${r*.02}" opacity=".6"/>`;
    return o;
  },

  wraith(cx,cy,r,mc,dc,lc,s){
    let o='';
    const nr=3+Math.floor(s.stm/30);
    for(let i=0;i<nr;i++){const ry2=cy-r*.15+i*r*(1.0/(nr-1))*.8,rx3=r*(.65-i*.04);
      o+=`<path d="M${cx},${ry2} Q${cx+rx3},${ry2-r*.12} ${cx+rx3*.9},${ry2+r*.1}" fill="none" stroke="${mc}" stroke-width="${r*.075}" stroke-linecap="round"/>`;
      o+=`<path d="M${cx},${ry2} Q${cx-rx3},${ry2-r*.12} ${cx-rx3*.9},${ry2+r*.1}" fill="none" stroke="${mc}" stroke-width="${r*.075}" stroke-linecap="round"/>`;
    }
    o+=`<line x1="${cx}" y1="${cy-r*.72}" x2="${cx}" y2="${cy+r*.72}" stroke="${dc}" stroke-width="${r*.1}" stroke-linecap="round"/>`;
    for(const sd of[-1,1]){
      o+=`<line x1="${cx}" y1="${cy-r*.1}" x2="${cx+sd*r*.82}" y2="${cy-r*.22}" stroke="${dc}" stroke-width="${r*.08}" stroke-linecap="round"/>`;
      o+=`<line x1="${cx+sd*r*.82}" y1="${cy-r*.22}" x2="${cx+sd*r*1.08}" y2="${cy+r*.32}" stroke="${dc}" stroke-width="${r*.07}" stroke-linecap="round"/>`;
      o+=`<circle cx="${cx+sd*r*.82}" cy="${cy-r*.22}" r="${r*.1}" fill="${mc}"/>`;
    }
    o+=`<ellipse cx="${cx}" cy="${cy}" rx="${r*.9}" ry="${r*.94}" fill="${MSD[mDom(s)]}" opacity=".18"/>`;
    return o;
  },
};

const HEADS = {
  alien:(hx,hy,hs,dc,mc,lc,s)=>
    `<ellipse cx="${hx}" cy="${hy-hs*.12}" rx="${hs*.7}" ry="${hs*1.12}" fill="${dc}"/`>` +
    `<ellipse cx="${hx}" cy="${hy-hs*.18}" rx="${hs*.62}" ry="${hs*1.02}" fill="${mc}"/>`,

  angular:(hx,hy,hs,dc,mc,lc,s)=>
    `<polygon points="${hx},${hy-hs} ${hx+hs*.92},${hy-hs*.12} ${hx+hs*.72},${hy+hs*.82} ${hx-hs*.72},${hy+hs*.82} ${hx-hs*.92},${hy-hs*.12}" fill="${dc}"/>` +
    `<polygon points="${hx},${hy-hs*.86} ${hx+hs*.8},${hy-hs*.06} ${hx+hs*.6},${hy+hs*.72} ${hx-hs*.6},${hy+hs*.72} ${hx-hs*.8},${hy-hs*.06}" fill="${mc}"/>`,

  skull:(hx,hy,hs,dc,mc,lc,s)=>
    `<ellipse cx="${hx}" cy="${hy-hs*.1}" rx="${hs*.88}" ry="${hs*1.02}" fill="${dc}"/`>` +
    `<ellipse cx="${hx}" cy="${hy-hs*.15}" rx="${hs*.78}" ry="${hs*.94}" fill="${mc}"/>` +
    `<rect x="${hx-hs*.58}" y="${hy+hs*.56}" width="${hs*1.16}" height="${hs*.46}" rx="${hs*.04}" fill="${dc}"/>`,

  wide:(hx,hy,hs,dc,mc,lc,s)=>
    `<ellipse cx="${hx}" cy="${hy+hs*.12}" rx="${hs*1.28}" ry="${hs*.76}" fill="${dc}"/`>` +
    `<ellipse cx="${hx}" cy="${hy}" rx="${hs*1.18}" ry="${hs*.7}" fill="${mc}"/>`,

  crown(hx,hy,hs,dc,mc,lc,s){
    let o=`<circle cx="${hx}" cy="${hy}" r="${hs*1.06}" fill="${dc}"/><circle cx="${hx}" cy="${hy}" r="${hs}" fill="${mc}"/`>`;
    const cpts=[-0.65,-0.3,0,0.3,0.65].map((p,i)=>`${hx+p*hs},${hy-hs*(i%2===0?1.12:0.72)}`).join(' ');
    o+=`<polyline points="${cpts}" fill="none" stroke="${lc}" stroke-width="${hs*.075}" stroke-linecap="round" stroke-linejoin="round" opacity=".92"/>`;
    o+=`<polygon points="${hx},${hy-hs*1.22} ${hx+hs*.1},${hy-hs*1.08} ${hx},${hy-hs*.98} ${hx-hs*.1},${hy-hs*1.08}" fill="${MSC.fcs}" opacity=".9"/>`;
    return o;
  },

  mask:(hx,hy,hs,dc,mc,lc,s)=>
    `<polygon points="${hx-hs},${hy-hs*.52} ${hx},${hy-hs} ${hx+hs},${hy-hs*.52} ${hx+hs},${hy+hs*.82} ${hx},${hy+hs} ${hx-hs},${hy+hs*.82}" fill="${dc}"/>` +
    `<polygon points="${hx-hs*.88},${hy-hs*.44} ${hx},${hy-hs*.88} ${hx+hs*.88},${hy-hs*.44} ${hx+hs*.88},${hy+hs*.74} ${hx},${hy+hs*.92} ${hx-hs*.88},${hy+hs*.74}" fill="${mc}"/>` +
    `<rect x="${hx-hs*.68}" y="${hy-hs*.18}" width="${hs*1.36}" height="${hs*.22}" rx="${hs*.08}" fill="${dc}" opacity=".6"/>` +
    `<rect x="${hx-hs*.62}" y="${hy-hs*.16}" width="${hs*1.24}" height="${hs*.18}" rx="${hs*.06}" fill="${lc}" opacity="${.3+s.agi/100*.4}"/>`,

  gem:(hx,hy,hs,dc,mc,lc,s)=>
    `<polygon points="${hx},${hy-hs*.92} ${hx+hs*.82},${hy} ${hx+hs*.52},${hy+hs*.58} ${hx-hs*.52},${hy+hs*.58} ${hx-hs*.82},${hy}" fill="${dc}"/>` +
    `<polygon points="${hx},${hy-hs*.75} ${hx+hs*.65},${hy} ${hx+hs*.4},${hy+hs*.43} ${hx-hs*.4},${hy+hs*.43} ${hx-hs*.65},${hy}" fill="${mc}"/>` +
    `<polygon points="${hx},${hy-hs*.75} ${hx+hs*.65},${hy} ${hx},${hy+hs*.05}" fill="${lc}" opacity=".28"/>`,

  round:(hx,hy,hs,dc,mc,lc,s)=>
    `<ellipse cx="${hx}" cy="${hy}" rx="${hs*.92}" ry="${hs*1.02}" fill="${dc}"/`>` +
    `<ellipse cx="${hx}" cy="${hy}" rx="${hs*.82}" ry="${hs*.92}" fill="${mc}"/>`,
};

const EYES = {
  cyclopean(hx,ey,er,ec,pc,s){
    let o=`<circle cx="${hx}" cy="${ey}" r="${er*2.6}" fill="${ec}"/>`;
    o+=`<ellipse cx="${hx}" cy="${ey}" rx="${er*.82}" ry="${er*2.05}" fill="${pc}"/`>`;
    o+=`<circle cx="${hx-er*.72}" cy="${ey-er*.72}" r="${er*.58}" fill="#ffffff" opacity=".85"/>`;
    const nr=6+Math.floor(s.fcs/18);
    for(let i=0;i<nr;i++){const a=i*Math.PI*2/nr;o+=`<line x1="${hx+Math.cos(a)*er*1.25}" y1="${ey+Math.sin(a)*er*1.25}" x2="${hx+Math.cos(a)*er*2.45}" y2="${ey+Math.sin(a)*er*2.45}" stroke="${pc}" stroke-width=".9" opacity=".5"/>`;}
    return o;
  },

  slit(hx,ey,er,ec,pc,s){
    let o='';
    const tilt=5+s.agi/100*18;
    for(const sd of[-1,1]){const ex=hx+sd*er*2.25;
      o+=`<ellipse cx="${ex}" cy="${ey}" rx="${er*1.55}" ry="${er*.72}" fill="${ec}" transform="rotate(${sd*-tilt},${ex},${ey})"/>`;
      o+=`<ellipse cx="${ex}" cy="${ey}" rx="${er*.3}" ry="${er*.64}" fill="${pc}"/`>`;
      o+=`<circle cx="${ex-er*.5}" cy="${ey-er*.2}" r="${er*.22}" fill="#fff" opacity=".6"/>`;
    }
    return o;
  },

  star(hx,ey,er,ec,pc,s){
    let o='';
    const np=4+Math.floor(s.sup/22);
    for(const sd of[-1,1]){const ex=hx+sd*er*2.25;
      o+=`<circle cx="${ex}" cy="${ey}" r="${er*1.35}" fill="${ec}"/>`;
      const pts=Array.from({length:np*2},(_,i)=>{const a=i*Math.PI/np-Math.PI/2,rr=i%2===0?er*1.15:er*.52;return`${ex+Math.cos(a)*rr},${ey+Math.sin(a)*rr}`;}).join(' ');
      o+=`<polygon points="${pts}" fill="${pc}"/`>`;
      o+=`<circle cx="${ex-er*.4}" cy="${ey-er*.4}" r="${er*.3}" fill="#fff" opacity=".6"/>`;
    }
    return o;
  },

  hollow(hx,ey,er,ec,pc,s){
    let o='';
    for(const sd of[-1,1]){const ex=hx+sd*er*2.25;
      o+=`<circle cx="${ex}" cy="${ey}" r="${er*1.35}" fill="none" stroke="${ec}" stroke-width="${er*.52}"/>`;
      o+=`<circle cx="${ex}" cy="${ey}" r="${er*.42}" fill="${ec}"/`>`;
      if(s.stm>80)o+=`<circle cx="${ex}" cy="${ey}" r="${er*1.55}" fill="none" stroke="${ec}" stroke-width="${er*.15}" opacity=".3"/>`;
    }
    return o;
  },

  insect(hx,ey,er,ec,pc,s){
    let o='';
    for(const sd of[-1,1]){const ex=hx+sd*er*2.1,hr2=er*.42;
      for(let di=0;di<7;di++){const hang=di*Math.PI/3;o+=`<circle cx="${ex+Math.cos(hang)*hr2}" cy="${ey+Math.sin(hang)*hr2}" r="${hr2*.5}" fill="${ec}"/>`;}
      o+=`<circle cx="${ex}" cy="${ey}" r="${hr2*.48}" fill="${pc}"/>`;
      o+=`<circle cx="${ex-hr2*.5}" cy="${ey-hr2*.5}" r="${hr2*.25}" fill="#fff" opacity=".5"/>`;
    }
    return o;
  },

  round(hx,ey,er,ec,pc,s){
    let o='';
    for(const sd of[-1,1]){const ex=hx+sd*er*2.25;
      o+=`<circle cx="${ex}" cy="${ey}" r="${er*1.25}" fill="${ec}"/>`;
      o+=`<circle cx="${ex}" cy="${ey}" r="${er*.68}" fill="${pc}"/>`;
      o+=`<circle cx="${ex-er*.3}" cy="${ey-er*.3}" r="${er*.34}" fill="#ffffff" opacity=".72"/>`;
    }
    return o;
  },
};

function drawHorns(hx,hy,hs,s,dc,lc){
  if(s.atk<=15)return'';
  const n=s.atk>85?4:s.atk>65?3:s.atk>38?2:1;
  const hh=hs*(.18+s.atk/100*.32),hw=hs*.1,hBase=hy-hs*.88;
  const pos={1:[0],2:[-.48,.48],3:[-.62,0,.62],4:[-.75,-.28,.28,.75]}[n];
  return pos.map(p=>{const hpx=hx+p*hs,lean=p*.28;
    return `<polygon points="${hpx-hw},${hBase} ${hpx+hw},${hBase} ${hpx+lean*hh},${hBase-hh}" fill="${dc}"/`>` +
           `<polygon points="${hpx-hw*.5},${hBase} ${hpx+hw*.5},${hBase} ${hpx+lean*hh*.72},${hBase-hh*.78}" fill="${lc}" opacity=".48"/>`;
  }).join('');
}

function drawWings(cx,cy,r,s,dc,sc){
  if(s.agi<=38)return'';
  const ww=r*(.85+s.agi/100*.95),wh=r*(.65+s.agi/100*.65); let o='';
  for(const sd of[-1,1]){const wx=cx+sd*r*.52;
    o+=`<polygon points="${wx},${cy} ${wx+sd*ww},${cy-wh*.52} ${wx+sd*ww*.78},${cy+wh*.58}" fill="${dc}" opacity=".88"/>`;
    o+=`<polygon points="${wx},${cy} ${wx+sd*ww*.82},${cy-wh*.3} ${wx+sd*ww*.58},${cy+wh*.42}" fill="${sc}" opacity=".32"/>`;
    if(s.agi>65){const mx=wx+sd*ww*.55,my=cy-wh*.22;o+=`<line x1="${wx}" y1="${cy}" x2="${mx}" y2="${my}" stroke="${sc}" stroke-width="${r*.02}" opacity=".5" stroke-linecap="round"/>`;o+=`<line x1="${wx}" y1="${cy}" x2="${wx+sd*ww*.38}" y2="${cy+wh*.32}" stroke="${sc}" stroke-width="${r*.015}" opacity=".4" stroke-linecap="round"/>`;}}
  return o;
}

function drawAura(cx,cy,size,s,mc){
  if(s.sup<=18)return'';
  const au=s.sup/100; let o='';
  o+=`<circle cx="${cx}" cy="${cy}" r="${size*.44}" fill="none" stroke="${MSC.sup}" stroke-width="${1+au*3.2}" opacity="${.1+au*.32}"/>`;
  if(s.sup>45){o+=`<circle cx="${cx}" cy="${cy}" r="${size*.47}" fill="none" stroke="${MSL.sup}" stroke-width="${.5+au}" opacity="${au*.2}"/`>`;}
  const np=Math.floor(s.sup/18);
  for(let i=0;i<np;i++){const a=(i/np)*Math.PI*2;
    o+=`<circle cx="${cx+Math.cos(a)*size*.44}" cy="${cy+Math.sin(a)*size*.44}" r="${size*.02}" fill="${MSL.sup}" opacity=".8"/>`;
  }
  if(s.sup>60)o+=`<circle cx="${cx}" cy="${cy}" r="${size*.38}" fill="none" stroke="${mc}" stroke-width="${.5}" opacity="${au*.2}"/>`;
  return o;
}

function drawStreaks(cx,cy,size,s,lc){
  if(s.agi<=55)return'';
  const n=1+Math.floor(s.agi/22); let o='';
  for(let i=0;i<n;i++){const a=(i/n)*Math.PI+.18;
    o+=`<line x1="${cx+Math.cos(a)*size*.3}" y1="${cy+Math.sin(a)*size*.3}" x2="${cx+Math.cos(a)*size*.48}" y2="${cy+Math.sin(a)*size*.48}" stroke="${lc}" stroke-width="${size*.014}" opacity=".52" stroke-linecap="round"/>`;
  }
  return o;
}

function drawMouth(hx,hy,hs,s,dc,lc){
  const my=hy+hs*.57;
  if(s.atk>s.sup+15){
    const mw=hs*.54;
    let o=`<path d="M${hx-mw},${my} Q${hx},${my+hs*.3} ${hx+mw},${my}" fill="none" stroke="${dc}" stroke-width="${hs*.09}" stroke-linecap="round"/>`;
    const nf=s.atk>72?2:1;
    const fp=nf===1?[[0,.18]]:[[-.28,.2],[.28,.2]];
    fp.forEach(([fx,fy])=>o+=`<polygon points="${hx+fx*hs-hs*.08},${my} ${hx+fx*hs+hs*.08},${my} ${hx+fx*hs},${my+fy*hs}" fill="#ffffff" opacity=".82"/>`);
    return o;
  }
  if(s.sup>52){const mw=hs*.42;return`<path d="M${hx-mw},${my} Q${hx},${my+hs*.35} ${hx+mw},${my}" fill="none" stroke="${lc}" stroke-width="${hs*.075}" stroke-linecap="round"/>`;}
  const mw=hs*.32;return`<line x1="${hx-mw}" y1="${my+hs*.04}" x2="${hx+mw}" y2="${my+hs*.04}" stroke="${lc}" stroke-width="${hs*.07}" stroke-linecap="round"/>`;
}

function drawGem(hx,hy,hs,s,headType){
  if(s.fcs<=42||headType==='gem')return'';
  const gr=hs*(.16+s.fcs/100*.08);
  return `<polygon points="${hx},${hy-hs*.9} ${hx+gr},${hy-hs*.68} ${hx},${hy-hs*.54} ${hx-gr},${hy-hs*.68}" fill="${MSC.fcs}" opacity=".92"/>` +
         `<polygon points="${hx},${hy-hs*.9} ${hx+gr},${hy-hs*.68} ${hx},${hy-hs*.72}" fill="#fff" opacity=".35"/>`;
}

function selectBody(s,seed){
  const d=mDom(s),sc=mSec(s);
  let choices=[];
  if(d==='atk')choices=s.agi>65?['phoenix','chimera','dragon']:s.fcs>60?['chimera','dragon','golem']:['dragon','golem','mech'];
  else if(d==='stm')choices=sc==='atk'?['golem','dragon','chimera']:s.fcs>58?['mech','golem','crystal']:s.sup>55?['tentacle','slime','phantom']:['slime','golem','mech'];
  else if(d==='fcs')choices=s.atk>55?['mech','crystal','chimera']:s.stm>55?['crystal','golem','mech']:s.agi>55?['phantom','crystal','serpent']:['crystal','phantom','mech'];
  else if(d==='agi')choices=s.fcs>52?['insect','phantom','serpent']:s.sup>52?['phantom','wraith','serpent']:s.atk>55?['phoenix','serpent','chimera']:['serpent','phantom','insect'];
  else if(d==='sup')choices=s.agi>52?['wraith','phantom','serpent']:s.stm>48?['tentacle','phantom','slime']:s.fcs>55?['crystal','phantom','tentacle']:['phantom','wraith','tentacle'];
  else choices=['dragon','slime','golem'];
  if(seed){
    const h=[...seed].reduce((a,c)=>(a*31+c.charCodeAt(0))|0,0);
    return choices[h%choices.length];
  }
  return choices[0];
}
function selectHead(s){
  if(s.fcs>=80)return'alien';
  if(s.atk>=78)return'angular';
  if(s.stm>=75)return'skull';
  if(s.agi>=80)return'mask';
  if(s.sup>=80)return'crown';
  if(s.fcs>=55)return'gem';
  if(s.atk>=48)return'wide';
  return'round';
}
function selectEyes(s){
  const d=mDom(s);
  if(d==='fcs')return'cyclopean';
  if(s.agi>=68)return'slit';
  if(s.sup>=68)return'star';
  if(s.stm>=68)return'hollow';
  if(s.fcs>=48&&s.agi>=48)return'insect';
  return'round';
}

function drawMonster(svg, s, size, seed){
  const cx=size/2, cy=size/2;
  const scale=0.68+(mTot(s)/500)*0.32;
  const r=Math.round(size*0.27*scale);
  const d=mDom(s), sc=mSec(s);
  const mc=MSC[d], dc=MSD[d], lc=MSL[d];

  const bodyType=selectBody(s,seed);
  const bodyCY=cy+size*.06;
  const hs=Math.round(size*(.17+s.stm/100*.09)*scale);
  const hx=cx, hy=bodyCY-hs*.9;
  const headType=selectHead(s);
  const eyeType=selectEyes(s);

  const ec=s.fcs>62?lc:(s.sup>62?MSL.sup:(s.agi>62?MSL.agi:'#dde8ff'));
  const pc='#040510';
  const er=Math.max(hs*.12, hs*.1+s.fcs/100*hs*.1);
  const ey=hy-hs*.1;

  let out=`<rect width="${size}" height="${size}" rx="${Math.round(size*.15)}" fill="#0d0d18"/>`;
  out+=drawAura(cx,cy,size,s,mc);
  out+=BODIES[bodyType](cx,bodyCY,r,mc,dc,lc,s);
  out+=drawWings(cx,bodyCY,r,s,dc,MSC[sc]);
  out+=HEADS[headType](hx,hy,hs,dc,mc,lc,s);
  out+=drawHorns(hx,hy,hs,s,dc,lc);
  out+=drawGem(hx,hy,hs,s,headType);
  out+=EYES[eyeType](hx,ey,er,ec,pc,s);
  out+=drawMouth(hx,hy,hs,s,dc,lc);
  out+=drawStreaks(cx,cy,size,s,lc);
  svg.innerHTML=out;
}

function buildMonsterWidget(s, size, seed){
  const arc=mArchetype(s), name=mName(s), trs=mTraits(s);
  const wrap=document.createElement('div');
  wrap.className='monster-widget';
  wrap.style.cssText='position:relative;flex-shrink:0;cursor:default;display:inline-block';

  const svgNS='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(svgNS,'svg');
  svg.setAttribute('width',size); svg.setAttribute('height',size);
  svg.setAttribute('viewBox',`0 0 ${size} ${size}`);
  drawMonster(svg,s,size,seed);

  const tip=document.createElement('div');
  tip.className='monster-tip';
  tip.style.cssText=`position:absolute;bottom:calc(100% + 7px);left:50%;transform:translateX(-50%);
    background:#12121a;border:1px solid #2a2a3e;border-radius:10px;padding:9px 13px;
    font-size:11px;font-family:monospace;white-space:nowrap;pointer-events:none;
    opacity:0;transition:opacity .18s;z-index:9999;text-align:center;min-width:140px`;
  const tHtml=trs.map(t=>`<span style="display:inline-block;font-size:9px;padding:1px 6px;border-radius:6px;margin:1px;background:${t.c}22;color:${t.c};border:1px solid ${t.c}44">${t.t}</span>`).join('');
  tip.innerHTML=`<div style="font-size:13px;font-weight:800;letter-spacing:1.5px;color:${arc.c};margin-bottom:2px">${name}</div>`+
                `<div style="font-size:10px;opacity:.82;color:${arc.c};margin-bottom:5px">${arc.l}</div>`+
                `<div>${tHtml}</div>`;

  wrap.appendChild(svg);
  wrap.appendChild(tip);
  wrap.addEventListener('mouseenter',()=>tip.style.opacity='1');
  wrap.addEventListener('mouseleave',()=>tip.style.opacity='0');
  return wrap;
}
