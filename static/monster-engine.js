const MSC  = {atk:'#ff4444', stm:'#00e676', fcs:'#ffd600', agi:'#00e5ff', sup:'#a855f7'};
const MSD  = {atk:'#881111', stm:'#006633', fcs:'#886600', agi:'#006688', sup:'#551188'};
const MSL  = {atk:'#ff9999', stm:'#88ffcc', fcs:'#ffee88', agi:'#88eeff', sup:'#cc88ff'};

const mDom = s => Object.entries(s).sort((a,b)=>b[1]-a[1])[0][0];
const mSec = s => Object.entries(s).sort((a,b)=>b[1]-a[1])[1][0];
const mTot = s => Object.values(s).reduce((a,b)=>a+b,0);

// Deterministic pseudo-random generator from name string
function nameSeed(name){
  if(!name)return()=>0;
  let h=0;
  for(let i=0;i<name.length;i++)h=((h<<5)-h+name.charCodeAt(i))|0;
  const seed=Math.abs(h)||1;
  let s=seed;
  return function(max){
    s=(s*16807+0)%2147483647;
    return max===undefined?s:(s%max);
  };
}

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

function getDominant(s){return mDom(s);}
function getSecondary(s){return mSec(s);}
function getTotal(s){return mTot(s);}

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

function getCoreArchetype(s){
  const dom=mDom(s),sc=mSec(s);
  const map={
    atk:{stm:'BERSERKER',fcs:'ASSASSIN',agi:'STRIKER',sup:'WARLORD',atk:'DESTROYER'},
    stm:{atk:'TANK',fcs:'SENTINEL',agi:'IRONFOOT',sup:'GUARDIAN',stm:'FORTRESS'},
    fcs:{atk:'SNIPER',stm:'SCHOLAR',agi:'PHANTOM',sup:'ORACLE',fcs:'ENLIGHTENED'},
    agi:{atk:'DUELIST',stm:'RUNNER',fcs:'TRICKSTER',sup:'HERALD',agi:'BLUR'},
    sup:{atk:'PALADIN',stm:'MENDER',fcs:'PROPHET',agi:'BARD',sup:'ASCENDANT'},
  };
  return{label:map[dom]?.[sc]||'WANDERER',color:MSC[dom]};
}

function getTier(s){
  const t=mTot(s);
  if(t>=451)return{name:'LEGENDARY',color:'#ffd700',glow:8,scale:1.15};
  if(t>=351)return{name:'EPIC',color:'#ff8800',glow:6,scale:1.1};
  if(t>=251)return{name:'RARE',color:'#00e5ff',glow:4,scale:1.05};
  if(t>=151)return{name:'ELITE',color:'#a855f7',glow:2,scale:1.02};
  return{name:'NORMAL',color:'#7a7a9a',glow:0,scale:1};
}

function drawTierEffects(s,cx,cy,size,showTier){
  let out='';
  if(!showTier)return out;
  const tier=getTier(s);
  if(tier.glow>0){
    out+='<circle cx="'+cx+'" cy="'+cy+'" r="'+size*0.5+'" fill="none" stroke="'+tier.color+'" stroke-width="'+(tier.glow/4)+'" opacity="0.12"/>';
  }
  if(tier.name==='LEGENDARY'){
    out+='<ellipse cx="'+cx+'" cy="'+(cy-size*0.55)+'" rx="'+size*0.25+'" ry="'+size*0.06+'" fill="none" stroke="'+tier.color+'" stroke-width="'+size*0.015+'" opacity="0.5"/>';
    for(let i=0;i<6;i++){
      const a=(i/6)*Math.PI*2,r0=size*0.52;
      out+='<circle cx="'+(cx+Math.cos(a)*r0)+'" cy="'+(cy+Math.sin(a)*r0)+'" r="'+size*0.012+'" fill="'+tier.color+'" opacity="0.7"/>';
    }
  }
  if(tier.name==='EPIC'){
    out+='<circle cx="'+cx+'" cy="'+cy+'" r="'+size*0.48+'" fill="none" stroke="'+tier.color+'" stroke-width="'+size*0.008+'" opacity="0.25" stroke-dasharray="'+size*0.05+' '+size*0.05+'"/>';
  }
  return out;
}

function getElement(s){
  const entries=Object.entries(s).sort((a,b)=>b[1]-a[1]);
  const dom=entries[0][0],sec=entries[1][0];
  const pair=[dom,sec].sort().join('-');
  const map={
    'agi-atk':{name:'VOID',tint:'#8800ff'},
    'agi-fcs':{name:'LIGHTNING',tint:'#ffff00'},
    'agi-stm':{name:'WIND',tint:'#aaffaa'},
    'agi-sup':{name:'AETHER',tint:'#ccffcc'},
    'atk-fcs':{name:'FIRE',tint:'#ff4400'},
    'atk-stm':{name:'EARTH',tint:'#44aa44'},
    'atk-sup':{name:'CHAOS',tint:'#ff0088'},
    'fcs-stm':{name:'ICE',tint:'#aaffff'},
    'fcs-sup':{name:'ARCANE',tint:'#ff00ff'},
    'stm-sup':{name:'WATER',tint:'#0088ff'},
  };
  return map[pair]||{name:'PHYSICAL',tint:'#aaaaaa'};
}

function tintColor(baseColor,tintColor,amount){
  amount=amount===undefined?0.3:amount;
  const parse=(hex)=>[parseInt(hex.slice(1,3),16),parseInt(hex.slice(3,5),16),parseInt(hex.slice(5,7),16)];
  const[r1,g1,b1]=parse(baseColor);
  const[r2,g2,b2]=parse(tintColor);
  const r=Math.round(r1*(1-amount)+r2*amount);
  const g=Math.round(g1*(1-amount)+g2*amount);
  const b=Math.round(b1*(1-amount)+b2*amount);
  const toHex=(v)=>v.toString(16).padStart(2,'0');
  return '#'+toHex(r)+toHex(g)+toHex(b);
}

function getStance(s,size){
  let ox=0,oy=0;
  if(s.atk>s.stm&&s.atk>s.agi){ox=size*0.03;oy=size*0.01;}
  else if(s.stm>s.atk&&s.stm>s.agi){oy=size*0.02;}
  else if(s.agi>s.atk&&s.agi>s.stm){ox=size*0.02;oy=-size*0.01;}
  else if(s.sup>50){oy=-size*0.02;}
  return{ox,oy};
}

function drawWeapon(s,dom,sec,cx,cy,bw,bh,by,size,mc,dc,lc,showEquip,seed){
  let out='';
  if(!showEquip)return out;
  const arch=getCoreArchetype(s).label;
  const wy=by+bh*0.6;
  var wStyle='';
  if(seed){
    const wStyles=['classic','ornate','rustic','sleek'];
    wStyle=wStyles[nameSeed(seed+'-weapon')(wStyles.length)];
  }

  if(['BERSERKER','DESTROYER','WARLORD','STRIKER','TANK','FORTRESS','PALADIN','GUARDIAN','IRONFOOT','SENTINEL'].indexOf(arch)>>-1){
    const wx=cx+bw*0.8,len=size*0.25;
    if(s.atk>60){
      out+='<line x1="'+wx+'" y1="'+wy+'" x2="'+(wx+len)+'" y2="'+(wy-len*0.8)+'" stroke="'+dc+'" stroke-width="'+size*0.04+'" stroke-linecap="round"/>';
      out+='<line x1="'+wx+'" y1="'+wy+'" x2="'+(wx+len*0.8)+'" y2="'+(wy-len*0.6)+'" stroke="'+lc+'" stroke-width="'+size*0.015+'" stroke-linecap="round"/>';
    }else{
      out+='<line x1="'+wx+'" y1="'+wy+'" x2="'+(wx+len*0.8)+'" y2="'+(wy-len*0.5)+'" stroke="'+dc+'" stroke-width="'+size*0.03+'" stroke-linecap="round"/>';
    }
    if(wStyle==='ornate'){
      out+='<circle cx="'+(wx+len*0.5)+'" cy="'+(wy-len*0.4)+'" r="'+size*0.02+'" fill="'+lc+'"/>';
    }else if(wStyle==='rustic'){
      out+='<line x1="'+wx+'" y1="'+(wy-size*0.01)+'" x2="'+(wx+len)+'" y2="'+(wy-len*0.8+size*0.01)+'" stroke="'+dc+'" stroke-width="'+size*0.015+'"/>';
    }
    out+='<circle cx="'+wx+'" cy="'+wy+'" r="'+size*0.03+'" fill="'+mc+'"/>';
  }else if(['ASSASSIN','DUELIST','PHANTOM','BLUR','TRICKSTER'].indexOf(arch)>-1){
    const wx=cx+bw*0.7,len=size*0.15;
    out+='<line x1="'+wx+'" y1="'+wy+'" x2="'+(wx+len)+'" y2="'+(wy-len*0.5)+'" stroke="'+dc+'" stroke-width="'+size*0.02+'" stroke-linecap="round"/>';
    out+='<line x1="'+(wx-len*0.3)+'" y1="'+(wy+len*0.2)+'" x2="'+(wx+len*0.5)+'" y2="'+(wy-len*0.3)+'" stroke="'+dc+'" stroke-width="'+size*0.015+'" stroke-linecap="round"/>';
    if(wStyle==='sleek'){
      out+='<line x1="'+(wx+len*0.7)+'" y1="'+(wy-len*0.35)+'" x2="'+(wx+len)+'" y2="'+(wy-len*0.55)+'" stroke="'+lc+'" stroke-width="'+size*0.008+'"/>';
    }
  }else if(arch==='SNIPER'){
    const wx=cx+bw*0.9,len=size*0.2;
    out+='<path d="M'+wx+','+(wy-len)+' Q'+(wx+len)+','+wy+' '+wx+','+(wy+len)+'" fill="none" stroke="'+dc+'" stroke-width="'+size*0.025+'"/>';
    out+='<line x1="'+wx+'" y1="'+(wy-len)+'" x2="'+wx+'" y2="'+(wy+len)+'" stroke="'+lc+'" stroke-width="'+size*0.01+'"/>';
    if(wStyle==='ornate'){
      out+='<circle cx="'+(wx+len*0.5)+'" cy="'+wy+'" r="'+size*0.015+'" fill="'+lc+'"/>';
    }
  }else if(['SCHOLAR','ENLIGHTENED','ORACLE','PROPHET','ASCENDANT','MENDER'].indexOf(arch)>-1){
    const wx=cx+bw*0.8,len=size*0.3;
    out+='<line x1="'+wx+'" y1="'+wy+'" x2="'+(wx+len*0.2)+'" y2="'+(wy-len)+'" stroke="'+dc+'" stroke-width="'+size*0.025+'" stroke-linecap="round"/>';
    out+='<circle cx="'+(wx+len*0.2)+'" cy="'+(wy-len)+'" r="'+size*0.04+'" fill="'+MSC['fcs']+'"/>';
    if(wStyle==='rustic'){
      out+='<path d="M'+(wx+len*0.1)+','+(wy-len*0.3)+' Q'+(wx+len*0.3)+','+(wy-len*0.5)+' '+(wx+len*0.2)+','+(wy-len)+'" fill="none" stroke="'+lc+'" stroke-width="'+size*0.008+'"/>';
    }
  }else{
    const wx=cx+bw*0.8,len=size*0.12;
    out+='<line x1="'+wx+'" y1="'+wy+'" x2="'+(wx+len)+'" y2="'+(wy-len*0.4)+'" stroke="'+dc+'" stroke-width="'+size*0.02+'" stroke-linecap="round"/>';
  }
  if(s.stm>60&&['TANK','FORTRESS','GUARDIAN','PALADIN','SENTINEL','IRONFOOT'].indexOf(arch)>-1){
    const sx=cx-bw*0.9,sy=wy,sr=size*0.1;
    out+='<path d="M'+sx+','+(sy-sr)+' Q'+(sx+sr*1.2)+','+(sy-sr*0.5)+' '+(sx+sr)+','+(sy+sr)+' Q'+sx+','+(sy+sr*1.2)+' '+(sx-sr)+','+(sy+sr)+' Q'+(sx-sr*1.2)+','+(sy-sr*0.5)+' '+sx+','+(sy-sr)+'" fill="'+dc+'" stroke="'+mc+'" stroke-width="'+size*0.01+'"/>';
  }
  return out;
}

function drawArmor(s,dom,sec,cx,cy,bw,bh,by,size,mc,dc,lc,showEquip){
  let out='';
  if(!showEquip)return out;
  if(s.stm>50&&s.agi<50){
    const ax=cx,ay=by+bh*0.4,aw=bw*1.1,ah=bh*0.6;
    out+='<rect x="'+(ax-aw/2)+'" y="'+(ay-ah/2)+'" width="'+aw+'" height="'+ah+'" rx="'+size*0.02+'" fill="'+dc+'" opacity=".5"/>';
    out+='<rect x="'+(ax-aw*0.4)+'" y="'+(ay-ah*0.3)+'" width="'+(aw*0.8)+'" height="'+(ah*0.6)+'" rx="'+size*0.01+'" fill="'+mc+'" opacity=".3"/>';
  }else if(s.sup>50){
    const ax=cx,ay=by+bh*0.3,aw=bw*1.3,ah=bh*1.4;
    out+='<path d="M'+(ax-aw/2)+','+ay+' Q'+ax+','+(ay+ah*0.2)+' '+(ax+aw/2)+','+ay+' L'+(ax+aw*0.6)+','+(ay+ah)+' Q'+ax+','+(ay+ah*1.2)+' '+(ax-aw*0.6)+','+(ay+ah)+' Z" fill="'+dc+'" opacity=".4"/>';
    out+='<path d="M'+(ax-aw*0.3)+','+ay+' Q'+ax+','+(ay+ah*0.3)+' '+(ax+aw*0.3)+','+ay+' L'+(ax+aw*0.35)+','+(ay+ah*0.8)+' Q'+ax+','+(ay+ah)+' '+(ax-aw*0.35)+','+(ay+ah*0.8)+' Z" fill="'+mc+'" opacity=".3"/>';
  }else if(s.agi>50){
    const ax=cx,ay=by+bh*0.5,aw=bw*0.9,ah=bh*0.4;
    out+='<rect x="'+(ax-aw/2)+'" y="'+(ay-ah/2)+'" width="'+aw+'" height="'+ah+'" rx="'+size*0.03+'" fill="'+dc+'" opacity=".4"/>';
    const wwy=by+bh*0.3;
    for(let side of[-1,1]){
      const wx=cx+side*(bw*0.5);
      out+='<rect x="'+(wx-size*0.02)+'" y="'+(wwy-size*0.03)+'" width="'+size*0.04+'" height="'+size*0.1+'" fill="'+mc+'" opacity=".5"/>';
    }
  }else{
    const ax=cx,ay=by+bh*0.5,aw=bw,ah=bh*0.5;
    out+='<rect x="'+(ax-aw/2)+'" y="'+(ay-ah/2)+'" width="'+aw+'" height="'+ah+'" rx="'+size*0.02+'" fill="'+dc+'" opacity=".3"/>';
  }
  if(s.stm>60||s.atk>70){
    const spSize=size*0.06,spY=by+bh*0.2;
    for(let side of[-1,1]){
      const spX=cx+side*(bw*0.6);
      out+='<circle cx="'+spX+'" cy="'+spY+'" r="'+spSize+'" fill="'+dc+'" opacity=".6"/>';
      out+='<circle cx="'+spX+'" cy="'+spY+'" r="'+(spSize*0.6)+'" fill="'+mc+'" opacity=".4"/>';
    }
  }
  return out;
}

function drawAccessory(s,dom,sec,cx,cy,bw,bh,by,size,mc,dc,lc,hs,hx,hy,showEquip){
  let out='';
  if(!showEquip)return out;
  if(s.fcs>60){
    const cr=hs*1.1,cy2=hy-hs*0.9;
    out+='<path d="M'+(hx-cr)+','+cy2+' L'+(hx-cr*0.5)+','+(cy2-cr*0.3)+' L'+hx+','+(cy2-cr*0.15)+' L'+(hx+cr*0.5)+','+(cy2-cr*0.3)+' L'+(hx+cr)+','+cy2+' Z" fill="'+MSC['fcs']+'" opacity=".8"/>';
    out+='<circle cx="'+hx+'" cy="'+(cy2-cr*0.2)+'" r="'+size*0.02+'" fill="'+MSL['fcs']+'"/>';
  }
  if(s.sup>50){
    const nx=cx,ny=hy+hs*0.8;
    out+='<circle cx="'+nx+'" cy="'+ny+'" r="'+size*0.025+'" fill="'+MSC['sup']+'" opacity=".9"/>';
    out+='<line x1="'+nx+'" y1="'+(ny-size*0.025)+'" x2="'+nx+'" y2="'+(hy+hs*0.3)+'" stroke="'+MSC['sup']+'" stroke-width="'+size*0.01+'" opacity=".6"/>';
  }
  const tier=getTier(s);
  if(tier.name==='LEGENDARY'||tier.name==='EPIC'){
    const cpx=cx,cpy=by+bh*0.2,cw=bw*1.4,ch=bh*1.8;
    out+='<path d="M'+(cpx-cw*0.3)+','+cpy+' Q'+cpx+','+(cpy+ch*0.1)+' '+(cpx+cw*0.3)+','+cpy+' L'+(cpx+cw*0.5)+','+(cpy+ch)+' Q'+cpx+','+(cpy+ch*1.2)+' '+(cpx-cw*0.5)+','+(cpy+ch)+' Z" fill="'+dc+'" opacity=".3"/>';
    out+='<path d="M'+(cpx-cw*0.2)+','+cpy+' Q'+cpx+','+(cpy+ch*0.15)+' '+(cpx+cw*0.2)+','+cpy+' L'+(cpx+cw*0.3)+','+(cpy+ch*0.7)+' Q'+cpx+','+(cpy+ch*0.85)+' '+(cpx-cw*0.3)+','+(cpy+ch*0.7)+' Z" fill="'+mc+'" opacity=".2"/>';
  }
  return out;
}

function drawMaterial(s,dom,cx,cy,bw,bh,by,size,mc,dc){
  let out='';
  if(s.stm>70){
    const scaleR=size*0.015;
    for(let i=0;i<5;i++){
      const sx=cx+(Math.sin(i*2.5)-0.5)*bw*0.8;
      const sy=by+bh*0.3+(Math.cos(i*1.7))*bh*0.4;
      out+='<circle cx="'+sx+'" cy="'+sy+'" r="'+scaleR+'" fill="'+dc+'" opacity=".3"/>';
    }
  }else if(s.atk>70){
    const furY=by;
    for(let i=0;i<6;i++){
      const fx=cx+(i-2.5)*size*0.04;
      out+='<line x1="'+fx+'" y1="'+furY+'" x2="'+(fx+size*0.02)+'" y2="'+(furY-size*0.06)+'" stroke="'+dc+'" stroke-width="'+size*0.008+'" opacity=".4"/>';
    }
  }else if(s.sup>70){
    for(let i=0;i<4;i++){
      const mx=cx+(Math.sin(i*3.1)-0.5)*bw*1.2;
      const my=by+(Math.cos(i*2.3))*bh*1.2;
      out+='<circle cx="'+mx+'" cy="'+my+'" r="'+size*0.03+'" fill="'+MSC['sup']+'" opacity=".1"/>';
    }
  }
  return out;
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
    return choices[Math.abs(h)%choices.length];
  }
  return choices[0];
}

function selectHead(s,seed){
  let type;
  if(s.fcs>=80)type='alien';
  else if(s.atk>=78)type='angular';
  else if(s.stm>=75)type='skull';
  else if(s.agi>=80)type='mask';
  else if(s.sup>=80)type='crown';
  else if(s.fcs>=55)type='gem';
  else if(s.atk>=48)type='wide';
  else type='round';
  if(!seed)return type;
  const variants={
    alien:['alien','alien-tall','alien-deep'],
    angular:['angular','angular-sharp','angular-broad'],
    skull:['skull','skull-narrow','skull-broad'],
    mask:['mask','mask-narrow','mask-wide'],
    crown:['crown','crown-tall','crown-orbed'],
    gem:['gem','gem-large','gem-faceted'],
    wide:['wide','wide-flat','wide-narrow'],
    round:['round','round-oval','round-flat']
  };
  const rng=nameSeed(seed+'-head');
  const list=variants[type]||[type];
  return list[rng(list.length)];
}

function mAnatomy(s,seed){
  const rng=seed?nameSeed(seed+'-anatomy'):null;
  const pick=(arr)=>rng?arr[rng(arr.length)]:arr[0];
  const headType=selectHead(s,seed);
  return{
    body:selectBody(s,seed),
    head:headType,
    eyes:'generative',
    horns:s.atk>15?pick(['curved','straight','spiral','antler','twisted'])+(s.atk>85?'-4':s.atk>65?'-3':s.atk>38?'-2':'-1'):'none',
    wings:s.agi>38?pick(['feathered','leathery','energy','crystalline'])+'-'+(s.agi>65?'streaked':'basic'):'none',
    aura:s.sup>18?pick(['radiant','pulsing','swirling','stable'])+'-'+(s.sup>60?'intense':s.sup>45?'glowing':'faint'):'none',
    mouth:s.atk>s.sup+15?pick(['fangs','tooth','sharp','beak'])+'-'+(s.atk>72?'aggressive':'mild'):s.sup>52?'smile':'neutral',
    gem:s.fcs>42&&headType.indexOf('gem')===-1?pick(['forehead','chest','shoulder'])+' gem':'none',
    streaks:s.agi>55?Math.floor(s.agi/22)+' '+pick(['speed','lightning','wind','phantom'])+' streaks':'none',
    pattern:s.stm>20?pick(['stripes','spots','gradient','solid','scales']):'solid',
    markings:s.atk>25?pick(['facial scar','eye marks','tribal','none']):'none',
    weapon:s.atk>30?pick(['sword','axe','spear','dagger','mace','staff']):'claws',
    armor:s.stm>35?pick(['plate','chain','robe','hide','scale']):'cloth',
    auraColor:s.sup>20?pick(['gold','silver','blue','purple','green','red']):'none'
  };
}

function drawMonster(svg,s,size,showEquipOrSeed,showTier){
  size=size||120;
  var showEquip=false,useTier=false,seed='';
  if(typeof showEquipOrSeed==='string'){
    seed=showEquipOrSeed;
    showEquip=true;
  }else if(typeof showEquipOrSeed==='boolean'){
    showEquip=showEquipOrSeed;
  }else if(typeof showEquipOrSeed==='object'&&showEquipOrSeed!==null){
    var opts=showEquipOrSeed||{};
    seed=opts.seed||'';
    showEquip=opts.showEquip!==undefined?opts.showEquip:true;
    useTier=opts.showTier!==undefined?opts.showTier:false;
  }
  if(typeof showTier==='boolean')useTier=showTier;

  function nameTint(seed){
    if(!seed)return null;
    const rng=nameSeed(seed+'-tint');
    const r=(rng(80)+175).toString(16).padStart(2,'0');
    const g=(rng(80)+175).toString(16).padStart(2,'0');
    const b=(rng(80)+175).toString(16).padStart(2,'0');
    return '#'+r+g+b;
  }

  var dom=mDom(s),sec=mSec(s);
  var total=mTot(s);
  var bodyScale=0.7+(total/500)*0.3;
  var element=getElement(s);

  var nt=nameTint(seed);
  var mc=tintColor(MSC[dom],element.tint,0.2);
  var sc=tintColor(MSC[sec],element.tint,0.15);
  var dc=tintColor(MSD[dom],element.tint,0.25);
  var lc=tintColor(MSL[dom],element.tint,0.1);

  var stance=getStance(s,size);
  var cx=size/2+stance.ox;
  var cy=size/2+stance.oy;

  var out='<rect width="'+size+'" height="'+size+'" rx="'+(size*0.15)+'" fill="#0d0d18"/>';
  out+=drawTierEffects(s,cx,cy,size,useTier);

  var bw=Math.round(size*0.28*bodyScale*getTier(s).scale);
  var bh=Math.round(size*0.28*bodyScale*getTier(s).scale);
  var bx=cx-bw/2,by=cy-bh/2+size*0.05;

    if(dom==='atk'){
    out+='<polygon points="'+cx+','+(by-bh*0.3)+' '+(bx+bw*1.2)+','+(by+bh*0.4)+' '+(bx+bw)+','+(by+bh*1.3)+' '+bx+','+(by+bh*1.3)+' '+(bx-bw*0.2)+','+(by+bh*0.4)+'" fill="'+dc+'"/>';
    out+='<polygon points="'+cx+','+(by-bh*0.2)+' '+(bx+bw)+','+(by+bh*0.4)+' '+(bx+bw*0.8)+','+(by+bh*1.2)+' '+(bx+bw*0.2)+','+(by+bh*1.2)+' '+bx+','+(by+bh*0.4)+'" fill="'+mc+'"/>';
  }else if(dom==='stm'){
    var r=bw*0.9;
    out+='<circle cx="'+cx+'" cy="'+(by+bh*0.6)+'" r="'+(r*1.1)+'" fill="'+dc+'"/>';
    out+='<circle cx="'+cx+'" cy="'+(by+bh*0.5)+'" r="'+r+'" fill="'+mc+'"/>';
  }else if(dom==='fcs'){
    var hh=bh*0.9;
    out+='<polygon points="'+cx+','+by+' '+(cx+bw)+','+(by+hh*0.5)+' '+(cx+bw*0.7)+','+(by+hh*1.1)+' '+(cx-bw*0.7)+','+(by+hh*1.1)+' '+(cx-bw)+','+(by+hh*0.5)+'" fill="'+dc+'"/>';
    out+='<polygon points="'+cx+','+(by+hh*0.1)+' '+(cx+bw*0.8)+','+(by+hh*0.55)+' '+(cx+bw*0.55)+','+(by+hh)+' '+(cx-bw*0.55)+','+(by+hh)+' '+(cx-bw*0.8)+','+(by+hh*0.55)+'" fill="'+mc+'"/>';
  }else if(dom==='agi'){
    out+='<ellipse cx="'+(cx+size*0.05)+'" cy="'+(by+bh*0.7)+'" rx="'+(bw*1.2)+'" ry="'+(bh*0.7)+'" fill="'+dc+'"/>';
    out+='<ellipse cx="'+cx+'" cy="'+(by+bh*0.6)+'" rx="'+(bw*1.1)+'" ry="'+(bh*0.6)+'" fill="'+mc+'"/>';
  }else{
    out+='<ellipse cx="'+cx+'" cy="'+(by+bh*0.7)+'" rx="'+(bw*0.9)+'" ry="'+(bh*1.1)+'" fill="'+dc+'"/>';
    out+='<ellipse cx="'+cx+'" cy="'+(by+bh*0.6)+'" rx="'+(bw*0.8)+'" ry="'+bh+'" fill="'+mc+'"/>';
  }

  out+=drawArmor(s,dom,sec,cx,cy,bw,bh,by,size,mc,dc,lc,showEquip);
  out+=drawMaterial(s,dom,cx,cy,bw,bh,by,size,mc,dc);

  if(seed&&s.stm>20){
    const patRng=nameSeed(seed+'-pattern');
    const patterns=['stripes','spots','scales','solid'];
    const pattern=patterns[patRng(patterns.length)];
    if(pattern==='stripes'){
      for(let i=0;i<4;i++){
        const sy=by+bh*(0.2+i*0.2);
        out+='<line x1="'+(cx-bw*0.8)+'" y1="'+sy+'" x2="'+(cx+bw*0.8)+'" y2="'+sy+'" stroke="'+dc+'" stroke-width="'+size*0.008+'" opacity=".25" stroke-linecap="round"/>';
      }
    }else if(pattern==='spots'){
      const spots=[{x:0.3,y:0.3},{x:-0.4,y:0.5},{x:0.5,y:0.7},{x:-0.2,y:0.8},{x:0,y:0.55}];
      for(let sp of spots){
        out+='<circle cx="'+(cx+sp.x*bw)+'" cy="'+(by+sp.y*bh)+'" r="'+size*0.025+'" fill="'+dc+'" opacity=".2"/>';
      }
    }else if(pattern==='scales'){
      for(let row=0;row<3;row++){
        for(let col=0;col<4;col++){
          const sx=cx+(col-1.5)*bw*0.35;
          const sy=by+(row+0.5)*bh*0.3;
          out+='<polygon points="'+sx+','+(sy-size*0.015)+' '+(sx+size*0.012)+','+sy+' '+sx+','+(sy+size*0.015)+' '+(sx-size*0.012)+','+sy+'" fill="'+dc+'" opacity=".15"/>';
        }
      }
    }
  }

  // Name-seeded armor overlay (extra chest piece or shoulder pad)
  if(seed&&s.stm>40){
    const armorRng=nameSeed(seed+'-armor');
    const armorStyle=['breastplate','pauldron','girdle','cloak'][armorRng(4)];
    if(armorStyle==='breastplate'){
      out+='<path d="M'+(cx-bw*0.4)+','+(by+bh*0.2)+' Q'+cx+','+(by+bh*0.1)+' '+(cx+bw*0.4)+','+(by+bh*0.2)+' L'+(cx+bw*0.35)+','+(by+bh*0.7)+' Q'+cx+','+(by+bh*0.8)+' '+(cx-bw*0.35)+','+(by+bh*0.7)+' Z" fill="'+dc+'" opacity=".3"/>';
    }else if(armorStyle==='pauldron'){
      for(let side of[-1,1]){
        const px=cx+side*bw*0.6;
        out+='<ellipse cx="'+px+'" cy="'+(by+bh*0.25)+'" rx="'+size*0.04+'" ry="'+size*0.03+'" fill="'+dc+'" opacity=".35"/>';
      }
    }else if(armorStyle==='cloak'){
      out+='<path d="M'+(cx-bw*0.5)+','+(by+bh*0.15)+' Q'+cx+','+(by+bh*0.05)+' '+(cx+bw*0.5)+','+(by+bh*0.15)+' L'+(cx+bw*0.7)+','+(by+bh*1.1)+' L'+(cx-bw*0.7)+','+(by+bh*1.1)+' Z" fill="'+dc+'" opacity=".2"/>';
    }
  }

  // Name-seeded aura enhancement (halo, runes, or energy tendrils)
  if(seed&&s.sup>35){
    const auraRng=nameSeed(seed+'-aura-enhance');
    const aType=['halo','runes','tendrils'][auraRng(3)];
    if(aType==='halo'){
      out+='<ellipse cx="'+hx+'" cy="'+(hy-hs*1.3)+'" rx="'+hs*0.8+'" ry="'+size*0.015+'" fill="none" stroke="'+tintColor(MSC['sup'],element.tint,0.2)+'" stroke-width="'+size*0.008+'" opacity=".6"/>';
    }else if(aType==='runes'){
      for(let i=0;i<3;i++){
        const rx=cx+(i-1)*bw*0.25;
        out+='<rect x="'+(rx-size*0.01)+'" y="'+(by+bh*0.15)+'" width="'+size*0.02+'" height="'+size*0.02+'" rx="'+size*0.005+'" fill="'+MSC['sup']+'" opacity=".3"/>';
      }
    }else if(aType==='tendrils'){
      for(let side of[-1,1]){
        const tx=cx+side*bw*0.6;
        out+='<path d="M'+tx+','+(by+bh*0.3)+' Q'+(tx+side*size*0.05)+','+(by+bh*0.1)+' '+tx+','+(by-bh*0.1)+'" fill="none" stroke="'+MSC['sup']+'" stroke-width="'+size*0.006+'" opacity=".4"/>';
      }
    }
  }

  if(seed&&s.stm>20){
    const patRng=nameSeed(seed+'-pattern');
    const patterns=['stripes','spots','scales','solid'];
    const pattern=patterns[patRng(patterns.length)];
    if(pattern==='stripes'){
      for(let i=0;i<4;i++){
        const sy=by+bh*(0.2+i*0.2);
        out+='<line x1="'+(cx-bw*0.8)+'" y1="'+sy+'" x2="'+(cx+bw*0.8)+'" y2="'+sy+'" stroke="'+dc+'" stroke-width="'+size*0.008+'" opacity=".25" stroke-linecap="round"/>';
      }
    }else if(pattern==='spots'){
      const spots=[{x:0.3,y:0.3},{x:-0.4,y:0.5},{x:0.5,y:0.7},{x:-0.2,y:0.8},{x:0,y:0.55}];
      for(let sp of spots){
        out+='<circle cx="'+(cx+sp.x*bw)+'" cy="'+(by+sp.y*bh)+'" r="'+size*0.025+'" fill="'+dc+'" opacity=".2"/>';
      }
    }else if(pattern==='scales'){
      for(let row=0;row<3;row++){
        for(let col=0;col<4;col++){
          const sx=cx+(col-1.5)*bw*0.35;
          const sy=by+(row+0.5)*bh*0.3;
          out+='<polygon points="'+sx+','+(sy-size*0.015)+' '+(sx+size*0.012)+','+sy+' '+sx+','+(sy+size*0.015)+' '+(sx-size*0.012)+','+sy+'" fill="'+dc+'" opacity=".15"/>';
        }
      }
    }
  }

    var hs=size*(0.18+s.stm/100*0.08)*bodyScale*getTier(s).scale;
  var hx=cx,hy=by-hs*0.3;

  if(s.fcs>70){
    out+='<polygon points="'+hx+','+(hy-hs)+' '+(hx+hs)+','+hy+' '+hx+','+(hy+hs*0.5)+' '+(hx-hs)+','+hy+'" fill="'+dc+'"/>';
    out+='<polygon points="'+hx+','+(hy-hs*0.8)+' '+(hx+hs*0.8)+','+hy+' '+hx+','+(hy+hs*0.35)+' '+(hx-hs*0.8)+','+hy+'" fill="'+mc+'"/>';
  }else if(s.stm>70){
    out+='<circle cx="'+hx+'" cy="'+hy+'" r="'+(hs*1.05)+'" fill="'+dc+'"/>';
    out+='<circle cx="'+hx+'" cy="'+hy+'" r="'+hs+'" fill="'+mc+'"/>';
  }else{
    out+='<ellipse cx="'+hx+'" cy="'+hy+'" rx="'+(hs*0.9)+'" ry="'+hs+'" fill="'+dc+'"/>';
    out+='<ellipse cx="'+hx+'" cy="'+hy+'" rx="'+(hs*0.8)+'" ry="'+(hs*0.9)+'" fill="'+mc+'"/>';
  }

  var er=Math.max(size*0.025,size*0.025+s.fcs/100*size*0.025);
  var ey=hy-hs*0.1;
  var ex=hs*0.35;
  var eyeColor=s.fcs>60?lc:(s.sup>60?tintColor(MSL['sup'],element.tint,0.1):'#ffffff');
  var pupilColor='#000a14';

  if(seed&&s.atk>25){
    const markRng=nameSeed(seed+'-markings');
    const marks=['facial scar','eye marks','tribal'];
    const mark=marks[markRng(marks.length)];
    if(mark==='facial scar'){
      out+='<line x1="'+(hx-hs*0.6)+'" y1="'+(hy-hs*0.2)+'" x2="'+(hx+hs*0.3)+'" y2="'+(hy+hs*0.4)+'" stroke="'+dc+'" stroke-width="'+size*0.015+'" opacity=".4" stroke-linecap="round"/>';
    }else if(mark==='eye marks'){
      for(let side of[-1,1]){
        const exm=hx+side*hs*0.5;
        out+='<path d="M'+(exm-size*0.04)+','+(ey-hs*0.15)+' L'+(exm+size*0.04)+','+(ey-hs*0.15)+' L'+exm+','+(ey+hs*0.05)+' Z" fill="'+dc+'" opacity=".35"/>';
      }
    }else if(mark==='tribal'){
      for(let i=0;i<3;i++){
        const ty=hy-hs*(0.3+i*0.15);
        out+='<line x1="'+(hx-hs*0.7)+'" y1="'+ty+'" x2="'+(hx-hs*0.4)+'" y2="'+ty+'" stroke="'+dc+'" stroke-width="'+size*0.01+'" opacity=".3" stroke-linecap="round"/>';
      }
    }
  }

  if(dom==='fcs'){
    out+='<circle cx="'+hx+'" cy="'+ey+'" r="'+(er*2.5)+'" fill="'+eyeColor+'"/>';
    out+='<ellipse cx="'+hx+'" cy="'+ey+'" rx="'+(er*0.8)+'" ry="'+(er*2)+'" fill="'+pupilColor+'"/>';
    out+='<circle cx="'+(hx-er*0.7)+'" cy="'+(ey-er*0.7)+'" r="'+(er*0.6)+'" fill="#ffffff" opacity=".8"/>';
    for(var i=0;i<8;i++){
      var a=i*Math.PI/4;
      var r0=er*1.2,r1=er*2.3;
      out+='<line x1="'+(hx+Math.cos(a)*r0)+'" y1="'+(ey+Math.sin(a)*r0)+'" x2="'+(hx+Math.cos(a)*r1)+'" y2="'+(ey+Math.sin(a)*r1)+'" stroke="'+dc+'" stroke-width="0.8" opacity=".6"/>';
    }
  }else{
    for(var side2 of[-1,1]){
      var ex2=hx+side2*ex;
      if(s.agi>70){
        out+='<ellipse cx="'+ex2+'" cy="'+ey+'" rx="'+(er*1.6)+'" ry="'+(er*0.8)+'" fill="'+eyeColor+'" transform="rotate('+(side2*-15)+','+ex2+','+ey+')"/>';
        out+='<ellipse cx="'+ex2+'" cy="'+ey+'" rx="'+(er*0.6)+'" ry="'+(er*0.6)+'" fill="'+pupilColor+'"/>';
      }else if(s.sup>70){
        out+='<circle cx="'+ex2+'" cy="'+ey+'" r="'+(er*1.4)+'" fill="'+eyeColor+'"/>';
        out+='<polygon points="'+ex2+','+(ey-er)+' '+(ex2+er*0.35)+','+(ey-er*0.35)+' '+(ex2+er)+','+ey+' '+(ex2+er*0.35)+','+(ey+er*0.35)+' '+ex2+','+(ey+er)+' '+(ex2-er*0.35)+','+(ey+er*0.35)+' '+(ex2-er)+','+ey+' '+(ex2-er*0.35)+','+(ey-er*0.35)+'" fill="'+tintColor(MSL['sup'],element.tint,0.1)+'"/>';
      }else{
        out+='<circle cx="'+ex2+'" cy="'+ey+'" r="'+(er*1.3)+'" fill="'+eyeColor+'"/>';
        out+='<circle cx="'+ex2+'" cy="'+ey+'" r="'+(er*0.7)+'" fill="'+pupilColor+'"/>';
        out+='<circle cx="'+(ex2-er*0.3)+'" cy="'+(ey-er*0.3)+'" r="'+(er*0.35)+'" fill="#ffffff" opacity=".7"/>';
      }
    }
  }

    if(s.atk>20){
    var hornH=size*(0.04+s.atk/100*0.1);
    var hornW=size*0.04;
    var hBase=hy-hs*0.75;
    var hCount=s.atk>75?3:s.atk>45?2:1;
    var hPositions=hCount===1?[0]:hCount===2?[-1,1]:[-1.5,0,1.5];
    var hornStyle='curved';
    if(seed){
      const hornStyles=['curved','straight','spiral','antler','twisted'];
      hornStyle=hornStyles[nameSeed(seed+'-horn')(hornStyles.length)];
    }
    for(var p of hPositions){
      var hpx=hx+p*hs*0.45;
      var lean=p*0.25;
      if(hornStyle==='spiral'){
        out+='<path d="M'+(hpx-hornW)+','+hBase+' L'+(hpx+hornW)+','+hBase+' Q'+(hpx+lean*hornH*0.5)+','+(hBase-hornH*0.5)+' '+(hpx+lean*hornH)+','+(hBase-hornH)+' Q'+(hpx-lean*hornH*0.3)+','+(hBase-hornH*0.7)+' '+(hpx)+','+(hBase-hornH*0.85)+' Z" fill="'+dc+'"/>';
      }else if(hornStyle==='antler'){
        out+='<line x1="'+hpx+'" y1="'+hBase+'" x2="'+(hpx+lean*hornH)+'" y2="'+(hBase-hornH)+'" stroke="'+dc+'" stroke-width="'+hornW+'" stroke-linecap="round"/>';
        out+='<line x1="'+(hpx+lean*hornH)+'" y1="'+(hBase-hornH)+'" x2="'+(hpx+lean*hornH*0.7)+'" y2="'+(hBase-hornH*0.6)+'" stroke="'+dc+'" stroke-width="'+(hornW*0.6)+'" stroke-linecap="round"/>';
      }else if(hornStyle==='twisted'){
        for(var t=0;t<3;t++){
          var tx=hpx+(lean*hornH*(t/2));
          var ty=hBase-(hornH*(t/2));
          out+='<polygon points="'+(tx-hornW*0.8)+','+ty+' '+(tx+hornW*0.8)+','+ty+' '+(tx+lean*hornH*0.4)+','+(ty-hornH*0.4)+'" fill="'+dc+'"/>';
        }
      }else{
        out+='<polygon points="'+(hpx-hornW)+','+hBase+' '+(hpx+hornW)+','+hBase+' '+(hpx+lean*hornH)+','+(hBase-hornH)+'" fill="'+dc+'"/>';
        out+='<polygon points="'+(hpx-hornW*0.5)+','+hBase+' '+(hpx+hornW*0.5)+','+hBase+' '+(hpx+lean*hornH*0.7)+','+(hBase-hornH*0.75)+'" fill="'+lc+'" opacity=".5"/>';
      }
    }
  }else{
    var earH=size*0.07;
    for(var side3 of[-1,1]){
      var epx=hx+side3*hs*0.8;
      out+='<polygon points="'+(epx-size*0.04)+','+(hy-hs*0.5)+' '+(epx+size*0.04)+','+(hy-hs*0.5)+' '+(epx+side3*size*0.02)+','+(hy-hs*0.5-earH)+'" fill="'+mc+'"/>';
    }
  }

    if(s.agi>40){
    var wingW=size*(0.1+s.agi/100*0.18);
    var wingH=size*(0.08+s.agi/100*0.1);
    var wy=by+bh*0.3;
    for(var side4 of[-1,1]){
      var wx=cx+side4*(bw*0.5);
      out+='<polygon points="'+wx+','+wy+' '+(wx+side4*wingW)+','+(wy-wingH*0.6)+' '+(wx+side4*wingW*0.7)+','+(wy+wingH)+'" fill="'+dc+'" opacity=".9"/>';
      out+='<polygon points="'+wx+','+wy+' '+(wx+side4*wingW*0.8)+','+(wy-wingH*0.4)+' '+(wx+side4*wingW*0.55)+','+(wy+wingH*0.8)+'" fill="'+sc+'" opacity=".5"/>';
    }
  }else{
    var aw=size*0.08,ah=size*0.05;
    for(var side5 of[-1,1]){
      var ax=cx+side5*(bw*0.55);
      out+='<rect x="'+(ax-aw/2)+'" y="'+(by+bh*0.3)+'" width="'+aw+'" height="'+ah+'" rx="'+(ah/2)+'" fill="'+dc+'"/>';
    }
  }

    if(s.stm>30){
    var tw=size*0.05,tl=size*(0.1+s.stm/100*0.14);
    var tx=cx,ty=by+bh*1.1;
    if(s.stm>70){
      out+='<polygon points="'+(tx-tw)+','+ty+' '+(tx+tw)+','+ty+' '+(tx+tw*0.5)+','+(ty+tl)+' '+(tx-tw*0.5)+','+(ty+tl)+'" fill="'+dc+'"/>';
      out+='<polygon points="'+tx+','+(ty+tl*0.6)+' '+(tx+tw*1.8)+','+(ty+tl*0.3)+' '+(tx+tw*0.3)+','+(ty+tl)+'" fill="'+mc+'" opacity=".7"/>';
      out+='<polygon points="'+tx+','+(ty+tl*0.6)+' '+(tx-tw*1.8)+','+(ty+tl*0.3)+' '+(tx-tw*0.3)+','+(ty+tl)+'" fill="'+mc+'" opacity=".7"/>';
    }else{
      out+='<ellipse cx="'+tx+'" cy="'+(ty+tl*0.5)+'" rx="'+(tw*0.8)+'" ry="'+(tl*0.5)+'" fill="'+dc+'" opacity=".7"/>';
    }
  }

    if(s.sup>20){
    var aura=s.sup/100;
    out+='<circle cx="'+cx+'" cy="'+cy+'" r="'+size*0.44+'" fill="none" stroke="'+tintColor(MSC['sup'],element.tint,0.1)+'" stroke-width="'+(1+aura*3)+'" opacity="'+(0.1+aura*0.3)+'"/>';
    if(s.sup>50){
      out+='<circle cx="'+cx+'" cy="'+cy+'" r="'+size*0.47+'" fill="none" stroke="'+tintColor(MSL['sup'],element.tint,0.1)+'" stroke-width="'+(0.5+aura)+'" opacity="'+(aura*0.2)+'"/>';
    }
    var nSparkles=Math.floor(s.sup/25);
    for(var i2=0;i2<nSparkles;i2++){
      var a2=(i2/nSparkles)*Math.PI*2+0.5;
      var sr2=size*0.42;
      out+='<circle cx="'+(cx+Math.cos(a2)*sr2)+'" cy="'+(cy+Math.sin(a2)*sr2)+'" r="'+size*0.018+'" fill="'+tintColor(MSL['sup'],element.tint,0.1)+'" opacity=".8"/>';
    }
  }

    var mouthY=hy+hs*0.55;
  if(s.atk>s.sup+20){
    var mw=hs*0.55;
    out+='<path d="M'+(hx-mw)+','+mouthY+' Q'+hx+','+(mouthY+hs*0.3)+' '+(hx+mw)+','+mouthY+'" fill="none" stroke="'+dc+'" stroke-width="'+size*0.025+'" stroke-linecap="round"/>';
    out+='<polygon points="'+(hx-mw*0.4)+','+mouthY+' '+(hx-mw*0.2)+','+mouthY+' '+(hx-mw*0.3)+','+(mouthY+hs*0.22)+'" fill="#ffffff" opacity=".8"/>';
    out+='<polygon points="'+(hx+mw*0.2)+','+mouthY+' '+(hx+mw*0.4)+','+mouthY+' '+(hx+mw*0.3)+','+(mouthY+hs*0.22)+'" fill="#ffffff" opacity=".8"/>';
  }else if(s.sup>50){
    var mw=hs*0.4;
    out+='<path d="M'+(hx-mw)+','+mouthY+' Q'+hx+','+(mouthY+hs*0.35)+' '+(hx+mw)+','+mouthY+'" fill="none" stroke="'+lc+'" stroke-width="'+size*0.02+'" stroke-linecap="round"/>';
  }else{
    var mw=hs*0.3;
    out+='<line x1="'+(hx-mw)+'" y1="'+(mouthY+hs*0.05)+'" x2="'+(hx+mw)+'" y2="'+(mouthY+hs*0.05)+'" stroke="'+lc+'" stroke-width="'+size*0.02+'" stroke-linecap="round"/>';
  }

    if(s.fcs>50&&dom!=='fcs'){
    var gr=size*0.03;
    out+='<polygon points="'+hx+','+(hy-hs*0.85)+' '+(hx+gr)+','+(hy-hs*0.65)+' '+hx+','+(hy-hs*0.55)+' '+(hx-gr)+','+(hy-hs*0.65)+'" fill="'+tintColor(MSC['fcs'],element.tint,0.1)+'" opacity=".9"/>';
  }

  out+=drawAccessory(s,dom,sec,cx,cy,bw,bh,by,size,mc,dc,lc,hs,hx,hy,showEquip);
  out+=drawWeapon(s,dom,sec,cx,cy,bw,bh,by,size,mc,dc,lc,showEquip,seed);

  svg.innerHTML=out;
}

function buildMonsterWidget(s,size,seed){
  const arc=mArchetype(s),name=mName(s),trs=mTraits(s);
  const wrap=document.createElement('div');
  wrap.className='monster-widget';
  wrap.style.cssText='position:relative;flex-shrink:0;cursor:default;display:inline-block';

  const svgNS='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(svgNS,'svg');
  svg.setAttribute('width',size);svg.setAttribute('height',size);
  svg.setAttribute('viewBox','0 0 '+size+' '+size);
  drawMonster(svg,s,size,seed);

  const tip=document.createElement('div');
  tip.className='monster-tip';
  tip.style.cssText='position:absolute;bottom:calc(100% + 7px);left:50%;transform:translateX(-50%);background:#12121a;border:1px solid #2a2a3e;border-radius:10px;padding:9px 13px;font-size:11px;font-family:monospace;white-space:nowrap;pointer-events:none;opacity:0;transition:opacity .18s;z-index:9999;text-align:center;min-width:140px';
  const tHtml=trs.map(t=>'<span style="display:inline-block;font-size:9px;padding:1px 6px;border-radius:6px;margin:1px;background:'+t.c+'22;color:'+t.c+';border:1px solid '+t.c+'44">'+t.t+'</span>').join('');
  const anatomy=mAnatomy(s,seed);
  const aHtml=Object.entries(anatomy).map(([k,v])=>'<span style="display:inline-block;font-size:8px;padding:1px 5px;border-radius:4px;margin:1px;background:#222233;color:#88aabb">'+k+':'+v+'</span>').join('');
  tip.innerHTML='<div style="font-size:13px;font-weight:800;letter-spacing:1.5px;color:'+arc.c+';margin-bottom:2px">'+name+'</div>'+
                '<div style="font-size:10px;opacity:.82;color:'+arc.c+';margin-bottom:5px">'+arc.l+'</div>'+
                '<div>'+tHtml+'</div>'+
                '<div style="margin-top:4px;border-top:1px solid #2a2a3e;padding-top:4px">'+aHtml+'</div>';

  wrap.appendChild(svg);
  wrap.appendChild(tip);
  wrap.addEventListener('mouseenter',function(){tip.style.opacity='1';});
  wrap.addEventListener('mouseleave',function(){tip.style.opacity='0';});
  return wrap;
}
