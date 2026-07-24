// ===== Common JS (multi-page) =====
const pageMap={
  'overview':'index.html','home':'home.html','refactor':'refactor.html',
  'customers':'customers.html','detail':'detail.html','analytics':'analytics.html',
  'consumption':'analytics.html','billing':'billing.html','balance':'balance.html',
  'pricing':'pricing.html','invoices':'invoices.html','payment':'payment.html',
  'health':'health.html','profile-analysis':'profile-analysis.html',
  'forecast':'forecast.html','tags':'tags.html','users':'users.html',
  'roles':'roles.html','industry-types':'industry-types.html',
  'database-management':'database-management.html','sync-logs':'sync-logs.html',
  'audit-logs':'audit-logs.html','profile-page':'profile.html',
  'reset-password':'reset-password.html','admin':'admin.html'
};
function pageToFilename(p){return pageMap[p]||null;}
function navigateTo(page){const t=pageToFilename(page);if(t)window.location.href=t;}

const shell=document.querySelector('.shell');
const parents=[...document.querySelectorAll('.nav-parent')];
const leafButtons=[...document.querySelectorAll('[data-page]:not(.nav-parent)')];
const toggle=document.querySelector('.toggle-btn');
const toggleLabel=document.querySelector('.toggle-label');
const toggleIcon=document.querySelector('.toggle-icon');

function setSidebarCollapsed(c){
  if(!shell)return;
  shell.classList.toggle('collapsed',c);
  if(toggle){toggle.setAttribute('aria-expanded',String(!c));toggle.setAttribute('aria-label',c?'展开侧边栏':'折叠侧边栏');toggle.title=c?'展开侧边栏':'折叠侧边栏';}
  if(toggleLabel)toggleLabel.textContent=c?'展开':'收起';
  if(toggleIcon)toggleIcon.textContent='‹';
  localStorage.setItem('prototype-sidebar-collapsed',String(c));
}

leafButtons.forEach(b=>b.addEventListener('click',()=>navigateTo(b.dataset.page)));
document.querySelectorAll('[data-page-link]').forEach(b=>b.addEventListener('click',()=>navigateTo(b.dataset.pageLink)));
parents.forEach(p=>p.addEventListener('click',e=>{
  e.stopPropagation();
  if(shell&&shell.classList.contains('collapsed')){navigateTo(p.dataset.page);return;}
  const isOpen=p.getAttribute('aria-expanded')==='true';
  parents.forEach(o=>o.setAttribute('aria-expanded',String(o===p&&!isOpen)));
}));
if(toggle)toggle.addEventListener('click',()=>setSidebarCollapsed(!shell.classList.contains('collapsed')));
setSidebarCollapsed(localStorage.getItem('prototype-sidebar-collapsed')==='true');

// Set active nav
(function(){
  const f=(window.location.pathname.split('/').pop()||'index.html').replace('.html','');
  const m={'index':'overview','profile':'profile-page'};
  const active=m[f]||f;
  leafButtons.forEach(b=>b.classList.toggle('active',b.dataset.page===active));
  parents.forEach(p=>{
    const isP=p.dataset.page===active
      ||(active==='detail'&&p.dataset.page==='customers')
      ||(active==='consumption'&&p.dataset.page==='analytics')
      ||(['balance','pricing','invoices'].includes(active)&&p.dataset.page==='billing')
      ||(['payment','health','profile-analysis','forecast','consumption'].includes(active)&&p.dataset.page==='analytics');
    p.classList.toggle('active',isP);
    if(!shell||!shell.classList.contains('collapsed'))p.setAttribute('aria-expanded',String(isP));
  });
})();

// Opt panels
document.querySelectorAll('.opt-toggle').forEach(b=>b.addEventListener('click',()=>b.parentElement.classList.toggle('open')));

// Home todo sort
const todoT=document.getElementById('todo-sort-toggle');
if(todoT)todoT.addEventListener('change',e=>{
  const l=document.getElementById('todo-list');if(!l)return;
  const r=[...l.querySelectorAll('.row')];
  r.sort((a,b)=>e.target.checked?parseInt(b.dataset.amount)-parseInt(a.dataset.amount):parseInt(b.dataset.urgency)-parseInt(a.dataset.urgency));
  r.forEach(x=>l.appendChild(x));
});
// Chart tabs
document.querySelectorAll('[data-chart-tab]').forEach(t=>t.addEventListener('click',()=>{t.parentElement.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));t.classList.add('active');}));
// Dropdown close
document.addEventListener('click',e=>{if(!e.target.closest('.row-dropdown'))document.querySelectorAll('.row-dropdown.open').forEach(d=>d.classList.remove('open'));});
document.querySelectorAll('.dropdown-menu button[data-page-link]').forEach(b=>b.addEventListener('click',()=>{navigateTo(b.dataset.pageLink);b.closest('.row-dropdown').classList.remove('open');}));
// Pagination
document.querySelectorAll('.pagination').forEach(pg=>{
  const c=pg.querySelector('.page-controls');if(!c)return;
  const ji=pg.querySelector('.page-jump-input');const bs=[...c.querySelectorAll('.page-btn')];
  const mp=ji?parseInt(ji.max):1;
  function sa(p){bs.forEach(b=>{const n=parseInt(b.textContent);if(!isNaN(n))b.classList.toggle('active',n===p);});if(ji)ji.value=p;const pv=bs.find(b=>b.textContent==='‹');if(pv)pv.disabled=p<=1;const nx=bs.find(b=>b.textContent==='›');if(nx)nx.disabled=p>=mp;}
  c.addEventListener('click',e=>{if(e.target.classList.contains('page-btn')&&!e.target.disabled){const t=e.target.textContent;let cu=parseInt(ji?ji.value:'1')||1;if(t==='‹')cu=Math.max(1,cu-1);else if(t==='›')cu=Math.min(mp,cu+1);else cu=parseInt(t);sa(cu);}});
  if(ji)ji.addEventListener('keydown',e=>{if(e.key==='Enter'){let v=parseInt(ji.value);if(isNaN(v))v=1;v=Math.max(1,Math.min(mp,v));sa(v);}});
});
// Generic tabs
document.querySelectorAll('.tabs').forEach(tg=>tg.querySelectorAll('.tab').forEach(t=>{if(t.hasAttribute('data-chart-tab')||t.classList.contains('detail-tab')||t.hasAttribute('data-timeline-filter'))return;t.addEventListener('click',()=>{tg.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));t.classList.add('active');});}));
// Day selector
document.querySelectorAll('.day-selector').forEach(s=>s.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{s.querySelectorAll('button').forEach(x=>x.classList.remove('active'));b.classList.add('active');})));
// Quick filters
document.querySelectorAll('.quick-filters').forEach(g=>g.querySelectorAll('.quick-filter').forEach(f=>f.addEventListener('click',()=>{g.querySelectorAll('.quick-filter').forEach(x=>x.classList.remove('active'));f.classList.add('active');})));
// DB management
const ci=document.querySelector('.confirm-input');const db=document.querySelector('.danger-btn');
if(ci&&db)ci.addEventListener('input',()=>{db.disabled=ci.value.trim()!=='CLEAR ALL DATA';});
document.querySelectorAll('.danger-zone input[type="checkbox"]').forEach(cb=>cb.addEventListener('change',()=>{const ac=[...document.querySelectorAll('.danger-zone input[type="checkbox"]')].some(c=>c.checked);if(db&&!db.disabled)db.disabled=!ac;}));
