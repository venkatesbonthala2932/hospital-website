/**
 * server-time.js
 * Fetches the authoritative server date and applies it as the `min` attribute
 * on every <input type="date"> that has data-server-min="today|tomorrow".
 *
 * This prevents users from selecting past dates even if they spoof their
 * device clock — all real booking validation is also done server-side.
 *
 * Usage in HTML:
 *   <input type="date" data-server-min="tomorrow" ...>
 *   <input type="date" data-server-min="today"    ...>
 *
 *   <script src="/static/js/server-time.js"></script>
 */
(async () => {
  try {
    const res  = await fetch('/api/server-time');
    const data = await res.json();

    document.querySelectorAll('input[type="date"][data-server-min]').forEach(el => {
      const which = el.dataset.serverMin;
      if (which === 'tomorrow') el.min = data.tomorrow;
      else if (which === 'today') el.min = data.today;
    });

    // Expose globally so inline JS can use it
    window._serverDate     = data.today;
    window._serverTomorrow = data.tomorrow;
  } catch (_) {
    // If server-time fails, fall back to client date (best effort)
    const today    = new Date();
    const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
    const fmt = d => d.toISOString().slice(0, 10);
    window._serverDate     = fmt(today);
    window._serverTomorrow = fmt(tomorrow);
    document.querySelectorAll('input[type="date"][data-server-min]').forEach(el => {
      el.min = el.dataset.serverMin === 'today' ? window._serverDate : window._serverTomorrow;
    });
  }
})();
