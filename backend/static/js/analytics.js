/**
 * analytics.js — Visit analytics renderer
 *
 * Usage from any page that has a container div with id="analytics-root":
 *   AHAnalytics.render({
 *     endpoint: '/api/admin/analytics' | '/api/doctor/analytics',
 *     authFetch:  your authenticated fetch wrapper (Bearer token),
 *     title:      'Patient Visits' (optional)
 *   });
 *
 * Renders:
 *   - 4 stat cards (Today, Week, Month, Year) with trend vs previous period
 *   - All-time count
 *   - Last-14-day mini bar chart
 *   - "Refresh" button to re-pull data
 */
(function () {
  function pct(curr, prev) {
    if (!prev) return curr > 0 ? '+∞%' : '0%';
    const change = ((curr - prev) / prev) * 100;
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(0)}%`;
  }

  function trendArrow(curr, prev) {
    if (curr > prev) return { icon: 'trending_up',   color: 'text-secondary', bg: 'bg-secondary/10' };
    if (curr < prev) return { icon: 'trending_down', color: 'text-tertiary',  bg: 'bg-tertiary/10' };
    return                  { icon: 'trending_flat', color: 'text-on-surface-variant', bg: 'bg-surface-container' };
  }

  function statCard({ label, current, previous, prevLabel, accent }) {
    const t = trendArrow(current, previous);
    return `
      <div class="bg-surface-container-lowest rounded-2xl p-5 editorial-shadow">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">${label}</p>
            <p class="font-headline text-4xl font-black ${accent || 'text-primary'} leading-none">${current}</p>
          </div>
          <div class="flex items-center gap-1 px-2.5 py-1 rounded-full ${t.bg} ${t.color} text-[11px] font-bold">
            <span class="material-symbols-outlined text-[14px]">${t.icon}</span>
            ${pct(current, previous)}
          </div>
        </div>
        <p class="text-xs text-on-surface-variant mt-3">
          ${prevLabel}: <strong>${previous}</strong>
        </p>
      </div>`;
  }

  function barChart(trend) {
    const max = Math.max(1, ...trend.map(d => d.count));
    return `
      <div class="bg-surface-container-lowest rounded-2xl p-5 editorial-shadow">
        <h3 class="font-headline text-sm font-bold mb-1 flex items-center gap-2">
          <span class="material-symbols-outlined text-primary text-[18px]">insights</span>
          Last 14 days
        </h3>
        <p class="text-xs text-on-surface-variant mb-4">Daily visit count.</p>
        <div class="flex items-end gap-1.5 h-32">
          ${trend.map(d => {
            const h   = Math.round((d.count / max) * 100);
            const lbl = new Date(d.date + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric' });
            const dow = new Date(d.date + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short' });
            return `
              <div class="flex-1 flex flex-col items-center gap-1 group">
                <div class="text-[10px] text-on-surface-variant font-semibold opacity-0 group-hover:opacity-100 transition-opacity">${d.count}</div>
                <div class="w-full bg-primary/70 hover:bg-primary rounded-t-md transition-colors relative" style="height: ${h}%" title="${d.date}: ${d.count} visits">
                </div>
                <div class="text-[9px] text-on-surface-variant text-center leading-tight">
                  ${lbl}<br>${dow}
                </div>
              </div>`;
          }).join('')}
        </div>
      </div>`;
  }

  async function render({ endpoint, authFetch, root = 'analytics-root', title = 'Patient Visit Analytics' }) {
    const el = document.getElementById(root);
    if (!el) return;
    el.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="font-headline text-lg font-bold">${title}</h2>
          <p class="text-xs text-on-surface-variant">How many patients have visited — compared to previous periods.</p>
        </div>
        <button id="ah-an-refresh" class="text-xs font-semibold text-primary border border-primary px-3 py-1.5 rounded-full hover:bg-primary/5 transition-colors flex items-center gap-1">
          <span class="material-symbols-outlined text-[14px]">refresh</span> Refresh
        </button>
      </div>
      <div id="ah-an-body" class="space-y-4">
        <p class="text-sm text-on-surface-variant text-center py-10">
          <span class="material-symbols-outlined text-3xl block mb-2" style="animation: spin 1s linear infinite">progress_activity</span>
          Loading analytics…
        </p>
      </div>`;

    async function load() {
      const body = document.getElementById('ah-an-body');
      try {
        const res  = await authFetch(endpoint);
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || 'Could not load analytics.');
        body.innerHTML = `
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            ${statCard({ label: 'Today',      current: json.today,      previous: json.yesterday,  prevLabel: 'Yesterday',  accent: 'text-primary' })}
            ${statCard({ label: 'This Week',  current: json.this_week,  previous: json.last_week,  prevLabel: 'Last week',  accent: 'text-secondary' })}
            ${statCard({ label: 'This Month', current: json.this_month, previous: json.last_month, prevLabel: 'Last month', accent: 'text-amber-600' })}
            ${statCard({ label: 'This Year',  current: json.this_year,  previous: json.last_year,  prevLabel: 'Last year',  accent: 'text-tertiary' })}
          </div>
          <div class="grid md:grid-cols-3 gap-3">
            <div class="bg-primary rounded-2xl p-5 editorial-shadow text-white">
              <p class="text-[10px] font-bold uppercase tracking-widest opacity-80 mb-1">All Time</p>
              <p class="font-headline text-4xl font-black leading-none">${json.all_time}</p>
              <p class="text-xs opacity-70 mt-3">Total visits ever recorded.</p>
            </div>
            <div class="md:col-span-2">
              ${barChart(json.trend_14d || [])}
            </div>
          </div>
          <p class="text-[10px] text-on-surface-variant text-right">As of ${json.as_of}.</p>`;
      } catch (e) {
        body.innerHTML = `<p class="text-tertiary text-sm text-center py-6">${e.message}</p>`;
      }
    }

    document.getElementById('ah-an-refresh').addEventListener('click', load);
    load();
  }

  window.AHAnalytics = { render };
})();
