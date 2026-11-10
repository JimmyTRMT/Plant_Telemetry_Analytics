/* Plotly figures. Each function takes the current selection and draws into one element. */
(function (T) {
  "use strict";

  var CONFIG = { displayModeBar: false, responsive: true };
  var CATEGORIES = {
    short_trip: { label: "Short trip", color: "--warn" },
    extended_stop: { label: "Extended stop", color: "--serious" },
    long_shutdown: { label: "Long shutdown", color: "--critical" }
  };

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function siteColor(site) {
    return css("--s" + (T.data.sites.indexOf(T.siteById[site.id]) + 1));
  }

  function isDark() {
    return document.documentElement.dataset.theme === "dark";
  }

  // One blue ramp for magnitude. In dark mode the low end sinks into the surface.
  function sequentialScale() {
    return isDark()
      ? [[0, "#1c2a52"], [0.5, "#1c5cab"], [1, "#5598e7"]]
      : [[0, "#d9e8fb"], [0.5, "#6da7ec"], [1, "#2a78d6"]];
  }

  function baseLayout(extra) {
    var family = css("--font");
    var layout = {
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: family, size: 13, color: css("--ink-2") },
      margin: { l: 56, r: 16, t: 8, b: 44 },
      showlegend: false,
      hoverlabel: {
        bgcolor: css("--surface"),
        bordercolor: css("--line"),
        font: { family: family, size: 13, color: css("--ink") }
      },
      xaxis: { gridcolor: css("--line"), linecolor: css("--line"), zeroline: false, tickfont: { color: css("--muted") }, fixedrange: true, automargin: true },
      yaxis: { gridcolor: css("--line"), linecolor: css("--line"), zeroline: false, tickfont: { color: css("--muted") }, fixedrange: true, automargin: true }
    };
    Object.keys(extra || {}).forEach(function (key) {
      var value = extra[key];
      layout[key] = value && typeof value === "object" && !Array.isArray(value) && layout[key]
        ? Object.assign({}, layout[key], value)
        : value;
    });
    return layout;
  }

  function colorbar(suffix) {
    return { thickness: 12, len: 0.9, outlinewidth: 0, ticksuffix: suffix, tickfont: { color: css("--muted") } };
  }

  function sized(id, height) {
    document.getElementById(id).style.height = height + "px";
  }

  function draw(id, traces, layout) {
    Plotly.react(id, traces, layout, CONFIG);
  }

  function empty(id, message) {
    draw(id, [], baseLayout({
      xaxis: { visible: false },
      yaxis: { visible: false },
      annotations: [{ text: message, showarrow: false, font: { size: 14, color: css("--muted") } }]
    }));
  }

  function unique(values) {
    return values.filter(function (value, index) { return values.indexOf(value) === index; }).sort();
  }

  function narrow(id) {
    var el = document.getElementById(id);
    return !!el && el.clientWidth < 560;
  }

  function energyTrend(sel) {
    var traces = sel.sites.map(function (site) {
      var rows = sel.daily.filter(function (row) { return row.site === site.id; });
      return {
        type: "scatter", mode: "lines", name: site.name,
        x: rows.map(function (row) { return row.date; }),
        y: rows.map(function (row) { return row.energyMwh; }),
        line: { color: siteColor(site), width: 2.6 },
        hovertemplate: "%{y:,.0f} MWh"
      };
    });
    draw("chart-energy", traces, baseLayout({
      hovermode: "x unified",
      showlegend: true,
      legend: { orientation: "h", x: 0, y: 1, yanchor: "bottom", font: { color: css("--ink") } },
      margin: { t: narrow("chart-energy") ? 64 : 36 },
      xaxis: { tickformat: "%d %b", hoverformat: "%a %d %b" },
      yaxis: { title: { text: "MWh per day" }, rangemode: "tozero" }
    }));
  }

  function availabilityHeatmap(sel) {
    var dates = unique(sel.daily.map(function (row) { return row.date; }));
    if (!dates.length) { empty("chart-heatmap", "No complete days in this period"); return; }
    var lookup = {};
    var values = [];
    sel.daily.forEach(function (row) {
      var hours = row.runningHours + row.stoppedHours;
      if (hours > 0) {
        lookup[row.site + row.date] = (row.runningHours / hours) * 100;
        values.push(lookup[row.site + row.date]);
      }
    });
    var floor = Math.min(80, Math.floor(Math.min.apply(null, values) / 10) * 10);
    var z = sel.sites.map(function (site) {
      return dates.map(function (date) { return lookup[site.id + date] === undefined ? null : lookup[site.id + date]; });
    });
    sized("chart-heatmap", 110 + 62 * sel.sites.length);
    draw("chart-heatmap", [{
      type: "heatmap", x: dates, y: sel.sites.map(function (site) { return site.name; }), z: z,
      zmin: floor, zmax: 100, xgap: 2, ygap: 2, colorscale: sequentialScale(), colorbar: colorbar(" %"),
      hovertemplate: "%{y}, %{x|%d %b}<br>%{z:.0f} % of hours running<extra></extra>"
    }], baseLayout({ xaxis: { tickformat: "%d %b" }, yaxis: { autorange: "reversed", tickfont: { color: css("--ink") } } }));
  }

  function downtimeTimeline(sel) {
    var names = sel.sites.map(function (site) { return site.name; });
    var nameById = {};
    sel.sites.forEach(function (site) { nameById[site.id] = site.name; });
    var traces = Object.keys(CATEGORIES).map(function (key) {
      var rows = sel.downtime.filter(function (row) { return row.category === key; });
      var color = css(CATEGORIES[key].color);
      return {
        type: "bar", orientation: "h", name: CATEGORIES[key].label,
        y: rows.map(function (row) { return nameById[row.site]; }),
        x: rows.map(function (row) { return new Date(row.end + "Z") - new Date(row.start + "Z"); }),
        base: rows.map(function (row) { return row.start; }),
        marker: { color: color, line: { color: color, width: 2 } },
        customdata: rows.map(function (row) { return [row.hours, T.fmt.dateTime(row.start)]; }),
        hovertemplate: "%{y}<br>" + CATEGORIES[key].label + ": %{customdata[0]} h<br>from %{customdata[1]} UTC<extra></extra>"
      };
    });
    sized("chart-timeline", 110 + 46 * sel.sites.length);
    draw("chart-timeline", traces, baseLayout({
      barmode: "overlay",
      xaxis: { type: "date", tickformat: "%d %b", range: [sel.from + "T00:00:00", T.addDays(sel.to, 1) + "T00:00:00"] },
      yaxis: { type: "category", categoryorder: "array", categoryarray: names, autorange: "reversed", tickfont: { color: css("--ink") } },
      bargap: 0.45
    }));
  }

  function completenessHeatmap(sel) {
    var tags = unique(sel.tagDaily.map(function (row) { return row.tag; }));
    if (!tags.length) { empty("chart-completeness", "No data in this period"); return; }
    var totals = {};
    sel.tagDaily.forEach(function (row) {
      var key = row.tag + "|" + row.site;
      totals[key] = totals[key] || { sum: 0, count: 0 };
      totals[key].sum += row.completeness * 100;
      totals[key].count += 1;
    });
    var all = [];
    var z = tags.map(function (tag) {
      return sel.sites.map(function (site) {
        var total = totals[tag + "|" + site.id];
        var value = total ? total.sum / total.count : null;
        if (value !== null) { all.push(value); }
        return value;
      });
    });
    var floor = Math.min(95, Math.floor(Math.min.apply(null, all) / 5) * 5);
    sized("chart-completeness", 110 + 40 * tags.length);
    draw("chart-completeness", [{
      type: "heatmap", x: sel.sites.map(function (site) { return site.name; }),
      y: tags.map(T.fmt.tag), z: z, zmin: floor, zmax: 100, xgap: 3, ygap: 3,
      colorscale: sequentialScale(), colorbar: colorbar(" %"),
      texttemplate: "%{z:.1f}", hovertemplate: "%{y} at %{x}<br>%{z:.2f} % of expected samples<extra></extra>"
    }], baseLayout({
      margin: { l: 150, t: 40 },
      xaxis: { side: "top", tickfont: { color: css("--ink") } },
      yaxis: { autorange: "reversed", tickfont: { color: css("--ink") } }
    }));
  }

  function rejectedBars(sel) {
    var totals = {};
    sel.tagDaily.forEach(function (row) {
      totals[row.tag] = totals[row.tag] || { valid: 0, invalid: 0 };
      totals[row.tag].valid += row.valid;
      totals[row.tag].invalid += row.invalid;
    });
    var rows = Object.keys(totals).map(function (tag) {
      var received = totals[tag].valid + totals[tag].invalid;
      return { tag: tag, share: received ? (totals[tag].invalid / received) * 100 : 0 };
    }).sort(function (a, b) { return a.share - b.share; });
    if (!rows.length) { empty("chart-rejected", "No data in this period"); return; }
    sized("chart-rejected", 90 + 38 * rows.length);
    draw("chart-rejected", [{
      type: "bar", orientation: "h",
      x: rows.map(function (row) { return row.share; }),
      y: rows.map(function (row) { return T.fmt.tag(row.tag); }),
      marker: { color: css("--accent") },
      texttemplate: "%{x:.2f} %", textposition: "outside", cliponaxis: false,
      textfont: { color: css("--ink") },
      hovertemplate: "%{y}: %{x:.2f} % of received samples rejected<extra></extra>"
    }], baseLayout({
      margin: { l: 150, r: 60 },
      bargap: 0.4,
      xaxis: { title: { text: "Share of received samples rejected" }, rangemode: "tozero", ticksuffix: " %" },
      yaxis: { tickfont: { color: css("--ink") } }
    }));
  }

  T.charts = {
    energyTrend: energyTrend,
    availabilityHeatmap: availabilityHeatmap,
    downtimeTimeline: downtimeTimeline,
    completenessHeatmap: completenessHeatmap,
    rejectedBars: rejectedBars,
    categories: CATEGORIES
  };
})(window.Telemetry = window.Telemetry || {});
