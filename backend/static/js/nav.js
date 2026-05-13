/**
 * nav.js — Shared navigation logic for all Aadityaa Hospital pages
 *
 * Include AFTER api.js on every page:
 *   <script src="/static/js/nav.js"></script>
 *
 * What this does:
 *  1. Fixes all href="#" nav links to real page URLs
 *  2. Highlights the active nav link for the current page
 *  3. Makes the hospital logo / name a clickable link to "/"
 *  4. Makes every "Book Appointment" button redirect to /departments.html
 *  5. Adds auth-aware nav: shows login/logout + dashboard link based on role
 *  6. Footer links are also wired up
 */

// ─── Page URL map ─────────────────────────────────────────────────────────────
const PAGE_URLS = {
  'Home':             '/',
  'About Us':         '/about.html',
  'Departments':      '/departments.html',
  'Doctors':          '/doctors.html',
  'Health Packages':  '/health-packages.html',
};

// Map current path → which nav label is "active"
const PATH_TO_NAV = {
  '/':                     'Home',
  '/index.html':            'Home',
  '/about.html':            'About Us',
  '/departments.html':      'Departments',
  '/doctors.html':          'Doctors',
  '/health-packages.html':  'Health Packages',
};

// Dashboard URL per role
const DASHBOARD_URL = {
  admin:   '/admin-dashboard.html',
  doctor:  '/doctor-dashboard.html',
  patient: '/patient-dashboard.html',
};

// ─── Run on DOM ready ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  fixNavLinks();
  fixLogoLink();
  fixBookButtons();
  fixFooterLinks();
  initAuthNav();
  initMobileMenu();
});

// ─── Fix nav <a> href values ──────────────────────────────────────────────────
function fixNavLinks() {
  const currentPath = window.location.pathname;
  const activeName  = PATH_TO_NAV[currentPath] || '';

  // Find all <a> tags inside header nav
  document.querySelectorAll('header nav a').forEach(link => {
    const text = link.textContent.trim();
    if (PAGE_URLS[text]) {
      link.href = PAGE_URLS[text];

      // Mark active link
      if (text === activeName) {
        link.classList.add('text-[#00535B]', 'font-bold', 'border-b-2', 'border-[#00535B]', 'pb-1');
        link.classList.remove('text-slate-600', 'dark:text-slate-400');
      }
    }
  });
}

// ─── Make hospital name / logo link to homepage ───────────────────────────────
function fixLogoLink() {
  // The logo area contains the "A" icon + "Aadityaa Hospital" text inside header
  const headerLogoArea = document.querySelector('header nav > div');
  if (headerLogoArea && headerLogoArea.tagName !== 'A') {
    const wrapper      = document.createElement('a');
    wrapper.href       = '/';
    wrapper.className  = 'flex items-center gap-2 cursor-pointer';
    wrapper.innerHTML  = headerLogoArea.innerHTML;
    headerLogoArea.replaceWith(wrapper);
  }
}

// ─── Every "Book Appointment" button → /departments.html ─────────────────────
function fixBookButtons() {
  document.querySelectorAll('button, a').forEach(el => {
    const text = el.textContent.trim();
    if (text === 'Book Appointment') {
      if (el.tagName === 'A') {
        el.href = '/departments.html';
      } else {
        el.addEventListener('click', () => window.location.href = '/departments.html');
      }
    }
  });
}

// ─── Wire footer links ────────────────────────────────────────────────────────
function fixFooterLinks() {
  const FOOTER_MAP = {
    'Book Appointment': '/departments.html',
    'Find a Doctor':    '/doctors.html',
    'Health Packages':  '/health-packages.html',
  };

  document.querySelectorAll('footer a').forEach(link => {
    const text = link.textContent.trim();
    if (FOOTER_MAP[text]) link.href = FOOTER_MAP[text];
  });
}

// ─── Auth-aware nav: login button + dashboard link ───────────────────────────
function initAuthNav() {
  const auth = _initFirebase();

  // Find the nav right-side button area
  const navButtonArea = document.querySelector('header nav > div:last-child');
  if (!navButtonArea) return;

  // Add a Dashboard link + Login/Logout button (injected before existing buttons)
  const authSlot = document.createElement('div');
  authSlot.id    = 'nav-auth-slot';
  authSlot.className = 'flex items-center gap-2';
  navButtonArea.prepend(authSlot);

  function renderAuthSlot(user) {
    if (!user) {
      // Not logged in — show Login link
      authSlot.innerHTML = `
        <a href="/login.html"
           class="text-primary font-semibold text-sm hover:underline hidden lg:block">
          Login
        </a>`;
    } else {
      // Logged in — show Dashboard + Logout
      const role     = window._currentRole || 'patient';
      const dashURL  = DASHBOARD_URL[role] || '/patient-dashboard.html';
      const name     = user.displayName || user.email.split('@')[0];

      authSlot.innerHTML = `
        <a href="${dashURL}"
           class="text-sm font-semibold text-primary border border-primary px-3 py-1.5 rounded-full hover:bg-primary hover:text-white transition-colors hidden lg:flex items-center gap-1">
          <span class="material-symbols-outlined text-[16px]">dashboard</span>
          Dashboard
        </a>
        <span class="text-xs text-on-surface-variant hidden lg:block">Hi, ${name.split(' ')[0]}</span>
        <button id="nav-logout-btn"
                class="text-xs text-on-surface-variant hover:text-tertiary transition-colors hidden lg:block">
          Logout
        </button>`;

      document.getElementById('nav-logout-btn')?.addEventListener('click', async () => {
        await Auth.logout();
      });
    }
  }

  if (auth) {
    // Listen for auth state changes — this fires immediately with the current state
    auth.onAuthStateChanged(async (user) => {
      if (user) {
        // Fetch role from backend so dashboard link is correct
        try {
          const token = await user.getIdToken();
          const res   = await fetch('/api/auth/me', {
            headers: { Authorization: `Bearer ${token}` }
          });
          const json = await res.json();
          window._currentRole = json.user?.role || 'patient';
        } catch {
          window._currentRole = 'patient';
        }
      }
      renderAuthSlot(user);
    });
  } else {
    // Firebase SDK not loaded — show Login link as fallback
    renderAuthSlot(null);
  }
}

// ─── Mobile / tablet hamburger menu (works on every page automatically) ─────
function initMobileMenu() {
  const header = document.querySelector('header');
  if (!header) return;

  const nav = header.querySelector('nav');
  if (!nav) return;

  // The desktop nav links live in a div with "hidden lg:flex" – find it.
  const navLinksContainer = nav.querySelector('div.hidden.lg\\:flex')
                          || Array.from(nav.querySelectorAll('div')).find(d => d.querySelector('a[href]'));
  const rightButtonArea   = nav.querySelector('div:last-child');
  if (!rightButtonArea) return;

  // Tighten the right-side buttons on small screens so we have room for the burger
  rightButtonArea.classList.add('gap-2', 'md:gap-3');

  // Hide redundant icon buttons (call/schedule) on small screens — the drawer has them
  rightButtonArea.querySelectorAll('button').forEach(btn => {
    const txt = btn.textContent.trim();
    if (txt === 'call' || txt === 'schedule') {
      btn.classList.add('hidden', 'md:inline-flex');
    }
  });

  // Make the visible Book Appointment button smaller on phones
  rightButtonArea.querySelectorAll('button, a').forEach(el => {
    if (el.textContent.trim() === 'Book Appointment') {
      el.classList.remove('px-6', 'py-2.5', 'text-sm');
      el.classList.add('px-3', 'py-2', 'text-xs', 'md:px-5', 'md:py-2.5', 'md:text-sm');
    }
  });

  // Build the hamburger button
  const burger = document.createElement('button');
  burger.id = 'nav-burger';
  burger.setAttribute('aria-label', 'Open menu');
  burger.className = 'lg:hidden w-10 h-10 rounded-full hover:bg-surface-container flex items-center justify-center text-primary flex-shrink-0';
  burger.innerHTML = '<span class="material-symbols-outlined">menu</span>';
  rightButtonArea.appendChild(burger);

  // Collect link list (text + URL) from nav.js page map, plus auth-aware extras
  const drawer = document.createElement('div');
  drawer.id = 'nav-drawer';
  drawer.className = 'fixed inset-0 z-[200] hidden';
  drawer.innerHTML = `
    <div id="nav-drawer-backdrop" class="absolute inset-0 bg-black/40 backdrop-blur-sm"></div>
    <aside class="absolute top-0 right-0 h-full w-[85%] max-w-xs bg-white shadow-2xl flex flex-col transform translate-x-full transition-transform duration-300" id="nav-drawer-panel">
      <div class="flex items-center justify-between px-5 py-4 border-b border-outline-variant">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-white text-sm font-black">A</div>
          <span class="font-bold text-primary text-sm tracking-tighter" data-cms="hospital_name">Aadityaa Hospital</span>
        </div>
        <button id="nav-drawer-close" aria-label="Close menu"
          class="w-9 h-9 rounded-full hover:bg-surface-container flex items-center justify-center text-on-surface-variant">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>
      <nav class="flex-1 overflow-y-auto py-3">
        ${Object.entries(PAGE_URLS).map(([label, url]) => `
          <a href="${url}" class="nav-drawer-link flex items-center gap-3 px-5 py-3 text-sm font-semibold text-on-surface hover:bg-surface-container hover:text-primary transition-colors">
            <span class="material-symbols-outlined text-[20px] text-primary/70">${iconFor(label)}</span>
            ${label}
          </a>`).join('')}
        <a href="/insurance.html" class="nav-drawer-link flex items-center gap-3 px-5 py-3 text-sm font-semibold text-on-surface hover:bg-surface-container hover:text-primary transition-colors">
          <span class="material-symbols-outlined text-[20px] text-primary/70">health_metrics</span>
          Insurance
        </a>
      </nav>
      <div id="nav-drawer-auth" class="border-t border-outline-variant p-4 space-y-2">
        <!-- Login / Dashboard / Logout injected by auth code -->
      </div>
      <div class="px-5 py-4 border-t border-outline-variant text-xs text-on-surface-variant space-y-1">
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-[14px]">phone</span>
          <a href="tel:+914012345678" data-cms="nav_phone" class="hover:text-primary">+91 40 1234 5678</a>
        </div>
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-[14px]">schedule</span>
          <span data-cms="nav_hours">Mon-Sat: 10:00 AM – 6:00 PM</span>
        </div>
      </div>
    </aside>`;
  document.body.appendChild(drawer);

  const panel = drawer.querySelector('#nav-drawer-panel');
  function openDrawer() {
    drawer.classList.remove('hidden');
    requestAnimationFrame(() => panel.classList.remove('translate-x-full'));
    document.body.style.overflow = 'hidden';
  }
  function closeDrawer() {
    panel.classList.add('translate-x-full');
    document.body.style.overflow = '';
    setTimeout(() => drawer.classList.add('hidden'), 300);
  }
  burger.addEventListener('click', openDrawer);
  drawer.querySelector('#nav-drawer-close').addEventListener('click', closeDrawer);
  drawer.querySelector('#nav-drawer-backdrop').addEventListener('click', closeDrawer);

  // Highlight the active link in the drawer too
  const here = window.location.pathname;
  drawer.querySelectorAll('.nav-drawer-link').forEach(a => {
    if (a.getAttribute('href') === here ||
        (here === '/' && a.getAttribute('href') === '/') ||
        (here === '/index.html' && a.getAttribute('href') === '/')) {
      a.classList.add('bg-primary/5', 'text-primary', 'border-l-4', 'border-primary');
      a.classList.remove('text-on-surface');
    }
  });

  // Fill auth slot in the drawer
  renderDrawerAuth();

  // Re-render auth slot whenever Firebase auth state changes (only if api.js loaded firebase)
  if (window.firebase && firebase.auth) {
    firebase.auth().onAuthStateChanged(() => renderDrawerAuth());
  }
}

function iconFor(label) {
  return {
    'Home':            'home',
    'About Us':        'info',
    'Departments':     'medical_services',
    'Doctors':         'stethoscope',
    'Health Packages': 'health_and_safety',
  }[label] || 'chevron_right';
}

function renderDrawerAuth() {
  const slot = document.getElementById('nav-drawer-auth');
  if (!slot) return;
  const user = (window.firebase && firebase.auth) ? firebase.auth().currentUser : null;
  if (!user) {
    slot.innerHTML = `
      <a href="/login.html" class="block w-full bg-primary text-white py-3 rounded-full text-center font-bold text-sm hover:opacity-90">
        Login / Register
      </a>`;
  } else {
    const role    = window._currentRole || 'patient';
    const dashURL = DASHBOARD_URL[role] || '/patient-dashboard.html';
    const name    = (user.displayName || user.email || '').split(' ')[0].split('@')[0];
    slot.innerHTML = `
      <a href="${dashURL}" class="block w-full bg-primary text-white py-3 rounded-full text-center font-bold text-sm hover:opacity-90 flex items-center justify-center gap-2">
        <span class="material-symbols-outlined text-[18px]">dashboard</span> My Dashboard
      </a>
      <div class="flex items-center justify-between px-1">
        <span class="text-xs text-on-surface-variant">Signed in as <strong>${name}</strong></span>
        <button id="drawer-logout-btn" class="text-xs font-semibold text-tertiary hover:underline">Logout</button>
      </div>`;
    document.getElementById('drawer-logout-btn')?.addEventListener('click', async () => {
      if (window.Auth) await Auth.logout(); else location.href = '/login.html';
    });
  }
}

// ─── Custom confirm + alert modal (replaces native confirm/alert) ───────────
// Available globally on every page that loads nav.js:
//   await window.confirmModal({title, message, confirmText, danger})
//   await window.alertModal({title, message, type:'error'|'success'|'info'})
(function () {
  function ensureModal() {
    if (document.getElementById('ah-confirm-modal')) return;
    const div = document.createElement('div');
    div.id = 'ah-confirm-modal';
    div.className = 'hidden fixed inset-0 z-[9998] flex items-center justify-center p-4';
    div.innerHTML = `
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" id="ah-cm-backdrop"></div>
      <div class="bg-white rounded-3xl w-full max-w-md p-7 relative shadow-2xl">
        <div class="flex items-start gap-4">
          <div id="ah-cm-icon-wrap" class="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 bg-tertiary/10">
            <span id="ah-cm-icon" class="material-symbols-outlined text-tertiary">warning</span>
          </div>
          <div class="flex-1 min-w-0">
            <h3 id="ah-cm-title" class="font-bold text-lg mb-1" style="font-family:Manrope">Are you sure?</h3>
            <p id="ah-cm-message" class="text-sm text-on-surface-variant leading-relaxed"></p>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-6" id="ah-cm-buttons">
          <button id="ah-cm-cancel" class="px-5 py-2.5 rounded-full text-sm font-bold text-on-surface-variant hover:bg-surface-container">Cancel</button>
          <button id="ah-cm-ok" class="px-5 py-2.5 rounded-full text-sm font-bold bg-tertiary text-white hover:opacity-90">Confirm</button>
        </div>
      </div>`;
    document.body.appendChild(div);
  }
  function styleByKind(kind, danger) {
    const icon  = document.getElementById('ah-cm-icon');
    const wrap  = document.getElementById('ah-cm-icon-wrap');
    const okBtn = document.getElementById('ah-cm-ok');
    const map = {
      error:   { name: 'error',         wrap: 'bg-tertiary/10', text: 'text-tertiary', btn: 'bg-tertiary' },
      success: { name: 'check_circle',  wrap: 'bg-secondary/10', text: 'text-secondary', btn: 'bg-secondary' },
      info:    { name: 'info',          wrap: 'bg-primary/10',   text: 'text-primary',  btn: 'bg-primary'  },
      warn:    { name: 'warning',       wrap: 'bg-tertiary/10',  text: 'text-tertiary', btn: 'bg-tertiary' },
    };
    const s = map[kind] || map.info;
    wrap.className = `w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 ${s.wrap}`;
    icon.className = `material-symbols-outlined ${s.text}`;
    icon.textContent = s.name;
    okBtn.className = `px-5 py-2.5 rounded-full text-sm font-bold text-white hover:opacity-90 ${danger ? 'bg-tertiary' : s.btn}`;
  }
  window.confirmModal = function({title='Are you sure?', message='', confirmText='Confirm', cancelText='Cancel', danger=true, kind=danger?'warn':'info'} = {}) {
    ensureModal();
    return new Promise(resolve => {
      const m = document.getElementById('ah-confirm-modal');
      document.getElementById('ah-cm-title').textContent   = title;
      document.getElementById('ah-cm-message').textContent = message;
      document.getElementById('ah-cm-ok').textContent      = confirmText;
      document.getElementById('ah-cm-cancel').textContent  = cancelText;
      document.getElementById('ah-cm-cancel').style.display = '';
      styleByKind(kind, danger);
      m.classList.remove('hidden');
      const cleanup = () => {
        m.classList.add('hidden');
        document.getElementById('ah-cm-ok').onclick     = null;
        document.getElementById('ah-cm-cancel').onclick = null;
        document.getElementById('ah-cm-backdrop').onclick = null;
      };
      document.getElementById('ah-cm-ok').onclick     = () => { cleanup(); resolve(true); };
      document.getElementById('ah-cm-cancel').onclick = () => { cleanup(); resolve(false); };
      document.getElementById('ah-cm-backdrop').onclick = () => { cleanup(); resolve(false); };
    });
  };
  window.alertModal = function({title='Notice', message='', kind='info', confirmText='OK'} = {}) {
    ensureModal();
    return new Promise(resolve => {
      const m = document.getElementById('ah-confirm-modal');
      document.getElementById('ah-cm-title').textContent   = title;
      document.getElementById('ah-cm-message').textContent = message;
      document.getElementById('ah-cm-ok').textContent      = confirmText;
      document.getElementById('ah-cm-cancel').style.display = 'none';
      styleByKind(kind, false);
      m.classList.remove('hidden');
      const cleanup = () => {
        m.classList.add('hidden');
        document.getElementById('ah-cm-cancel').style.display = '';
        document.getElementById('ah-cm-ok').onclick = null;
        document.getElementById('ah-cm-backdrop').onclick = null;
      };
      document.getElementById('ah-cm-ok').onclick     = () => { cleanup(); resolve(); };
      document.getElementById('ah-cm-backdrop').onclick = () => { cleanup(); resolve(); };
    });
  };
})();

// ─── Utility: show a toast notification ──────────────────────────────────────
// Available globally so other page scripts can call: showToast('Saved!', 'success')
function showToast(message, type = 'info') {
  const existing = document.getElementById('ah-toast');
  if (existing) existing.remove();

  const colors = {
    success: 'bg-primary text-white',
    error:   'bg-tertiary text-white',
    info:    'bg-surface-container-high text-on-surface',
  };

  const toast = document.createElement('div');
  toast.id        = 'ah-toast';
  toast.className = `fixed bottom-6 left-1/2 -translate-x-1/2 px-6 py-3 rounded-full text-sm font-semibold shadow-xl z-[9999] transition-all ${colors[type] || colors.info}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => toast.remove(), 3500);
}

// ─── Utility: redirect to login if not authenticated ─────────────────────────
// Pages that require login can call: requireLogin()
async function requireLogin(redirectBack = true) {
  const auth = _initFirebase();
  if (!auth) return false;

  return new Promise(resolve => {
    auth.onAuthStateChanged(user => {
      if (user) {
        resolve(true);
      } else {
        const back = redirectBack ? `?next=${encodeURIComponent(window.location.pathname + window.location.search)}` : '';
        window.location.href = `/login.html${back}`;
        resolve(false);
      }
    });
  });
}
