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

function mGetArchetype(s) {
  const dom = mGetDominant(s);
  const sec = mGetSecondary(s);
  const total = mGetTotal(s);
  const balanced = Object.values(s).every(v => v > 30 && v < 80);
  if (balanced && total > 250) return { label:'ALLROUNDER', color:'#ffffff' };
  const map = {
    atk: { stm:'BERSERKER', fcs:'ASSASSIN', agi:'STRIKER', sup:'WARLORD', atk:'DESTROYER' },
    stm: { atk:'TANK', fcs:'SENTINEL', agi:'IRONFOOT', sup:'GUARDIAN', stm:'FORTRESS' },
    fcs: { atk:'SNIPER', stm:'SCHOLAR', agi:'PHANTOM', sup:'ORACLE', fcs:'ENLIGHTENED' },
    agi: { atk:'DUELIST', stm:'RUNNER', fcs:'TRICKSTER', sup:'HERALD', agi:'BLUR' },
    sup: { atk:'PALADIN', stm:'MENDER', fcs:'PROPHET', agi:'BARD', sup:'ASCENDANT' },
  };
  return { label: map[dom][sec] || 'WANDERER', color: MSTAT_COLORS[dom] };
}

function drawMonster(svg, s, size, seed) {
  const cx = size/2, cy = size/2;
  const dom = mGetDominant(s);
  const sec = mGetSecondary(s);
  const total = mGetTotal(s) / 500;
  const bodyScale = 0.7 + total * 0.3;

  const mc = MSTAT_COLORS[dom];
  const sc = MSTAT_COLORS[sec];
  const dc = MSTAT_DARK[dom];
  const lc = MSTAT_LIGHT[dom];

  let out = `<rect width="${size}" height="${size}" rx="${size*0.15}" fill="#0d0d18"/>`;

  const bw = Math.round(size * 0.28 * bodyScale);
  const bh = Math.round(size * 0.28 * bodyScale);
  const bx = cx - bw/2, by = cy - bh/2 + size*0.05;

  if (dom === 'atk') {
    out += `<polygon points="${cx},${by-bh*0.3} ${bx+bw*1.2},${by+bh*0.4} ${bx+bw},${by+bh*1.3} ${bx},${by+bh*1.3} ${bx-bw*0.2},${by+bh*0.4}" fill="${dc}"/>`;
    out += `<polygon points="${cx},${by-bh*0.2} ${bx+bw},${by+bh*0.4} ${bx+bw*0.8},${by+bh*1.2} ${bx+bw*0.2},${by+bh*1.2} ${bx},${by+bh*0.4}" fill="${mc}"/>`;
  } else if (dom === 'stm') {
    const r = bw * 0.9;
    out += `<circle cx="${cx}" cy="${by+bh*0.6}" r="${r*1.1}" fill="${dc}"/>`;
    out += `<circle cx="${cx}" cy="${by+bh*0.5}" r="${r}" fill="${mc}"/>`;
  } else if (dom === 'fcs') {
    const hh = bh * 0.9;
    out += `<polygon points="${cx},${by} ${cx+bw},${by+hh*0.5} ${cx+bw*0.7},${by+hh*1.1} ${cx-bw*0.7},${by+hh*1.1} ${cx-bw},${by+hh*0.5}" fill="${dc}"/>`;
    out += `<polygon points="${cx},${by+hh*0.1} ${cx+bw*0.8},${by+hh*0.55} ${cx+bw*0.55},${by+hh} ${cx-bw*0.55},${by+hh} ${cx-bw*0.8},${by+hh*0.55}" fill="${mc}"/>`;
  } else if (dom === 'agi') {
    out += `<ellipse cx="${cx+size*0.05}" cy="${by+bh*0.7}" rx="${bw*1.2}" ry="${bh*0.7}" fill="${dc}"/>`;
    out += `<ellipse cx="${cx}" cy="${by+bh*0.6}" rx="${bw*1.1}" ry="${bh*0.6}" fill="${mc}"/>`;
  } else {
    out += `<ellipse cx="${cx}" cy="${by+bh*0.7}" rx="${bw*0.9}" ry="${bh*1.1}" fill="${dc}"/>`;
    out += `<ellipse cx="${cx}" cy="${by+bh*0.6}" rx="${bw*0.8}" ry="${bh}" fill="${mc}"/>`;
  }

  const hs = size * (0.18 + s.stm/100 * 0.08) * bodyScale;
  const hx = cx, hy = by - hs * 0.3;

  if (s.fcs > 70) {
    out += `<polygon points="${hx},${hy-hs} ${hx+hs},${hy} ${hx},${hy+hs*0.5} ${hx-hs},${hy}" fill="${dc}"/>`;
    out += `<polygon points="${hx},${hy-hs*0.8} ${hx+hs*0.8},${hy} ${hx},${hy+hs*0.35} ${hx-hs*0.8},${hy}" fill="${mc}"/>`;
  } else if (s.stm > 70) {
    out += `<circle cx="${hx}" cy="${hy}" r="${hs*1.05}" fill="${dc}"/>`;
    out += `<circle cx="${hx}" cy="${hy}" r="${hs}" fill="${mc}"/>`;
  } else {
    out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.9}" ry="${hs}" fill="${dc}"/>`;
    out += `<ellipse cx="${hx}" cy="${hy}" rx="${hs*0.8}" ry="${hs*0.9}" fill="${mc}"/>`;
  }

  const er = Math.max(size*0.025, size * 0.025 + s.fcs/100 * size*0.025);
  const ey = hy - hs*0.1;
  const ex = hs * 0.35;
  const eyeColor = s.fcs > 60 ? lc : (s.sup > 60 ? MSTAT_LIGHT['sup'] : '#ffffff');
  const pupilColor = '#000a14';

  if (dom === 'fcs') {
    out += `<circle cx="${hx}" cy="${ey}" r="${er*2.5}" fill="${eyeColor}"/>`;
    out += `<ellipse cx="${hx}" cy="${ey}" rx="${er*0.8}" ry="${er*2}" fill="${pupilColor}"/>`;
    out += `<circle cx="${hx-er*0.7}" cy="${ey-er*0.7}" r="${er*0.6}" fill="#ffffff" opacity=".8"/>`;
    for(let i=0;i<8;i++){
      const a=i*Math.PI/4; const r0=er*1.2,r1=er*2.3;
      out+=`<line x1="${hx+Math.cos(a)*r0}" y1="${ey+Math.sin(a)*r0}" x2="${hx+Math.cos(a)*r1}" y2="${ey+Math.sin(a)*r1}" stroke="${dc}" stroke-width="0.8" opacity=".6"/>`;
    }
  } else {
    for(const side of [-1,1]) {
      const ex2 = hx + side*ex;
      if (s.agi > 70) {
        out += `<ellipse cx="${ex2}" cy="${ey}" rx="${er*1.6}" ry="${er*0.8}" fill="${eyeColor}" transform="rotate(${side*-15},${ex2},${ey})"/>`;
        out += `<ellipse cx="${ex2}" cy="${ey}" rx="${er*0.6}" ry="${er*0.6}" fill="${pupilColor}"/>`;
      } else if (s.sup > 70) {
        out += `<circle cx="${ex2}" cy="${ey}" r="${er*1.4}" fill="${eyeColor}"/>`;
        out += `<polygon points="${ex2},${ey-er} ${ex2+er*0.35},${ey-er*0.35} ${ex2+er},${ey} ${ex2+er*0.35},${ey+er*0.35} ${ex2},${ey+er} ${ex2-er*0.35},${ey+er*0.35} ${ex2-er},${ey} ${ex2-er*0.35},${ey-er*0.35}" fill="${MSTAT_LIGHT['sup']}"/>`;
      } else {
        out += `<circle cx="${ex2}" cy="${ey}" r="${er*1.3}" fill="${eyeColor}"/>`;
        out += `<circle cx="${ex2}" cy="${ey}" r="${er*0.7}" fill="${pupilColor}"/>`;
        out += `<circle cx="${ex2-er*0.3}" cy="${ey-er*0.3}" r="${er*0.35}" fill="#ffffff" opacity=".7"/>`;
      }
    }
  }

  if (s.atk > 20) {
    const hornH = size * (0.04 + s.atk/100 * 0.1);
    const hornW = size * 0.04;
    const hBase = hy - hs*0.75;
    const hCount = s.atk > 75 ? 3 : s.atk > 45 ? 2 : 1;
    const hornPositions = hCount===1 ? [0] : hCount===2 ? [-1,1] : [-1.5,0,1.5];
    for(const p of hornPositions) {
      const hpx = hx + p * hs*0.45;
      const lean = p * 0.25;
      out += `<polygon points="${hpx-hornW},${hBase} ${hpx+hornW},${hBase} ${hpx+lean*hornH},${hBase-hornH}" fill="${dc}"/>`;
      out += `<polygon points="${hpx-hornW*0.5},${hBase} ${hpx+hornW*0.5},${hBase} ${hpx+lean*hornH*0.7},${hBase-hornH*0.75}" fill="${lc}" opacity=".5"/>`;
    }
  } else {
    const earH = size * 0.07;
    for(const side of [-1,1]) {
      const epx = hx + side*hs*0.8;
      out += `<polygon points="${epx-size*0.04},${hy-hs*0.5} ${epx+size*0.04},${hy-hs*0.5} ${epx+side*size*0.02},${hy-hs*0.5-earH}" fill="${mc}"/>`;
    }
  }

  if (s.agi > 40) {
    const wingW = size * (0.1 + s.agi/100 * 0.18);
    const wingH = size * (0.08 + s.agi/100 * 0.1);
    const wy = by + bh*0.3;
    for(const side of [-1,1]) {
      const wx = cx + side*(bw*0.5);
      out += `<polygon points="${wx},${wy} ${wx+side*wingW},${wy-wingH*0.6} ${wx+side*wingW*0.7},${wy+wingH}" fill="${dc}" opacity=".9"/>`;
      out += `<polygon points="${wx},${wy} ${wx+side*wingW*0.8},${wy-wingH*0.4} ${wx+side*wingW*0.55},${wy+wingH*0.8}" fill="${sc}" opacity=".5"/>`;
    }
  } else {
    const aw = size*0.08, ah=size*0.05;
    for(const side of [-1,1]) {
      const ax = cx + side*(bw*0.55);
      out += `<rect x="${ax-aw/2}" y="${by+bh*0.3}" width="${aw}" height="${ah}" rx="${ah/2}" fill="${dc}"/>`;
    }
  }

  if (s.stm > 30) {
    const tw = size*0.05, tl = size*(0.1 + s.stm/100*0.14);
    const tx = cx, ty = by+bh*1.1;
    if (s.stm > 70) {
      out += `<polygon points="${tx-tw},${ty} ${tx+tw},${ty} ${tx+tw*0.5},${ty+tl} ${tx-tw*0.5},${ty+tl}" fill="${dc}"/>`;
      out += `<polygon points="${tx},${ty+tl*0.6} ${tx+tw*1.8},${ty+tl*0.3} ${tx+tw*0.3},${ty+tl}" fill="${mc}" opacity=".7"/>`;
      out += `<polygon points="${tx},${ty+tl*0.6} ${tx-tw*1.8},${ty+tl*0.3} ${tx-tw*0.3},${ty+tl}" fill="${mc}" opacity=".7"/>`;
    } else {
      out += `<ellipse cx="${tx}" cy="${ty+tl*0.5}" rx="${tw*0.8}" ry="${tl*0.5}" fill="${dc}" opacity=".7"/>`;
    }
  }

  if (s.sup > 20) {
    const aura = s.sup / 100;
    out += `<circle cx="${cx}" cy="${cy}" r="${size*0.44}" fill="none" stroke="${MSTAT_COLORS['sup']}" stroke-width="${1+aura*3}" opacity="${0.1+aura*0.3}"/>`;
    if (s.sup > 50) {
      out += `<circle cx="${cx}" cy="${cy}" r="${size*0.47}" fill="none" stroke="${MSTAT_LIGHT['sup']}" stroke-width="${0.5+aura}" opacity="${aura*0.2}"/>`;
    }
    const nSparkles = Math.floor(s.sup/25);
    for(let i=0;i<nSparkles;i++){
      const a = (i/nSparkles)*Math.PI*2 + 0.5;
      const sr = size*0.42;
      const sx2 = cx+Math.cos(a)*sr, sy2 = cy+Math.sin(a)*sr;
      out += `<circle cx="${sx2}" cy="${sy2}" r="${size*0.018}" fill="${MSTAT_LIGHT['sup']}" opacity=".8"/>`;
    }
  }

  const mouthY = hy + hs*0.55;
  if (s.atk > s.sup + 20) {
    const mw = hs*0.55;
    out += `<path d="M${hx-mw},${mouthY} Q${hx},${mouthY+hs*0.3} ${hx+mw},${mouthY}" fill="none" stroke="${dc}" stroke-width="${size*0.025}" stroke-linecap="round"/>`;
    out += `<polygon points="${hx-mw*0.4},${mouthY} ${hx-mw*0.2},${mouthY} ${hx-mw*0.3},${mouthY+hs*0.22}" fill="#ffffff" opacity=".8"/>`;
    out += `<polygon points="${hx+mw*0.2},${mouthY} ${hx+mw*0.4},${mouthY} ${hx+mw*0.3},${mouthY+hs*0.22}" fill="#ffffff" opacity=".8"/>`;
  } else if (s.sup > 50) {
    const mw = hs*0.4;
    out += `<path d="M${hx-mw},${mouthY} Q${hx},${mouthY+hs*0.35} ${hx+mw},${mouthY}" fill="none" stroke="${lc}" stroke-width="${size*0.02}" stroke-linecap="round"/>`;
  } else {
    const mw = hs*0.3;
    out += `<line x1="${hx-mw}" y1="${mouthY+hs*0.05}" x2="${hx+mw}" y2="${mouthY+hs*0.05}" stroke="${lc}" stroke-width="${size*0.02}" stroke-linecap="round"/>`;
  }

  if (s.fcs > 50 && dom !== 'fcs') {
    const gr = size * 0.03;
    out += `<polygon points="${hx},${hy-hs*0.85} ${hx+gr},${hy-hs*0.65} ${hx},${hy-hs*0.55} ${hx-gr},${hy-hs*0.65}" fill="${MSTAT_COLORS['fcs']}" opacity=".9"/>`;
  }

  svg.innerHTML = out;
}
