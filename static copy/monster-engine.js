const MSTAT_COLORS = {atk:'#ff4444', stm:'#00e676', fcs:'#ffd600', agi:'#00e5ff', sup:'#a855f7'};
const MSTAT_DARK   = {atk:'#cc1111', stm:'#009944', fcs:'#cc9900', agi:'#0099bb', sup:'#6622aa'};
const MSTAT_LIGHT  = {atk:'#ff9999', stm:'#88ffcc', fcs:'#ffee88', agi:'#88eeff', sup:'#cc88ff'};
const MNAMES_A = ['BLA','VER','LUM','ZEP','AET','KRO','PHO','TOR','MYS','NUL','GLA','OBL','PYR','SOL','NEB'];
const MNAMES_B = ['ZOR','DAX','NOS','IXX','MUS','KAR','PHX','VEX','RAX','THO','GON','WYN','SYX','RUL','ORM'];

function mGetName(stats) {
  const dom = mGetDominant(stats);
  const idx = Math.floor(stats[dom] / 7) % MNAMES_A.length;
  const idx2 = Math.floor((stats.atk + stats.stm) / 13) % MNAMES_B.length;
  return MNAMES_A[idx] + MNAMES_B[idx2];
}
function mGetDominant(s) { return Object.entries(s).sort((a,b)=>b[1]-a[1])[0][0]; }
function mGetSecondary(s) { return Object.entries(s).sort((a,b)=>b[1]-a[1])[1][0]; }
function mGetTotal(s) { return Object.values(s).reduce((a,b)=>a+b,0); }

let _CURRENT_SEED = '';
function mSetSeed(seed) { _CURRENT_SEED = seed || ''; }
function mClearSeed() { _CURRENT_SEED = ''; }
function mHash() {
  if (!_CURRENT_SEED) return 0;
  let h = 0;
  for (let i = 0; i < _CURRENT_SEED.length; i++) h = ((h << 5) - h) + _CURRENT_SEED.charCodeAt(i) | 0;
  return Math.abs(h);
}
function mSeededPick(items, offset) {
  if (!_CURRENT_SEED || items.length <= 1) return items[0];
  const idx = Math.abs((mHash() + (offset || 0) * 137)) % items.length;
  return items[idx];
}

const BODY_DEFS = {
  dragon:   {dom:['atk','agi'], sec:['atk','agi','fcs']},
  slime:    {dom:['stm','sup'], sec:['stm','sup','fcs']},
  mech:     {dom:['stm','fcs'], sec:['stm','fcs','atk']},
  serpent:  {dom:['agi','stm'], sec:['agi','stm','fcs']},
  insect:   {dom:['agi','fcs'], sec:['agi','fcs','atk']},
  phantom:  {dom:['fcs','agi'], sec:['fcs','agi','sup']},
  golem:    {dom:['stm','atk'], sec:['stm','atk','fcs']},
  phoenix:  {dom:['atk','sup'], sec:['atk','sup','agi']},
  crystal:  {dom:['fcs','stm'], sec:['fcs','stm','sup']},
  tentacle: {dom:['sup','fcs'], sec:['sup','fcs','agi']},
  chimera:  {dom:['atk','fcs'], sec:['atk','fcs','sup']},
  wraith:   {dom:['sup','agi'], sec:['sup','agi','stm']}
};

function selectBody(s) {
  const dom = mGetDominant(s), sec = mGetSecondary(s);
  const possible = [];
  for (const [type, def] of Object.entries(BODY_DEFS)) {
    if (def.dom.includes(dom) && def.sec.includes(sec)) possible.push(type);
  }
  if (possible.length > 0) return mSeededPick(possible, 0);
  if (s.atk >= s.stm && s.atk >= s.fcs && s.atk >= s.agi && s.atk >= s.sup) return 'dragon';
  if (s.stm >= s.atk && s.stm >= s.fcs && s.stm >= s.agi && s.stm >= s.sup) return 'golem';
  if (s.fcs >= s.atk && s.fcs >= s.stm && s.fcs >= s.agi && s.fcs >= s.sup) return 'phantom';
  if (s.agi >= s.atk && s.agi >= s.stm && s.agi >= s.fcs && s.agi >= s.sup) return 'serpent';
  return 'wraith';
}

const HEAD_DEFS = [
  {id:'alien',  check: (s)=>s.fcs >= 80},
  {id:'angular',check: (s)=>s.atk >= 80},
  {id:'skull',  check: (s)=>s.stm >= 80},
  {id:'beak',   check: (s)=>s.agi >= 80},
  {id:'crown',  check: (s)=>s.sup >= 80},
  {id:'gem',    check: (s)=>s.fcs >= 50},
  {id:'beast',  check: (s)=>s.atk >= 50},
  {id:'default',check: (s)=>true}
];

function selectHead(s) {
  for (const h of HEAD_DEFS) if (h.check(s)) return h.id;
  return 'default';
}

const EYE_DEFS = [
  {id:'cyclopean', check: (s,dom)=>dom === 'fcs'},
  {id:'slit',      check: (s,dom)=>s.agi >= 70},
  {id:'star',      check: (s,dom)=>s.sup >= 70},
  {id:'hollow',    check: (s,dom)=>s.stm >= 70},
  {id:'insect',    check: (s,dom)=>s.fcs >= 50 && s.agi >= 50},
  {id:'round',     check: (s,dom)=>true}
];

function selectEyes(s) {
  const dom = mGetDominant(s);
  for (const e of EYE_DEFS) if (e.check(s, dom)) return e.id;
  return 'round';
}

const ARCHETYPES = {
  atk:{stm:'BERSERKER', fcs:'ASSASSIN', agi:'STRIKER', sup:'WARLORD', atk:'DESTROYER'},
  stm:{atk:'TANK', fcs:'SENTINEL', agi:'IRONFOOT', sup:'GUARDIAN', stm:'FORTRESS'},
  fcs:{atk:'SNIPER', stm:'SCHOLAR', agi:'PHANTOM', sup:'ORACLE', fcs:'ENLIGHTENED'},
  agi:{atk:'DUELIST', stm:'RUNNER', fcs:'TRICKSTER', sup:'HERALD', agi:'BLUR'},
  sup:{atk:'PALADIN', stm:'MENDER', fcs:'PROPHET', agi:'BARD', sup:'ASCENDANT'}
};

const SPECIAL_ARCHETYPES = [
  {label:'ALLROUNDER',     color:'#ffffff', check: (s)=>Object.values(s).every(v=>v>30&&v<80) && mGetTotal(s)>200},
  {label:'LEGENDARY',      color:'#ffd700', check: (s)=>mGetTotal(s) >= 400},
  {label:'DRAGON LORD',    color:'#ff4500', check: (s)=>selectBody(s)==='dragon' && mGetDominant(s)==='atk'},
  {label:'MECH TITAN',     color:'#a0a0b0', check: (s)=>selectBody(s)==='mech' && mGetDominant(s)==='stm'},
  {label:'SLIME KING',     color:'#00ffaa', check: (s)=>selectBody(s)==='slime' && mGetDominant(s)==='stm'},
  {label:'SERPENT MASTER', color:'#00ddee', check: (s)=>selectBody(s)==='serpent' && mGetDominant(s)==='agi'},
  {label:'INSECT LORD',    color:'#88ff00', check: (s)=>selectBody(s)==='insect' && s.fcs>60},
  {label:'PHANTOM WALKER', color:'#cc88ff', check: (s)=>selectBody(s)==='phantom' && mGetDominant(s)==='fcs'},
  {label:'GOLEM CRUSHER',  color:'#777777', check: (s)=>selectBody(s)==='golem' && s.atk>60},
  {label:'PHOENIX RISEN',  color:'#ff6a00', check: (s)=>selectBody(s)==='phoenix' && s.sup>60},
  {label:'CRYSTAL SAGE',   color:'#00ffef', check: (s)=>selectBody(s)==='crystal' && mGetDominant(s)==='fcs'},
  {label:'TENTACLE SUMMONER',color:'#ff00cc',check: (s)=>selectBody(s)==='tentacle' && s.sup>60},
  {label:'CHIMERA BEAST',  color:'#ff2200', check: (s)=>selectBody(s)==='chimera' && s.atk>70},
  {label:'WRAITH KING',    color:'#6666ff', check: (s)=>selectBody(s)==='wraith' && mGetDominant(s)==='sup'},
  {label:'UNSTOPPABLE',    color:'#ff1111', check: (s)=>s.atk>=95},
  {label:'IMMORTAL',       color:'#00e676', check: (s)=>s.stm>=95},
  {label:'ALL-SEEING',     color:'#ffd600', check: (s)=>s.fcs>=95},
  {label:'LIGHTNING',      color:'#00e5ff', check: (s)=>s.agi>=95},
  {label:'DIVINE',         color:'#a855f7', check: (s)=>s.sup>=95},
  {label:'FLEDGLING',      color:'#8888aa', check: (s)=>mGetTotal(s) < 80},
  {label:'MYTHIC',         color:'#ff55ff', check: (s)=>mGetTotal(s) >= 350 && mGetTotal(s) < 400},
  {label:'VOID WALKER',    color:'#4400ff', check: (s)=>s.fcs>80 && s.agi>80},
  {label:'IRON GOD',       color:'#ffaa00', check: (s)=>s.atk>80 && s.stm>80},
  {label:'SHADOW',         color:'#333355', check: (s)=>s.fcs<20 && s.agi<20 && s.sup<20},
  {label:'BALANCE KEEPER', color:'#ffffff', check: (s)=>{
    const vals=Object.values(s); const max=Math.max(...vals), min=Math.min(...vals);
    return max-min <= 15 && mGetTotal(s) >= 150;
  }}
];

function mGetArchetype(s) {
  for (const spec of SPECIAL_ARCHETYPES) {
    if (spec.check(s)) return {label: spec.label, color: spec.color};
  }
  const dom = mGetDominant(s), sec = mGetSecondary(s);
  const base = ARCHETYPES[dom]?.[sec] || 'WANDERER';
  return {label: base, color: MSTAT_COLORS[dom]};
}

function mGetTraits(s) {
  const traits = [];
  if (s.atk > 80) traits.push({t:'RAGING', c:'#ff4444'});
  if (s.atk > 60) traits.push({t:'FIERCE', c:'#ff6666'});
  if (s.stm > 80) traits.push({t:'IMMORTAL', c:'#00e676'});
  if (s.stm > 60) traits.push({t:'STURDY', c:'#44dd88'});
  if (s.fcs > 80) traits.push({t:'ALLSEEING', c:'#ffd600'});
  if (s.fcs > 60) traits.push({t:'SHARP', c:'#ddcc00'});
  if (s.agi > 80) traits.push({t:'HYPERSPEED', c:'#00e5ff'});
  if (s.agi > 60) traits.push({t:'NIMBLE', c:'#44ddff'});
  if (s.sup > 80) traits.push({t:'DIVINE', c:'#a855f7'});
  if (s.sup > 60) traits.push({t:'BLESSED', c:'#cc88ff'});
  if (mGetTotal(s) > 350) traits.push({t:'LEGENDARY', c:'#ffd700'});
  if (Object.values(s).some(v=>v<10)) traits.push({t:'CURSED', c:'#666688'});
  return traits.slice(0,4);
}

function drawBody(type, cx, cy, size, scale, dc, mc) {
  const bx = cx, by = cy + size * 0.08;
  const bw = Math.round(size * 0.28 * scale);
  const bh = Math.round(size * 0.28 * scale);
  let out = '';
  switch(type) {
    case 'dragon':
      out += `<polygon points="${bx},${by-bh*0.35} ${bx+bw*1.3},${by+bh*0.35} ${bx+bw},${by+bh*1.35} ${bx-bw},${by+bh*1.35} ${bx-bw*1.3},${by+bh*0.35}" fill="${dc}"/>`;
      out += `<polygon points="${bx},${by-bh*0.25} ${bx+bw*1.1},${by+bh*0.45} ${bx+bw*0.8},${by+bh*1.25} ${bx-bw*0.8},${by+bh*1.25} ${bx-bw*1.1},${by+bh*0.45}" fill="${mc}"/>`;
      break;
    case 'slime':
      out += `<ellipse cx="${bx}" cy="${by+bh*0.7}" rx="${bw*1.1}" ry="${bh*1.15}" fill="${dc}"/>`;
      out += `<ellipse cx="${bx}" cy="${by+bh*0.6}" rx="${bw}" ry="${bh}" fill="${mc}"/>`;
      out += `<ellipse cx="${bx+bw*0.3}" cy="${by+bh*1.2}" rx="${bw*0.25}" ry="${bh*0.2}" fill="${dc}"/>`;
      break;
    case 'mech':
      out += `<rect x="${bx-bw}" y="${by}" width="${bw*2}" height="${bh*1.2}" rx="${bw*0.15}" fill="${dc}"/>`;
      out += `<rect x="${bx-bw*0.85}" y="${by+bh*0.1}" width="${bw*1.7}" height="${bh*0.9}" rx="${bw*0.1}" fill="${mc}"/>`;
      out += `<line x1="${bx-bw}" y1="${by+bh*0.4}" x2="${bx+bw}" y2="${by+bh*0.4}" stroke="${dc}" stroke-width="${size*0.02}"/>`;
      break;
    case 'serpent':
      out += `<path d="M${bx-bw},${by+bh*1.2} Q${bx-bw*0.5},${by-bh*0.2} ${bx},${by+bh*0.6} Q${bx+bw*0.5},${by+bh*1.4} ${bx+bw},${by-bh*0.1}" fill="none" stroke="${dc}" stroke-width="${bh*0.5}" stroke-linecap="round"/>`;
      out += `<path d="M${bx-bw*0.85},${by+bh*1.15} Q${bx-bw*0.4},${by-bh*0.05} ${bx},${by+bh*0.55} Q${bx+bw*0.4},${by+bh*1.35} ${bx+bw*0.85},${by-bh*0.05}" fill="none" stroke="${mc}" stroke-width="${bh*0.35}" stroke-linecap="round"/>`;
      break;
    case 'insect':
      out += `<polygon points="${bx},${by-bh*0.2} ${bx+bw},${by+bh*0.3} ${bx+bw*0.8},${by+bh*1.2} ${bx-bw*0.8},${by+bh*1.2} ${bx-bw},${by+bh*0.3}" fill="${dc}"/>`;
      out += `<line x1="${bx-bw*1.1}" y1="${by+bh*0.3}" x2="${bx-bw*0.9}" y2="${by+bh*0.7}" stroke="${dc}" stroke-width="${size*0.02}"/>`;
      out += `<line x1="${bx+bw*1.1}" y1="${by+bh*0.3}" x2="${bx+bw*0.9}" y2="${by+bh*0.7}" stroke="${dc}" stroke-width="${size*0.02}"/>`;
      break;
    case 'phantom':
      out += `<ellipse cx="${bx}" cy="${by+bh*0.6}" rx="${bw*0.9}" ry="${bh*1.1}" fill="${dc}" opacity=".6"/>`;
      out += `<ellipse cx="${bx}" cy="${by+bh*0.55}" rx="${bw*0.8}" ry="${bh}" fill="${mc}" opacity=".85"/>`;
      break;
    case 'golem':
      out += `<rect x="${bx-bw*1.05}" y="${by-bh*0.1}" width="${bw*2.1}" height="${bh*1.3}" rx="${bw*0.08}" fill="${dc}"/>`;
      out += `<rect x="${bx-bw*0.9}" y="${by}" width="${bw*1.8}" height="${bh*1.1}" rx="${bw*0.06}" fill="${mc}"/>`;
      out += `<rect x="${bx-bw*0.3}" y="${by+bh*1.0}" width="${bw*0.6}" height="${bh*0.3}" rx="${bw*0.05}" fill="${dc}"/>`;
      break;
    case 'phoenix':
      out += `<ellipse cx="${bx}" cy="${by+bh*0.6}" rx="${bw}" ry="${bh*0.8}" fill="${dc}"/>`;
      out += `<ellipse cx="${bx}" cy="${by+bh*0.5}" rx="${bw*0.85}" ry="${bh*0.65}" fill="${mc}"/>`;
      out += `<polygon points="${bx-bw},${by+bh*0.8} ${bx-bw*1.4},${by+bh*0.2} ${bx-bw*0.8},${by+bh*0.5}" fill="${dc}" opacity=".7"/>`;
      out += `<polygon points="${bx+bw},${by+bh*0.8} ${bx+bw*1.4},${by+bh*0.2} ${bx+bw*0.8},${by+bh*0.5}" fill="${dc}" opacity=".7"/>`;
      break;
    case 'crystal':
      out += `<polygon points="${bx},${by} ${bx+bw},${by+bh*0.5} ${bx+bw*0.6},${by+bh*1.2} ${bx-bw*0.6},${by+bh*1.2} ${bx-bw},${by+bh*0.5}" fill="${dc}"/>`;
      out += `<polygon points="${bx},${by+bh*0.2} ${bx+bw*0.75},${by+bh*0.55} ${bx+bw*0.45},${by+bh*1.05} ${bx-bw*0.45},${by+bh*1.05} ${bx-bw*0.75},${by+bh*0.55}" fill="${mc}"/>`;
      break;
    case 'tentacle':
      out += `<ellipse cx="${bx}" cy="${by+bh*0.7}" rx="${bw*0.75}" ry="${bh*1.1}" fill="${dc}"/>`;
      out += `<ellipse cx="${bx}" cy="${by+bh*0.6}" rx="${bw*0.65}" ry="${bh}" fill="${mc}"/>`;
      for(let ti=0; ti<3; ti++) {
        const tx = bx + (ti-1)*bw*0.45;
        out += `<ellipse cx="${tx}" cy="${by+bh*1.25}" rx="${bw*0.15}" ry="${bh*0.28}" fill="${dc}" opacity=".8"/>`;
      }
      break;
    case 'chimera':
      out += `<polygon points="${bx},${by-bh*0.25} ${bx+bw*1.15},${by+bh*0.4} ${bx+bw*0.85},${by+bh*1.25} ${bx-bw*0.85},${by+bh*1.25} ${bx-bw*1.15},${by+bh*0.4}" fill="${dc}"/>`;
      out += `<polygon points="${bx},${by-bh*0.1} ${bx+bw*0.95},${by+bh*0.45} ${bx+bw*0.75},${by+bh*1.1} ${bx-bw*0.75},${by+bh*1.1} ${bx-bw*0.95},${by+bh*0.45}" fill="${mc}"/>`;
      out += `<circle cx="${bx-bw*0.5}" cy="${by+bh*0.3}" r="${bw*0.22}" fill="${dc}"/>`;
      out += `<circle cx="${bx+bw*0.45}" cy="${by+bh*0.35}" r="${bw*0.18}" fill="${dc}"/>`;
      break;
    default:
      out += `<ellipse cx="${bx}" cy="${by+bh*0.65}" rx="${bw*0.8}" ry="${bh*1.15}" fill="${dc}"/>`;
      out += `<ellipse cx="${bx}" cy="${by+bh*0.55}" rx="${bw*0.7}" ry="${bh}" fill="${mc}"/>`;
      out += `<ellipse cx="${bx}" cy="${by+bh*1.15}" rx="${bw*0.2}" ry="${bh*0.15}" fill="${dc}" opacity=".4"/>`;
  }
  return out;
}

function drawHead(type, hx, hy, hs, dc, mc, s) {
  let out = '';
  switch(type) {
    case 'alien':
      out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.75}" ry="${hs*1.15}" fill="${dc}"/>`;
      out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.65}" ry="${hs*1.0}" fill="${mc}"/>`;
      break;
    case 'angular':
      out += `<polygon points="${hx},${hy-hs} ${hx+hs},${hy} ${hx+hs*0.5},${hy+hs*0.6} ${hx-hs*0.5},${hy+hs*0.6} ${hx-hs},${hy}" fill="${dc}"/>`;
      out += `<polygon points="${hx},${hy-hs*0.8} ${hx+hs*0.85},${hy} ${hx+hs*0.4},${hy+hs*0.45} ${hx-hs*0.4},${hy+hs*0.45} ${hx-hs*0.85},${hy}" fill="${mc}"/>`;
      break;
    case 'skull':
      out += `<circle cx="${hx}" cy="${hy}" r="${hs*1.05}" fill="${dc}"/>`;
      out += `<circle cx="${hx}" cy="${hy}" r="${hs}" fill="${mc}"/>`;
      out += `<polygon points="${hx-hs*0.5},${hy+hs*0.2} ${hx+hs*0.5},${hy+hs*0.2} ${hx+hs*0.35},${hy+hs*0.65} ${hx-hs*0.35},${hy+hs*0.65}" fill="${dc}" opacity=".6"/>`;
      break;
    case 'beak':
      out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.9}" ry="${hs}" fill="${dc}"/>`;
      out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.8}" ry="${hs*0.9}" fill="${mc}"/>`;
      out += `<polygon points="${hx},${hy+hs*0.3} ${hx+hs*0.15},${hy+hs*0.7} ${hx-hs*0.15},${hy+hs*0.7}" fill="${dc}"/>`;
      break;
    case 'crown':
      out += `<circle cx="${hx}" cy="${hy}" r="${hs*1.05}" fill="${dc}"/>`;
      out += `<circle cx="${hx}" cy="${hy}" r="${hs}" fill="${mc}"/>`;
      out += `<polygon points="${hx-hs*0.6},${hy-hs} ${hx-hs*0.4},${hy-hs*0.55} ${hx-hs*0.15},${hy-hs*0.85} ${hx},${hy-hs*0.5} ${hx+hs*0.15},${hy-hs*0.85} ${hx+hs*0.4},${hy-hs*0.55} ${hx+hs*0.6},${hy-hs}" fill="${dc}"/>`;
      break;
    case 'gem':
      out += `<polygon points="${hx},${hy-hs*0.9} ${hx+hs*0.8},${hy} ${hx+hs*0.5},${hy+hs*0.55} ${hx-hs*0.5},${hy+hs*0.55} ${hx-hs*0.8},${hy}" fill="${dc}"/>`;
      out += `<polygon points="${hx},${hy-hs*0.7} ${hx+hs*0.65},${hy} ${hx+hs*0.4},${hy+hs*0.4} ${hx-hs*0.4},${hy+hs*0.4} ${hx-hs*0.65},${hy}" fill="${mc}"/>`;
      break;
    case 'beast':
      out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.95}" ry="${hs*0.85}" fill="${dc}"/>`;
      out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.85}" ry="${hs*0.75}" fill="${mc}"/>`;
      out += `<ellipse cx="${hx}" cy="${hy+hs*0.25}" rx="${hs*0.35}" ry="${hs*0.22}" fill="${dc}" opacity=".5"/>`;
      break;
    default:
      out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.9}" ry="${hs}" fill="${dc}"/>`;
      out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.8}" ry="${hs*0.9}" fill="${mc}"/>`;
  }
  return out;
}

function drawEyes(type, hx, hy, hs, eyeColor, pupilColor, s) {
  let out = '';
  const er = Math.max(hs*0.18, hs*0.12 + s.fcs/100*hs*0.12);
  switch(type) {
    case 'cyclopean':
      out += `<circle cx="${hx}" cy="${hy-hs*0.05}" r="${er*2.2}" fill="${eyeColor}"/>`;
      out += `<ellipse cx="${hx}" cy="${hy-hs*0.05}" rx="${er*0.7}" ry="${er*1.8}" fill="${pupilColor}"/>`;
      out += `<circle cx="${hx-er*0.6}" cy="${hy-hs*0.05-er*0.6}" r="${er*0.5}" fill="#ffffff" opacity=".8"/>`;
      break;
    case 'slit':
      for(const side of [-1,1]) {
        const ex2 = hx + side*hs*0.32;
        out += `<ellipse cx="${ex2}" cy="${hy-hs*0.05}" rx="${er*1.5}" ry="${er*0.65}" fill="${eyeColor}" transform="rotate(${side*-12},${ex2},${hy-hs*0.05})"/>`;
        out += `<ellipse cx="${ex2}" cy="${hy-hs*0.05}" rx="${er*0.25}" ry="${er*0.55}" fill="${pupilColor}"/>`;
      }
      break;
    case 'star':
      for(const side of [-1,1]) {
        const ex2 = hx + side*hs*0.32;
        out += `<circle cx="${ex2}" cy="${hy-hs*0.05}" r="${er*1.3}" fill="${eyeColor}"/>`;
        const pts = [];
        for(let si=0; si<10; si++) {
          const ang = (si*Math.PI)/5 - Math.PI/2;
          const rad = si%2===0 ? er*0.9 : er*0.4;
          pts.push(`${ex2+Math.cos(ang)*rad},${hy-hs*0.05+Math.sin(ang)*rad}`);
        }
        out += `<polygon points="${pts.join(' ')}" fill="#ffffff" opacity=".85"/>`;
      }
      break;
    case 'hollow':
      for(const side of [-1,1]) {
        const ex2 = hx + side*hs*0.32;
        out += `<circle cx="${ex2}" cy="${hy-hs*0.05}" r="${er*1.25}" fill="${eyeColor}" opacity=".4"/>`;
        out += `<circle cx="${ex2}" cy="${hy-hs*0.05}" r="${er*0.55}" fill="${pupilColor}" opacity=".9"/>`;
      }
      break;
    case 'insect':
      for(const side of [-1,1]) {
        const ex2 = hx + side*hs*0.32;
        const hexR = er*0.35;
        for(let hi=0; hi<7; hi++) {
          const hang = hi*Math.PI/3;
          const hcx = ex2 + Math.cos(hang)*hexR;
          const hcy = hy - hs*0.05 + Math.sin(hang)*hexR;
          out += `<circle cx="${hcx}" cy="${hcy}" r="${hexR*0.45}" fill="${eyeColor}"/>`;
        }
        out += `<circle cx="${ex2}" cy="${hy-hs*0.05}" r="${hexR*0.4}" fill="${pupilColor}"/>`;
      }
      break;
    default:
      for(const side of [-1,1]) {
        const ex2 = hx + side*hs*0.32;
        out += `<circle cx="${ex2}" cy="${hy-hs*0.05}" r="${er*1.2}" fill="${eyeColor}"/>`;
        out += `<circle cx="${ex2}" cy="${hy-hs*0.05}" r="${er*0.65}" fill="${pupilColor}"/>`;
        out += `<circle cx="${ex2-er*0.25}" cy="${hy-hs*0.05-er*0.25}" r="${er*0.3}" fill="#ffffff" opacity=".7"/>`;
      }
  }
  return out;
}

function drawHorns(hx, hy, hs, s, dc, lc) {
  if (s.atk <= 20) return '';
  let out = '';
  const hornH = Math.round(hs * (0.5 + s.atk/100 * 0.7));
  const hornW = Math.round(hs * 0.18);
  const hBase = hy - hs * 0.85;
  const hCount = s.atk > 75 ? 3 : s.atk > 45 ? 2 : 1;
  const positions = hCount === 1 ? [0] : hCount === 2 ? [-0.6,0.6] : [-0.85,0,0.85];
  for(const p of positions) {
    const hpx = hx + p * hs;
    const lean = p * 0.3;
    out += `<polygon points="${hpx-hornW},${hBase} ${hpx+hornW},${hBase} ${hpx+lean*hornH},${hBase-hornH}" fill="${dc}"/>`;
    out += `<polygon points="${hpx-hornW*0.5},${hBase} ${hpx+hornW*0.5},${hBase} ${hpx+lean*hornH*0.7},${hBase-hornH*0.75}" fill="${lc}" opacity=".5"/>`;
  }
  return out;
}

function drawWings(s, cx, by, bw, bh, dc, sc) {
  if (s.agi <= 40) return '';
  let out = '';
  const wingW = Math.round(bw * (0.9 + s.agi/100 * 1.1));
  const wingH = Math.round(bh * (0.7 + s.agi/100 * 0.8));
  const wy = by + bh * 0.35;
  for(const side of [-1,1]) {
    const wx = cx + side * (bw * 0.55);
    out += `<polygon points="${wx},${wy} ${wx+side*wingW},${wy-wingH*0.5} ${wx+side*wingW*0.8},${wy+wingH*0.6}" fill="${dc}" opacity=".85"/>`;
    out += `<polygon points="${wx},${wy} ${wx+side*wingW*0.75},${wy-wingH*0.3} ${wx+side*wingW*0.55},${wy+wingH*0.45}" fill="${sc}" opacity=".4"/>`;
  }
  return out;
}

function drawAura(s, cx, cy, size) {
  if (s.sup <= 20) return '';
  let out = '';
  const aura = s.sup / 100;
  out += `<circle cx="${cx}" cy="${cy}" r="${Math.round(size*0.44)}" fill="none" stroke="${MSTAT_COLORS['sup']}" stroke-width="${Math.round(1+aura*3)}" opacity="${0.1+aura*0.3}"/>`;
  if (s.sup > 50) {
    out += `<circle cx="${cx}" cy="${cy}" r="${Math.round(size*0.47)}" fill="none" stroke="${MSTAT_LIGHT['sup']}" stroke-width="${0.5+aura}" opacity="${aura*0.2}"/>`;
  }
  const nSparkles = Math.floor(s.sup / 25);
  for(let i=0; i<nSparkles; i++) {
    const ang = (i/nSparkles) * Math.PI * 2 + 0.5;
    const sr = size * 0.42;
    const sx2 = Math.round(cx + Math.cos(ang) * sr);
    const sy2 = Math.round(cy + Math.sin(ang) * sr);
    out += `<circle cx="${sx2}" cy="${sy2}" r="${Math.round(size*0.018)}" fill="${MSTAT_LIGHT['sup']}" opacity=".8"/>`;
  }
  return out;
}

function drawSpeedStreaks(s, cx, cy, size, lc) {
  if (s.agi <= 60) return '';
  let out = '';
  const streaks = Math.floor(s.agi / 30);
  for(let i=0; i<streaks; i++) {
    const ang = (i/streaks) * Math.PI + 0.2;
    const r0 = size * 0.32;
    const r1 = size * 0.48;
    const x1 = Math.round(cx + Math.cos(ang) * r0);
    const y1 = Math.round(cy + Math.sin(ang) * r0);
    const x2 = Math.round(cx + Math.cos(ang) * r1);
    const y2 = Math.round(cy + Math.sin(ang) * r1);
    out += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${lc}" stroke-width="${size*0.012}" opacity=".5" stroke-linecap="round"/>`;
  }
  return out;
}

function drawMouth(s, hx, hy, hs, dc, lc) {
  let out = '';
  const mouthY = hy + hs * 0.55;
  if (s.atk > s.sup + 20) {
    const mw = Math.round(hs * 0.55);
    out += `<path d="M${hx-mw},${mouthY} Q${hx},${mouthY+Math.round(hs*0.3)} ${hx+mw},${mouthY}" fill="none" stroke="${dc}" stroke-width="${Math.round(hs*0.1)}" stroke-linecap="round"/>`;
    out += `<polygon points="${hx-mw*0.35},${mouthY} ${hx-mw*0.15},${mouthY} ${hx-mw*0.25},${mouthY+Math.round(hs*0.22)}" fill="#ffffff" opacity=".8"/>`;
    out += `<polygon points="${hx+mw*0.15},${mouthY} ${hx+mw*0.35},${mouthY} ${hx+mw*0.25},${mouthY+Math.round(hs*0.22)}" fill="#ffffff" opacity=".8"/>`;
  } else if (s.sup > 55) {
    const mw = Math.round(hs * 0.4);
    out += `<path d="M${hx-mw},${mouthY} Q${hx},${mouthY+Math.round(hs*0.35)} ${hx+mw},${mouthY}" fill="none" stroke="${lc}" stroke-width="${Math.round(hs*0.08)}" stroke-linecap="round"/>`;
  } else {
    const mw = Math.round(hs * 0.3);
    out += `<line x1="${hx-mw}" y1="${mouthY+Math.round(hs*0.05)}" x2="${hx+mw}" y2="${mouthY+Math.round(hs*0.05)}" stroke="${lc}" stroke-width="${Math.round(hs*0.08)}" stroke-linecap="round"/>`;
  }
  return out;
}

function drawForeheadGem(s, hx, hy, hs) {
  if (s.fcs <= 45 || selectHead(s) === 'gem') return '';
  const gr = Math.round(hs * 0.22);
  return `<polygon points="${hx},${hy-hs*0.9} ${hx+gr},${hy-hs*0.65} ${hx},${hy-hs*0.5} ${hx-gr},${hy-hs*0.65}" fill="${MSTAT_COLORS['fcs']}" opacity=".9"/>`;
}

function drawMonster(svg, s, size, seed) {
  mSetSeed(seed || '');
  const cx = size/2, cy = size/2;
  const dom = mGetDominant(s), sec = mGetSecondary(s);
  const total = mGetTotal(s) / 500;
  const bodyScale = 0.7 + total * 0.3;
  const mc = MSTAT_COLORS[dom], sc = MSTAT_COLORS[sec], dc = MSTAT_DARK[dom], lc = MSTAT_LIGHT[dom];

  let out = `<rect width="${size}" height="${size}" rx="${Math.round(size*0.15)}" fill="#0d0d18"/>`;

  const bodyType = selectBody(s);
  out += drawBody(bodyType, cx, cy, size, bodyScale, dc, mc);

  const hs = Math.round(size * (0.18 + s.stm/100 * 0.08) * bodyScale);
  const hx = cx, hy = cy - hs * 0.35;

  const headType = selectHead(s);
  out += drawHead(headType, hx, hy, hs, dc, mc, s);

  const eyeColor = s.fcs > 60 ? lc : (s.sup > 60 ? MSTAT_LIGHT['sup'] : '#e0e0f0');
  const pupilColor = '#050510';
  const eyeType = selectEyes(s);
  out += drawEyes(eyeType, hx, hy, hs, eyeColor, pupilColor, s);

  out += drawHorns(hx, hy, hs, s, dc, lc);
  out += drawWings(s, cx, cy + size*0.05, Math.round(size*0.28*bodyScale), Math.round(size*0.28*bodyScale), dc, sc);
  out += drawAura(s, cx, cy, size);
  out += drawSpeedStreaks(s, cx, cy, size, lc);
  out += drawMouth(s, hx, hy, hs, dc, lc);
  out += drawForeheadGem(s, hx, hy, hs);

  svg.innerHTML = out;
  mClearSeed();
}
