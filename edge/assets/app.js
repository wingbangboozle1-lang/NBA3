// NBA3 dashboard helpers: JSON fetch + table rendering.
async function jget(name){const r=await fetch('data/'+name);if(!r.ok)throw new Error(name+' '+r.status);return r.json();}
function el(t,c,h){const e=document.createElement(t);if(c)e.className=c;if(h!==undefined)e.innerHTML=h;return e;}
function badge(text,cls){const s=el('span','badge'+(cls?' '+cls:''),text);return s;}
function statusBadge(status){
  if(status==='eligible')return badge('eligible','ok');
  if(status&&status.startsWith('provisional'))return badge('provisional','warn');
  if(status&&status.startsWith('not eligible'))return badge('not eligible','bad');
  return badge(status||'—','');
}
function table(cols,rows,opts){
  opts=opts||{};
  const w=el('div','tblwrap');const t=el('table');
  const tr=el('tr');
  cols.forEach(c=>{const th=el('th',c.cls||'',c.h);if(c.num)th.classList.add('num');tr.appendChild(th);});
  const thead=el('thead');thead.appendChild(tr);t.appendChild(thead);
  const tb=el('tbody');
  rows.forEach(r=>{const trr=el('tr');r.forEach(cell=>{trr.appendChild(cell);});tb.appendChild(trr);});
  t.appendChild(tb);w.appendChild(t);return w;
}
function td(h,cls){const c=el('td',cls,h);return c;}
function num(v,dec,dash){if(v===null||v===undefined||v==='')return td(dash||'—','num');return td(Number(v).toFixed(dec===undefined?1:dec),'num');}
function srcLink(href,label){return `<a href="${href}" target="_blank" rel="noopener">${label||'source'}</a>`;}
function fmtML(v){if(v===null||v===undefined)return '—';return (v>0?'+':'')+v;}
const BBR_BOX = (d,home)=>`https://www.basketball-reference.com/boxscores/${d.replace(/-/g,'')}0${home}.html`;
const BBR_NOV = 'https://www.basketball-reference.com/leagues/NBA_2027_games-november.html';
const BBR_OCT = 'https://www.basketball-reference.com/leagues/NBA_2027_games-october.html';
const BBR_RATINGS = 'https://www.basketball-reference.com/leagues/NBA_2027_ratings.html';
const INJ_PDF = 'https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf';
const BBR_PERGAME = 'https://www.basketball-reference.com/leagues/NBA_2027_per_game.html';
