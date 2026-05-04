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
