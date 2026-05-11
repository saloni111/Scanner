// ===== STATE =====
let token='',ghUser=null,repos=[],selectedRepo=null,selectedPR=null;
let prData={details:null,files:[],commits:[]};

// ===== API =====
async function ghFetch(url){
  const r=await fetch(url,{headers:{'Authorization':`Bearer ${token}`,'Accept':'application/vnd.github.v3+json'}});
  if(r.status===401) throw new Error('Invalid token — please check your Personal Access Token.');
  if(r.status===403){const b=await r.json().catch(()=>({}));throw new Error(b.message?.includes('rate limit')?'GitHub API rate limit reached — please wait and try again.':'Access denied — check your token permissions.');}
  if(r.status===404) throw new Error('Repository or PR not found — check your token permissions.');
  if(!r.ok) throw new Error(`GitHub API error (${r.status}).`);
  return r.json();
}

// ===== NAV =====
function goToStep(s){
  document.querySelectorAll('.step-panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('step'+s).classList.add('active');
  document.querySelectorAll('.step-dot').forEach(d=>{const n=+d.dataset.step;d.classList.remove('active','completed');if(n===s)d.classList.add('active');else if(n<s)d.classList.add('completed');});
  document.querySelectorAll('.step-line').forEach(l=>{const a=+l.dataset.after;l.classList.remove('active','completed');if(a<s)l.classList.add('completed');else if(a===s-1)l.classList.add('active');});
  window.scrollTo({top:0,behavior:'smooth'});
}
function showError(id,msg){const e=document.getElementById(id);e.textContent=msg;e.classList.add('visible');}
function hideError(id){const e=document.getElementById(id);e.textContent='';e.classList.remove('visible');}

// ===== STEP 1 =====
async function connectGitHub(){
  const btn=document.getElementById('connectBtn');
  token=document.getElementById('tokenInput').value.trim();
  hideError('connectError');
  if(!token){showError('connectError','Please enter a token.');return;}
  btn.classList.add('btn-loading');btn.innerHTML='<span class="spinner"></span>Connecting...';
  try{
    const[user,rd]=await Promise.all([ghFetch('https://api.github.com/user'),ghFetch('https://api.github.com/user/repos?per_page=100&sort=updated')]);
    ghUser=user;repos=rd;renderUserCard();renderRepos();goToStep(2);
  }catch(e){showError('connectError',e.message||'Connection failed.');}
  finally{btn.classList.remove('btn-loading');btn.innerHTML='Connect to GitHub';}
}

// ===== STEP 2 =====
function renderUserCard(){document.getElementById('userCard').innerHTML=`<img src="${ghUser.avatar_url}" alt="${ghUser.login}"><div class="user-info"><h4>${ghUser.name||ghUser.login}</h4><p>@${ghUser.login} · ${repos.length} repositories</p></div>`;}
function renderRepos(f){
  const list=document.getElementById('repoList');
  const filtered=f?repos.filter(r=>r.full_name.toLowerCase().includes(f.toLowerCase())):repos;
  if(!filtered.length){list.innerHTML='<div class="empty-state">No repositories match.</div>';return;}
  list.innerHTML=filtered.map(r=>`<div class="repo-item" onclick="selectRepo('${r.full_name}',this)"><div><h4>${r.full_name}</h4><p>${r.description?r.description.substring(0,60):'No description'}</p></div><span class="vis">${r.private?'private':'public'}</span></div>`).join('');
}
function filterRepos(){renderRepos(document.getElementById('repoSearch').value);}
async function selectRepo(fn,el){
  document.querySelectorAll('.repo-item').forEach(i=>i.classList.remove('selected'));el.classList.add('selected');
  selectedRepo=repos.find(r=>r.full_name===fn);selectedPR=null;
  document.getElementById('scanBtn').style.opacity='.4';document.getElementById('scanBtn').style.pointerEvents='none';
  const sec=document.getElementById('prSection');sec.style.display='block';
  document.getElementById('prLoading').style.display='block';document.getElementById('prListContainer').innerHTML='';hideError('prError');
  try{
    const prs=await ghFetch(`https://api.github.com/repos/${fn}/pulls?state=open&per_page=50`);
    document.getElementById('prLoading').style.display='none';
    if(!prs.length){document.getElementById('prListContainer').innerHTML='<div class="empty-state">No open pull requests found in this repository.</div>';return;}
    document.getElementById('prListContainer').innerHTML='<div class="pr-list">'+prs.map(pr=>`<div class="pr-item" onclick="selectPR(${pr.number},this)"><div class="pr-item-main"><h4>#${pr.number} — ${esc(pr.title)}</h4><p>${pr.user.login} · ${pr.head.ref} → ${pr.base.ref} · ${timeAgo(new Date(pr.created_at))}</p></div></div>`).join('')+'</div>';
  }catch(e){document.getElementById('prLoading').style.display='none';showError('prError',e.message);}
}
function selectPR(n,el){document.querySelectorAll('.pr-item').forEach(i=>i.classList.remove('selected'));el.classList.add('selected');selectedPR=n;document.getElementById('scanBtn').style.opacity='1';document.getElementById('scanBtn').style.pointerEvents='auto';}

// ===== STEP 3 =====
async function startScan(){
  if(!selectedPR||!selectedRepo)return;
  const repo=selectedRepo.full_name;
  document.getElementById('scanTitle').textContent=`Scanning PR #${selectedPR}`;
  document.getElementById('scanTerminal').innerHTML='';
  document.getElementById('progressFill').style.width='0%';hideError('scanError');goToStep(3);
  const T=document.getElementById('scanTerminal'),F=document.getElementById('progressFill'),L=document.getElementById('progressLabel');
  function log(m,p){const d=document.createElement('div');d.className='scan-line';const n=new Date();d.innerHTML=`<span class="time">[${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}:${String(n.getSeconds()).padStart(2,'0')}]</span> ${m}`;T.appendChild(d);T.scrollTop=T.scrollHeight;if(p!=null){F.style.width=p+'%';L.textContent=p+'% complete';}}
  try{
    log('Initializing Scanner v2.4.1...',5);await delay(300);
    log(`Fetching PR #${selectedPR} from ${repo}...`,15);
    const details=await ghFetch(`https://api.github.com/repos/${repo}/pulls/${selectedPR}`);
    prData.details=details;log(`<span class="ok">done</span> PR: "${esc(details.title)}"`,25);await delay(200);
    log('Fetching changed files with patch data...',35);
    const files=await ghFetch(`https://api.github.com/repos/${repo}/pulls/${selectedPR}/files`);
    prData.files=files;log(`<span class="ok">done</span> ${files.length} files (+${files.reduce((s,f)=>s+f.additions,0)} / -${files.reduce((s,f)=>s+f.deletions,0)})`,50);await delay(200);
    log('Fetching commit history...',60);
    const commits=await ghFetch(`https://api.github.com/repos/${repo}/pulls/${selectedPR}/commits`);
    prData.commits=commits;log(`<span class="ok">done</span> ${commits.length} commits`,70);await delay(200);
    log('--- Security Analysis ---',75);await delay(300);
    log('Scanning for sensitive files...',78);await delay(200);
    log('Scanning patches for hardcoded secrets...',82);await delay(300);
    log('Checking commit verification...',86);await delay(200);
    log('Analyzing dependency changes...',90);await delay(200);
    const flags=analyzeRedFlags(details,files,commits);
    const risk=computeRisk(flags);
    log(`Flagged ${flags.length} findings`,95);await delay(200);
    log(`<span class="${risk.level==='low'?'ok':risk.level==='medium'?'warn':'err'}">done</span> Risk: ${risk.score}/100 (${risk.label})`,100);
    await delay(500);renderReport(risk,flags);goToStep(4);
  }catch(e){showError('scanError',e.message);log(`<span class="err">ERROR</span> ${esc(e.message)}`,null);}
}

// ===== ANALYSIS ENGINE =====
const SENSITIVE_PATTERNS=[/\.env$/i,/\.pem$/i,/id_rsa/i,/config\.yml$/i,/config\.yaml$/i,/secrets?\./i,/credentials/i,/\.key$/i,/\.cert$/i,/settings\.py$/i,/database\.yml$/i,/\.secret/i];
const SECRET_PATTERNS=[
  {re:/password\s*[=:]\s*["'][^"']+["']/gi,name:'Hardcoded password'},
  {re:/api[_-]?key\s*[=:]\s*["'][^"']+["']/gi,name:'API key'},
  {re:/secret[_-]?key\s*[=:]\s*["'][^"']+["']/gi,name:'Secret key'},
  {re:/token\s*[=:]\s*["'][^"']+["']/gi,name:'Hardcoded token'},
  {re:/Bearer\s+[A-Za-z0-9\-._~+\/]+=*/g,name:'Bearer token'},
  {re:/private[_-]?key\s*[=:]\s*["'][^"']+["']/gi,name:'Private key'},
  {re:/AWS_SECRET/gi,name:'AWS secret reference'},
  {re:/GITHUB_TOKEN/gi,name:'GitHub token reference'},
  {re:/DATABASE_PASSWORD\s*=\s*["'][^"']+["']/gi,name:'Database password'},
  {re:/JWT_SECRET\s*=\s*["'][^"']+["']/gi,name:'JWT secret'},
  {re:/sk_live_/gi,name:'Stripe live key'},
  {re:/HARDCODED_.*SECRET/gi,name:'Hardcoded secret placeholder'},
];
const LOCK_FILES=['package-lock.json','yarn.lock','Gemfile.lock','poetry.lock','go.sum','pnpm-lock.yaml'];
const DEP_FILES=['package.json','requirements.txt','go.mod','Gemfile','pyproject.toml','Cargo.toml'];
const BINARY_EXT=['.png','.jpg','.jpeg','.gif','.ico','.svg','.woff','.woff2','.ttf','.eot','.pdf','.zip','.tar','.gz'];

function analyzeRedFlags(details,files,commits){
  const flags=[];
  // 1. Sensitive files
  files.forEach(f=>{
    SENSITIVE_PATTERNS.forEach(p=>{
      if(p.test(f.filename)){
        flags.push({sev:'critical',title:'Sensitive file changed',desc:`File matching sensitive pattern was modified.`,evidence:f.filename,action:'Review this file carefully. Ensure no secrets are committed. Consider using .gitignore.'});
      }
    });
  });
  // 2. Hardcoded secrets in patches
  files.forEach(f=>{
    if(!f.patch)return;
    const addedLines=f.patch.split('\n').filter(l=>l.startsWith('+')&&!l.startsWith('+++'));
    addedLines.forEach((line,idx)=>{
      SECRET_PATTERNS.forEach(sp=>{
        if(sp.re.test(line)){
          sp.re.lastIndex=0;
          const lineNum=idx+1;
          flags.push({sev:'critical',title:sp.name+' detected',desc:`Pattern matching "${sp.name}" found in added code.`,evidence:`${f.filename} (added line ~${lineNum}): ${line.substring(1,80).trim()}${line.length>80?'…':''}`,action:'Remove the secret and use environment variables or a secrets manager.'});
        }
        sp.re.lastIndex=0;
      });
    });
  });
  // 3. PR size
  const totalChanges=files.reduce((s,f)=>s+f.additions+f.deletions,0);
  if(files.length>10||totalChanges>500){
    flags.push({sev:'high',title:'Large PR',desc:`This PR changes ${files.length} files with ${totalChanges} total line changes.`,evidence:`${files.length} files, +${files.reduce((s,f)=>s+f.additions,0)} / -${files.reduce((s,f)=>s+f.deletions,0)}`,action:'Consider splitting into smaller, focused PRs for easier review.'});
  }
  // 4. No description
  if(!details.body||details.body.trim().length<10){
    flags.push({sev:'medium',title:'Missing PR description',desc:'This PR has no meaningful description, making review harder.',evidence:'PR body is empty or too short.',action:'Add a description explaining what this PR does and why.'});
  }
  // 5. Binary/lock files
  const locks=files.filter(f=>LOCK_FILES.some(l=>f.filename.endsWith(l)));
  if(locks.length) flags.push({sev:'low',title:'Lock file changes',desc:`Dependency lock file(s) updated.`,evidence:locks.map(l=>l.filename).join(', '),action:'Verify dependency updates are intentional and reviewed.'});
  const bins=files.filter(f=>BINARY_EXT.some(e=>f.filename.toLowerCase().endsWith(e)));
  if(bins.length) flags.push({sev:'low',title:'Binary files changed',desc:`${bins.length} binary/asset file(s) modified.`,evidence:bins.map(b=>b.filename).join(', '),action:'Ensure binary files are necessary and not bloating the repository.'});
  // 6. Unverified commits
  const unverified=commits.filter(c=>c.commit.verification&&!c.commit.verification.verified);
  if(unverified.length) flags.push({sev:'medium',title:'Unverified commits',desc:`${unverified.length} of ${commits.length} commits are not cryptographically signed.`,evidence:unverified.map(c=>c.sha.substring(0,7)).join(', '),action:'Enable GPG or SSH commit signing for auditability.'});
  // 7. Dependency files
  const deps=files.filter(f=>DEP_FILES.some(d=>f.filename.endsWith(d)));
  if(deps.length) flags.push({sev:'medium',title:'Dependency changes detected',desc:'Files that manage project dependencies were modified.',evidence:deps.map(d=>d.filename).join(', '),action:'Audit new dependencies for known vulnerabilities before merging.'});
  // 8. Large single files
  const bigFiles=files.filter(f=>f.changes>300);
  if(bigFiles.length) flags.push({sev:'medium',title:'Large file changes',desc:`${bigFiles.length} file(s) with 300+ line changes.`,evidence:bigFiles.map(f=>`${f.filename} (${f.changes} lines)`).join(', '),action:'Review these files thoroughly — large changes are error-prone.'});
  // Deduplicate by title+evidence
  const seen=new Set();
  return flags.filter(f=>{const k=f.title+f.evidence;if(seen.has(k))return false;seen.add(k);return true;});
}

function computeRisk(flags){
  let s=5;
  flags.forEach(f=>{if(f.sev==='critical')s+=20;else if(f.sev==='high')s+=12;else if(f.sev==='medium')s+=5;else s+=2;});
  s=Math.min(s,100);
  const level=s>=70?'critical':s>=45?'high':s>=25?'medium':'low';
  const label=level==='critical'?'Critical':level==='high'?'High':level==='medium'?'Medium':'Low';
  return{score:s,level,label};
}

// ===== STEP 4 RENDER =====
function renderReport(risk,flags){
  const d=prData.details,f=prData.files,c=prData.commits;
  const totalAdd=f.reduce((s,x)=>s+x.additions,0),totalDel=f.reduce((s,x)=>s+x.deletions,0);
  const scanTime=new Date().toLocaleString();
  const sevOrder={critical:0,high:1,medium:2,low:3};
  flags.sort((a,b)=>sevOrder[a.sev]-sevOrder[b.sev]);
  const counts={critical:0,high:0,medium:0,low:0};
  flags.forEach(fl=>counts[fl.sev]++);

  // Header
  document.getElementById('reportHeader').innerHTML=`
    <div class="rpt-header-left">
      <h2 class="rpt-pr-title">#${d.number} — ${esc(d.title)}</h2>
      <div class="rpt-meta-row">
        <span>by <strong>${esc(d.user.login)}</strong></span>
        <span class="rpt-sep">·</span>
        <span class="rpt-branch">${esc(d.head.ref)} → ${esc(d.base.ref)}</span>
        <span class="rpt-sep">·</span>
        <span>Scanned ${scanTime}</span>
      </div>
    </div>`;

  // Risk score
  const rc=risk.level==='critical'?'rsk-critical':risk.level==='high'?'rsk-high':risk.level==='medium'?'rsk-medium':'rsk-low';
  document.getElementById('riskPanel').innerHTML=`
    <div class="rsk-score-ring ${rc}">
      <div class="rsk-num">${risk.score}</div>
      <div class="rsk-of">/100</div>
    </div>
    <div class="rsk-info">
      <div class="rsk-badge ${rc}">${risk.label} Risk</div>
      <p>${counts.critical} critical · ${counts.high} high · ${counts.medium} medium · ${counts.low} low</p>
    </div>`;

  // Stats bar
  document.getElementById('statsBar').innerHTML=`
    <div class="stat-cell"><div class="stat-v">${f.length}</div><div class="stat-l">Files</div></div>
    <div class="stat-cell"><div class="stat-v">+${totalAdd}</div><div class="stat-l">Added</div></div>
    <div class="stat-cell"><div class="stat-v">-${totalDel}</div><div class="stat-l">Removed</div></div>
    <div class="stat-cell"><div class="stat-v">${c.length}</div><div class="stat-l">Commits</div></div>`;

  // Flags
  const fc=document.getElementById('flagsPanel');
  if(!flags.length){fc.innerHTML='<div class="rpt-success">No issues detected — this PR looks clean.</div>';
  }else{
    fc.innerHTML=flags.map(fl=>{
      const cls=fl.sev==='critical'?'sev-critical':fl.sev==='high'?'sev-high':fl.sev==='medium'?'sev-medium':'sev-low';
      return `<div class="flag-card">
        <div class="flag-top"><span class="flag-badge ${cls}">${fl.sev}</span><span class="flag-title">${esc(fl.title)}</span></div>
        <p class="flag-desc">${esc(fl.desc)}</p>
        <div class="flag-evidence"><code>${esc(fl.evidence)}</code></div>
        <div class="flag-action"><strong>Action:</strong> ${esc(fl.action)}</div>
      </div>`;
    }).join('');
  }

  // Files
  document.getElementById('filesPanel').innerHTML=f.map(file=>{
    const st=file.status==='added'?'+':file.status==='removed'?'−':'~';
    const sc=file.status==='added'?'fst-add':file.status==='removed'?'fst-del':'fst-mod';
    return `<div class="ftbl-row"><span class="ftbl-status ${sc}">${st}</span><span class="ftbl-name">${esc(file.filename)}</span><span class="ftbl-stat"><span class="fc-add">+${file.additions}</span> <span class="fc-del">-${file.deletions}</span></span></div>`;
  }).join('');

  // Commits
  document.getElementById('commitsPanel').innerHTML=c.map(cm=>{
    const v=cm.commit.verification?.verified;
    return `<div class="ctbl-row"><span class="ctbl-sha">${cm.sha.substring(0,7)}</span><span class="ctbl-msg">${esc(cm.commit.message.split('\n')[0])}</span><span class="ctbl-author">${esc(cm.commit.author.name)}</span><span class="ctbl-ver ${v?'ver-yes':'ver-no'}">${v?'verified':'unverified'}</span></div>`;
  }).join('');
}

function shareReport(){
  const d=prData.details,f=prData.files,c=prData.commits;
  const totalAdd=f.reduce((s,x)=>s+x.additions,0),totalDel=f.reduce((s,x)=>s+x.deletions,0);
  const text=`Scanner Security Report\nPR #${d.number}: ${d.title}\nAuthor: ${d.user.login} | ${d.head.ref} → ${d.base.ref}\nFiles: ${f.length} | +${totalAdd} / -${totalDel} | Commits: ${c.length}\n${d.html_url}`;
  navigator.clipboard.writeText(text).then(()=>{const b=document.getElementById('shareBtn');b.textContent='Copied to clipboard';setTimeout(()=>{b.textContent='Share Report';},2500);});
}
function resetDemo(){selectedRepo=null;selectedPR=null;prData={details:null,files:[],commits:[]};goToStep(2);}

// ===== UTILS =====
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function delay(ms){return new Promise(r=>setTimeout(r,ms));}
function timeAgo(d){const s=Math.floor((Date.now()-d)/1000);if(s<60)return'just now';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago';}
window.addEventListener('scroll',()=>{document.getElementById('navbar').classList.toggle('scrolled',window.scrollY>50);});
