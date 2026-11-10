/* Shared state, filters, theme and formatting helpers. Loaded on every page. */
(function (T) {
  "use strict";

  var FILTER_KEY = "telemetry-filters";
  var THEME_KEY = "telemetry-theme";
  var DAY_MS = 86400000;
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  // Pages without charts (About) ship no data, only the theme toggle.
  var dataNode = document.getElementById("dashboard-data");
  var data = dataNode
    ? JSON.parse(dataNode.textContent)
    : { meta: { firstDay: "2000-01-01", lastDay: "2000-01-01" }, sites: [], daily: [], downtime: [], tagDaily: [], flatlines: [] };
  var siteById = {};
  data.sites.forEach(function (site, index) {
    site.color = "var(--s" + (index + 1) + ")";
    siteById[site.id] = site;
  });
  var listeners = [];

  // Dates arrive as ISO strings. Plain day strings compare correctly as text.
  function parseDay(iso) {
    return new Date(iso.slice(0, 10) + "T00:00:00Z");
  }

  function addDays(iso, count) {
    return new Date(parseDay(iso).getTime() + count * DAY_MS).toISOString().slice(0, 10);
  }

  var span = Math.round((parseDay(data.meta.lastDay) - parseDay(data.meta.firstDay)) / DAY_MS) + 1;
  var periods = [7, 14, 30].filter(function (days) { return days < span; }).concat(span);

  function defaults() {
    return { days: span, sites: data.sites.map(function (site) { return site.id; }) };
  }

  function loadState() {
    var fallback = defaults();
    try {
      var saved = JSON.parse(localStorage.getItem(FILTER_KEY) || "null");
      if (!saved) { return fallback; }
      var sites = (saved.sites || []).filter(function (id) { return siteById[id]; });
      return {
        days: periods.indexOf(saved.days) >= 0 ? saved.days : fallback.days,
        sites: sites.length ? sites : fallback.sites
      };
    } catch (error) {
      return fallback;
    }
  }

  var state = loadState();

  function saveState() {
    try { localStorage.setItem(FILTER_KEY, JSON.stringify(state)); } catch (error) { /* storage can be blocked */ }
  }

  // The slice of data every chart, figure and table on the page is drawn from.
  function selection() {
    var from = addDays(data.meta.lastDay, -(state.days - 1));
    var keep = state.sites;
    function inSites(row) { return keep.indexOf(row.site) >= 0; }
    return {
      from: from,
      to: data.meta.lastDay,
      days: state.days,
      sites: data.sites.filter(function (site) { return keep.indexOf(site.id) >= 0; }),
      allSites: keep.length === data.sites.length,
      daily: data.daily.filter(function (row) { return inSites(row) && row.date >= from; }),
      downtime: data.downtime.filter(function (row) { return inSites(row) && row.localStart.slice(0, 10) >= from; }),
      tagDaily: data.tagDaily.filter(function (row) { return inSites(row) && row.date >= from; }),
      flatlines: data.flatlines.filter(function (row) { return inSites(row) && row.start.slice(0, 10) >= from; })
    };
  }

  // Formatting
  var numberFormats = {};
  function number(value, digits) {
    digits = digits || 0;
    if (value === null || value === undefined || Number.isNaN(value)) { return "n/a"; }
    numberFormats[digits] = numberFormats[digits] || new Intl.NumberFormat("en-GB", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
    return numberFormats[digits].format(value);
  }

  function percent(ratio, digits) {
    return ratio === null || ratio === undefined || Number.isNaN(ratio) ? "n/a" : number(ratio * 100, digits === undefined ? 1 : digits) + " %";
  }

  function shortDate(iso) {
    return parseDay(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  }

  function dateTime(iso) {
    var date = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso + "Z");
    return date.toLocaleString("en-GB", {
      day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC"
    });
  }

  var TAG_LABELS = { STACK_NOX: "Stack NOx", STACK_CO: "Stack CO" };
  function tagLabel(name) {
    if (TAG_LABELS[name]) { return TAG_LABELS[name]; }
    var text = name.toLowerCase().replace(/_/g, " ");
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  // Small DOM builder. Text always goes through textContent, never innerHTML.
  function h(tag, props) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (key) {
      if (key === "text") { node.textContent = props[key]; }
      else if (key === "class") { node.className = props[key]; }
      else if (key === "style") { node.setAttribute("style", props[key]); }
      else { node.setAttribute(key, props[key]); }
    });
    for (var i = 2; i < arguments.length; i += 1) {
      var child = arguments[i];
      if (child === null || child === undefined) { continue; }
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  // Animates a figure when a filter changes it. The first draw is instant.
  function setNumber(element, target, format) {
    var from = element._value;
    element._value = target;
    var instant = from === undefined || from === null || target === null || from === target || reducedMotion.matches;
    if (instant) { element.textContent = format(target); return; }
    var start = performance.now();
    var duration = 350;
    function step(now) {
      if (element._value !== target) { return; }
      var progress = Math.min((now - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = format(from + (target - from) * eased);
      if (progress < 1) { requestAnimationFrame(step); }
    }
    requestAnimationFrame(step);
  }

  function downloadCsv(filename, columns, rows) {
    function cell(value) {
      var text = value === null || value === undefined ? "" : String(value);
      return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
    }
    var lines = [columns.map(function (column) { return cell(column.label); }).join(",")];
    rows.forEach(function (row) {
      lines.push(columns.map(function (column) { return cell(column.value(row)); }).join(","));
    });
    var blob = new Blob([lines.join("\n") + "\n"], { type: "text/csv;charset=utf-8" });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
  }

  // Change notifications
  function onChange(listener) { listeners.push(listener); }
  function emit() { listeners.forEach(function (listener) { listener(); }); }

  // Theme
  function syncThemeButton() {
    var button = document.getElementById("theme-toggle");
    if (!button) { return; }
    var dark = document.documentElement.dataset.theme === "dark";
    button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  }

  function toggleTheme() {
    var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(THEME_KEY, next); } catch (error) { /* storage can be blocked */ }
    syncThemeButton();
    emit();
  }

  // Filter controls
  function buildControls() {
    var period = document.getElementById("period");
    var chips = document.getElementById("site-chips");
    var reset = document.getElementById("reset-filters");
    if (!period || !chips || !reset) { return; }

    function draw() {
      period.replaceChildren.apply(period, periods.map(function (days) {
        var label = days === span && days > 30 ? "All " + days + " days" : days + " days";
        var button = h("button", { type: "button", role: "radio", "aria-checked": String(days === state.days), text: label });
        button.addEventListener("click", function () {
          state.days = days;
          saveState();
          draw();
          emit();
        });
        return button;
      }));

      chips.replaceChildren.apply(chips, data.sites.map(function (site) {
        var active = state.sites.indexOf(site.id) >= 0;
        var chip = h("button", {
          type: "button", class: "chip", "aria-pressed": String(active),
          title: site.name + ", " + site.country, style: "--dot: " + site.color
        }, h("i"), site.name);
        chip.addEventListener("click", function () {
          var next = active ? state.sites.filter(function (id) { return id !== site.id; }) : state.sites.concat(site.id);
          if (!next.length) { return; }
          state.sites = data.sites.map(function (item) { return item.id; }).filter(function (id) { return next.indexOf(id) >= 0; });
          saveState();
          draw();
          emit();
        });
        return chip;
      }));
    }

    reset.addEventListener("click", function () {
      state = defaults();
      saveState();
      draw();
      emit();
    });
    draw();
  }

  function start() {
    var toggle = document.getElementById("theme-toggle");
    if (toggle) { toggle.addEventListener("click", toggleTheme); }
    syncThemeButton();
    buildControls();
  }

  if (!dataNode) { document.addEventListener("DOMContentLoaded", start); }

  T.data = data;
  T.siteById = siteById;
  T.selection = selection;
  T.onChange = onChange;
  T.start = start;
  T.h = h;
  T.setNumber = setNumber;
  T.downloadCsv = downloadCsv;
  T.addDays = addDays;
  T.fmt = { number: number, percent: percent, shortDate: shortDate, dateTime: dateTime, tag: tagLabel };
})(window.Telemetry = window.Telemetry || {});
