/**
 * rbac.js — Role-Based Access Control (frontend)
 *
 * Hierarchy:   admin (3) > doctor (2) > patient (1)
 * Admins can do anything; doctors can do doctor + patient stuff;
 * patients can only do patient stuff.
 *
 * It reads the role from two sources, in this priority:
 *   1. Firebase ID-token custom claim `role` (set by backend after registration
 *      or role change — fast, no API call)
 *   2. /api/auth/me  (fallback when claims aren't present yet)
 *
 * What it provides on every page:
 *   window.RBAC.getRole()              → 'admin' | 'doctor' | 'patient' | null
 *   window.RBAC.hasRole(r)             → strict equality
 *   window.RBAC.hasMinRole(r)          → hierarchical (admin ≥ doctor ≥ patient)
 *   window.RBAC.requireMinRole(r,opts) → redirects to /login.html?next=... if denied
 *
 * Declarative usage in HTML:
 *   <div data-min-role="doctor">…</div>     ← hidden for patients
 *   <button data-role="admin">…</button>    ← only admins see it (strict)
 *
 * Page guard via <meta>:
 *   <meta name="require-min-role" content="doctor">
 *   <meta name="require-role"     content="admin">
 *
 * The above will redirect unauthorised users to /login.html (or '/' if signed in
 * but wrong role) automatically on page load.
 */
(function () {
  const ROLE_LEVEL = { patient: 1, doctor: 2, admin: 3 };
  const DASHBOARDS = {
    admin:   '/admin-dashboard.html',
    doctor:  '/doctor-dashboard.html',
    patient: '/patient-dashboard.html',
  };

  let _role = null;
  let _user = null;
  let _readyResolve;
  const _ready = new Promise(r => { _readyResolve = r; });

  function levelOf(role) { return ROLE_LEVEL[(role || '').toLowerCase()] || 0; }

  async function loadRole() {
    const auth = (window._initFirebase && _initFirebase()) ||
                 (window.firebase && firebase.auth ? firebase.auth() : null);

    if (!auth) { _role = null; _user = null; _readyResolve(); applyDeclaratives(); return; }

    auth.onAuthStateChanged(async user => {
      _user = user;
      if (!user) {
        _role = null; window._currentRole = null;
        _readyResolve(); applyDeclaratives(); enforcePageGuard(); return;
      }
      try {
        // Prefer custom claim (no API call) — falls back to /api/auth/me
        const tokenResult = await user.getIdTokenResult();
        const claimRole   = tokenResult.claims && tokenResult.claims.role;
        if (claimRole) {
          _role = claimRole;
        } else {
          const token = await user.getIdToken();
          const res   = await fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } });
          const json  = await res.json();
          _role = json.user?.role || 'patient';
        }
      } catch (_) {
        _role = 'patient';
      }
      window._currentRole = _role;
      _readyResolve();
      applyDeclaratives();
      enforcePageGuard();
    });
  }

  function applyDeclaratives() {
    // Strict role match
    document.querySelectorAll('[data-role]').forEach(el => {
      const allowed = el.dataset.role.split(',').map(s => s.trim().toLowerCase());
      el.style.display = (_role && allowed.includes(_role)) ? '' : 'none';
    });
    // Hierarchical (min role)
    document.querySelectorAll('[data-min-role]').forEach(el => {
      const min = el.dataset.minRole.trim().toLowerCase();
      el.style.display = (levelOf(_role) >= levelOf(min)) ? '' : 'none';
    });
    // Hide things ONLY for signed-out users
    document.querySelectorAll('[data-signed-in-only]').forEach(el => {
      el.style.display = _user ? '' : 'none';
    });
    document.querySelectorAll('[data-signed-out-only]').forEach(el => {
      el.style.display = _user ? 'none' : '';
    });
  }

  function enforcePageGuard() {
    const minMeta = document.querySelector('meta[name="require-min-role"]');
    const strMeta = document.querySelector('meta[name="require-role"]');
    if (!minMeta && !strMeta) return;

    const here = window.location.pathname + window.location.search;
    const back = '?next=' + encodeURIComponent(here);

    if (!_user) { window.location.replace('/login.html' + back); return; }

    if (minMeta) {
      const min = minMeta.content.trim().toLowerCase();
      if (levelOf(_role) < levelOf(min)) {
        const target = DASHBOARDS[_role] || '/';
        window.location.replace(target);
      }
    }
    if (strMeta) {
      const allowed = strMeta.content.split(',').map(s => s.trim().toLowerCase());
      if (!allowed.includes(_role)) {
        const target = DASHBOARDS[_role] || '/';
        window.location.replace(target);
      }
    }
  }

  window.RBAC = {
    ready:  () => _ready,
    getRole: () => _role,
    getUser: () => _user,
    hasRole: r => _role === (r || '').toLowerCase(),
    hasMinRole: r => levelOf(_role) >= levelOf(r),
    requireMinRole: async (r, opts = {}) => {
      await _ready;
      if (levelOf(_role) >= levelOf(r)) return true;
      if (opts.redirect !== false) {
        const back = '?next=' + encodeURIComponent(window.location.pathname + window.location.search);
        window.location.replace(_user ? (DASHBOARDS[_role] || '/') : ('/login.html' + back));
      }
      return false;
    },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadRole);
  } else {
    loadRole();
  }
})();
