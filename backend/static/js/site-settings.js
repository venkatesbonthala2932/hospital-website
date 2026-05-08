/**
 * site-settings.js — CMS loader
 *
 * Fetches /api/site-settings once per session and applies values to any
 * element that has one of these attributes:
 *
 *   data-cms="key"          → sets element.textContent
 *   data-cms-src="key"      → sets element.src  (images)
 *   data-cms-href="key"     → sets element.href (links)
 *   data-cms-alt="key"      → sets element.alt  (images)
 *   data-cms-title="key"    → sets document.title suffix
 *
 * Also updates <title> tags that contain the hospital name.
 *
 * Cache: sessionStorage, 5-minute TTL so edits propagate quickly.
 */
(function () {
  const CACHE_KEY = 'aadityaa_site_settings';
  const CACHE_TTL = 5 * 60 * 1000; // 5 min

  // Default values shipped in HTML — these get globally replaced anywhere
  // they appear in text nodes, so pages that don't have data-cms attributes
  // (login, doctor pages, etc.) still pick up branding changes.
  const TEXT_REPLACEMENTS = {
    hospital_name:  ['Aadityaa Hospital', 'Aaditya Hospital'],
    nav_address:    ['PI/466, 8, ZP Rd, Phase 4, Teachers Colony, Hastinapuram, Hyderabad, 500070'],
    nav_hours:      ['Mon-Sat: 10:00 AM – 6:00 PM'],
    nav_phone:      ['+91 40 1234 5678'],
    contact_email:  ['info@aadityaahospital.com'],
    emergency_phone:['+91 40 9999 9999'],
  };

  // Remember what we've previously replaced TO, so subsequent renames
  // can swap "SHYAM Hospital" → "BABAJI Hospital" too.
  const APPLIED_KEY = 'aadityaa_applied_replacements';
  function getApplied() {
    try { return JSON.parse(sessionStorage.getItem(APPLIED_KEY) || '{}'); }
    catch (_) { return {}; }
  }
  function setApplied(m) {
    try { sessionStorage.setItem(APPLIED_KEY, JSON.stringify(m)); } catch (_) {}
  }

  function replaceInTextNodes(settings) {
    const root = document.body;
    if (!root) return;
    const previouslyApplied = getApplied();
    const replacements = [];

    Object.entries(TEXT_REPLACEMENTS).forEach(([key, defaults]) => {
      const newVal = settings[key];
      if (!newVal) return;
      // Original hardcoded defaults
      defaults.forEach(d => { if (d !== newVal) replacements.push([d, newVal]); });
      // Previously-applied value (if user changed multiple times)
      const prev = previouslyApplied[key];
      if (prev && prev !== newVal && !defaults.includes(prev)) {
        replacements.push([prev, newVal]);
      }
    });

    if (replacements.length) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode: n => n.parentNode && !['SCRIPT','STYLE','TEXTAREA'].includes(n.parentNode.nodeName)
          ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT
      });
      const nodes = []; let n; while ((n = walker.nextNode())) nodes.push(n);
      nodes.forEach(node => {
        let v = node.nodeValue;
        replacements.forEach(([from, to]) => {
          if (v.includes(from)) v = v.split(from).join(to);
        });
        if (v !== node.nodeValue) node.nodeValue = v;
      });
    }

    // Persist what we've now applied
    const applied = {};
    Object.keys(TEXT_REPLACEMENTS).forEach(k => { if (settings[k]) applied[k] = settings[k]; });
    setApplied(applied);
  }

  function apply(settings) {
    const name = settings['hospital_name'];

    // Update page title
    if (name) {
      if (document.title.includes('Aadityaa Hospital'))
        document.title = document.title.replace(/Aadityaa Hospital/g, name);
      if (document.title.includes('Aaditya Hospital'))
        document.title = document.title.replace(/Aaditya Hospital/g, name);
    }

    document.querySelectorAll('[data-cms]').forEach(el => {
      const val = settings[el.dataset.cms];
      if (val !== undefined) el.textContent = val;
    });

    document.querySelectorAll('[data-cms-src]').forEach(el => {
      const val = settings[el.dataset.cmsSrc];
      if (val) { el.src = val; el.alt = el.alt || ''; }
    });

    document.querySelectorAll('[data-cms-href]').forEach(el => {
      const val = settings[el.dataset.cmsHref];
      if (val) el.href = val;
    });

    document.querySelectorAll('[data-cms-alt]').forEach(el => {
      const val = settings[el.dataset.cmsAlt];
      if (val) el.alt = val;
    });

    // Catch-all: replace known default strings in text nodes
    replaceInTextNodes(settings);
  }

  async function load() {
    // Check cache
    try {
      const cached = sessionStorage.getItem(CACHE_KEY);
      if (cached) {
        const { ts, data } = JSON.parse(cached);
        if (Date.now() - ts < CACHE_TTL) { apply(data); return; }
      }
    } catch (_) {}

    try {
      const res = await fetch('/api/site-settings');
      if (!res.ok) return;
      const json = await res.json();
      const settings = json.settings || {};
      try {
        sessionStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: settings }));
      } catch (_) {}
      apply(settings);
    } catch (_) {}
  }

  // Expose so admin can bust the cache after saving
  window.SiteSettings = {
    reload: function () {
      try { sessionStorage.removeItem(CACHE_KEY); } catch (_) {}
      load();
    },
    getCache: function () {
      try {
        const c = sessionStorage.getItem(CACHE_KEY);
        return c ? JSON.parse(c).data : {};
      } catch (_) { return {}; }
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
