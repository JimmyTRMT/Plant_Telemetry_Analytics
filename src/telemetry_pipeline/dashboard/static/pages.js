/* Page logic: figures, tables and summary sentences. Redraws whenever a filter or the theme changes. */
(function (T) {
  "use strict";

  var h = T.h;
  var fmt = T.fmt;
  var DOT_SHAPES = {
    short_trip: '<circle cx="6" cy="6" r="5"></circle>',
    extended_stop: '<path d="M6 .8 11.2 6 6 11.2.8 6z"></path>',
    long_shutdown: '<rect x="1" y="1" width="10" height="10" rx="1.5"></rect>'
  };

  function sum(rows, key) {
    return rows.reduce(function (total, row) { return total + (row[key] || 0); }, 0);
  }

  function byId(id) { return document.getElementById(id); }

  function setText(id, text) {
    var node = byId(id);
    if (node) { node.textContent = text; }
  }

  // Per-plant totals for a selection. Fleet figures use the same maths on all rows.
  function summarize(rows, sites) {
    var energy = sum(rows, "energyMwh");
    var running = sum(rows, "runningHours");
    var stopped = sum(rows, "stoppedHours");
    var nominalHours = rows.reduce(function (total, row) {
      return total + T.siteById[row.site].nominalPowerMw * (row.runningHours + row.stoppedHours);
    }, 0);
    var completeness = rows.filter(function (row) { return row.completeness !== null; });
    return {
      energyMwh: energy,
      availability: running + stopped ? running / (running + stopped) : null,
      capacityFactor: nominalHours ? energy / nominalHours : null,
      alarmHours: sum(rows, "exceedanceHours"),
      completeness: completeness.length ? sum(completeness, "completeness") / completeness.length : null,
      sites: sites
    };
  }

  function plantLabel(sel) {
    if (sel.allSites) { return sel.sites.length + " plants"; }
    return sel.sites.map(function (site) { return site.name; }).join(" and ");
  }

  function plural(count, word) { return count + " " + word + (count === 1 ? "" : "s"); }

  /* Overview */
  var scorecardSort = { key: "energyMwh", direction: "descending" };

  function scorecardRows(sel) {
    return sel.sites.map(function (site) {
      var rows = sel.daily.filter(function (row) { return row.site === site.id; });
      var totals = summarize(rows, [site]);
      totals.site = site;
      totals.series = rows.map(function (row) { return row.energyMwh; });
      totals.name = site.name;
      totals.nominalPowerMw = site.nominalPowerMw;
      return totals;
    });
  }

  function sparkline(series, color) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "spark");
    svg.setAttribute("viewBox", "0 0 120 30");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("style", "--dot: " + color);
    if (series.length > 1) {
      var low = Math.min.apply(null, series);
      var high = Math.max.apply(null, series);
      var range = high - low || 1;
      var points = series.map(function (value, index) {
        var x = (index / (series.length - 1)) * 116 + 2;
        var y = 27 - ((value - low) / range) * 24;
        return x.toFixed(1) + "," + y.toFixed(1);
      }).join(" ");
      var line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      line.setAttribute("points", points);
      svg.appendChild(line);
    }
    return svg;
  }

  function meterCell(ratio) {
    var width = ratio === null ? 0 : Math.max(0, Math.min(ratio, 1)) * 100;
    return h("td", { class: "num" }, h("div", { class: "meter-cell" },
      h("div", { class: "meter", "aria-hidden": "true" }, h("i", { style: "width: " + width.toFixed(1) + "%" })),
      h("span", { text: fmt.percent(ratio) })));
  }

  var SCORECARD_COLUMNS = [
    { key: "name", label: "Plant", numeric: false },
    { key: "nominalPowerMw", label: "Nominal MW", numeric: true },
    { key: "energyMwh", label: "Energy (GWh)", numeric: true },
    { key: "availability", label: "Availability", numeric: true },
    { key: "capacityFactor", label: "Capacity factor", numeric: true },
    { key: "alarmHours", label: "Alarm hours", numeric: true },
    { key: "series", label: "Daily energy", numeric: false, unsortable: true }
  ];

  function drawScorecard(sel) {
    var table = byId("scorecard");
    var head = table.tHead;
    var body = table.tBodies[0];
    var rows = scorecardRows(sel).sort(function (a, b) {
      var left = a[scorecardSort.key];
      var right = b[scorecardSort.key];
      var order = typeof left === "string" ? left.localeCompare(right) : (left || 0) - (right || 0);
      return scorecardSort.direction === "ascending" ? order : -order;
    });

    var headerRow = h("tr");
    SCORECARD_COLUMNS.forEach(function (column) {
      var cell = h("th", { scope: "col", class: column.numeric ? "num" : "" });
      if (column.unsortable) {
        cell.textContent = column.label;
      } else {
        var button = h("button", { type: "button", text: column.label });
        button.addEventListener("click", function () {
          var same = scorecardSort.key === column.key;
          scorecardSort = {
            key: column.key,
            direction: same && scorecardSort.direction === "descending" ? "ascending" : "descending"
          };
          drawScorecard(T.selection());
        });
        cell.appendChild(button);
        if (scorecardSort.key === column.key) { cell.setAttribute("aria-sort", scorecardSort.direction); }
      }
      headerRow.appendChild(cell);
    });
    head.replaceChildren(headerRow);

    body.replaceChildren.apply(body, rows.map(function (row) {
      return h("tr", null,
        h("td", null, h("span", { class: "plant", style: "--dot: " + row.site.color }, h("i"), row.name, h("small", { text: row.site.country }))),
        h("td", { class: "num", text: fmt.number(row.nominalPowerMw, 1) }),
        h("td", { class: "num", text: fmt.number(row.energyMwh / 1000, 1) }),
        meterCell(row.availability),
        meterCell(row.capacityFactor),
        h("td", { class: "num", text: fmt.number(row.alarmHours) }),
        h("td", null, sparkline(row.series, row.site.color)));
    }));
  }

  function drawOverview(sel) {
    var totals = summarize(sel.daily, sel.sites);
    document.querySelectorAll(".kpi").forEach(function (card) {
      var value = card.querySelector("[data-value]");
      var kind = card.getAttribute("data-kpi");
      if (kind === "energy") { T.setNumber(value, totals.energyMwh / 1000, function (v) { return fmt.number(v, 1); }); }
      if (kind === "availability") { T.setNumber(value, totals.availability === null ? null : totals.availability * 100, function (v) { return fmt.number(v, 1); }); }
      if (kind === "capacity") { T.setNumber(value, totals.capacityFactor === null ? null : totals.capacityFactor * 100, function (v) { return fmt.number(v, 1); }); }
      if (kind === "alarms") { T.setNumber(value, totals.alarmHours, function (v) { return fmt.number(v); }); }
      if (kind === "completeness") { T.setNumber(value, totals.completeness === null ? null : totals.completeness * 100, function (v) { return fmt.number(v, 1); }); }
    });

    setText("summary", plantLabel(sel) + " delivered " + fmt.number(totals.energyMwh / 1000, 1) +
      " GWh over the last " + plural(sel.days, "day") + " and ran " + fmt.percent(totals.availability) + " of the time.");

    var perPlant = scorecardRows(sel).sort(function (a, b) { return b.energyMwh - a.energyMwh; });
    if (perPlant.length > 1) {
      setText("insight-energy", perPlant[0].name + " delivered the most, " + fmt.number(perPlant[0].energyMwh / 1000, 1) +
        " GWh. " + perPlant[perPlant.length - 1].name + " delivered the least, " +
        fmt.number(perPlant[perPlant.length - 1].energyMwh / 1000, 1) + " GWh. Hover a day to compare plants.");
    } else {
      setText("insight-energy", "Daily energy for " + perPlant[0].name + ", in MWh.");
    }

    T.charts.energyTrend(sel);
    drawScorecard(sel);
  }

  /* Operations */
  function stopPill(category) {
    var label = T.charts.categories[category].label;
    var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 12 12");
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = DOT_SHAPES[category];
    var pill = h("span", { class: "pill " + category });
    pill.appendChild(icon);
    pill.appendChild(document.createTextNode(label));
    return pill;
  }

  function drawOperations(sel) {
    var stops = sel.downtime.slice().sort(function (a, b) { return b.start.localeCompare(a.start); });
    var hours = sum(stops, "hours");
    if (!stops.length) {
      setText("summary", "No stops for " + plantLabel(sel) + " in the last " + plural(sel.days, "day") + ".");
    } else {
      var longest = stops.reduce(function (best, stop) { return stop.hours > best.hours ? stop : best; });
      setText("summary", plural(stops.length, "stop") + " in the last " + plural(sel.days, "day") + ", " +
        fmt.number(hours) + " hours of downtime in total. The longest lasted " + longest.hours + " hours at " +
        T.siteById[longest.site].name + ", starting " + fmt.shortDate(longest.localStart) + ".");
    }

    var lowest = null;
    sel.daily.forEach(function (row) {
      var total = row.runningHours + row.stoppedHours;
      var ratio = total ? row.runningHours / total : null;
      if (ratio !== null && (lowest === null || ratio < lowest.ratio)) { lowest = { ratio: ratio, row: row }; }
    });
    setText("insight-heatmap", lowest
      ? "Lowest day: " + T.siteById[lowest.row.site].name + " on " + fmt.shortDate(lowest.row.date) + ", running " +
        fmt.percent(lowest.ratio, 0) + " of the hours. Squares that fade into the background are days with stops."
      : "Each square is one plant on one local day.");

    T.charts.availabilityHeatmap(sel);
    T.charts.downtimeTimeline(sel);

    var shown = stops.slice(0, 25);
    var body = byId("stops").tBodies[0];
    if (!shown.length) {
      body.replaceChildren(h("tr", null, h("td", { class: "empty", colspan: "5", text: "No stops in this period." })));
    } else {
      body.replaceChildren.apply(body, shown.map(function (stop) {
        var site = T.siteById[stop.site];
        return h("tr", null,
          h("td", null, h("span", { class: "plant", style: "--dot: " + site.color }, h("i"), site.name)),
          h("td", { text: fmt.dateTime(stop.localStart) }),
          h("td", { class: "num", text: stop.hours + " h" }),
          h("td", null, stopPill(stop.category)),
          h("td", { text: stop.censored ? "Cut by the edge of the period, may be longer" : "" }));
      }));
    }
    setText("stops-hint", stops.length > shown.length
      ? "Showing the " + shown.length + " most recent of " + stops.length + ". Times are local to each plant. The CSV has all of them."
      : "Most recent stops first. Times are local to each plant.");
  }

  /* Data quality */
  function drawQuality(sel) {
    var valid = sum(sel.tagDaily, "valid");
    var invalid = sum(sel.tagDaily, "invalid");
    var totals = summarize(sel.daily, sel.sites);
    setText("summary", fmt.percent(totals.completeness) + " of the expected samples arrived and passed validation. " +
      fmt.percent(valid + invalid ? invalid / (valid + invalid) : null, 2) + " of the samples received were rejected. " +
      (sel.flatlines.length ? plural(sel.flatlines.length, "stuck sensor episode") + " in this period." : "No stuck sensors in this period."));

    var worst = null;
    var groups = {};
    sel.tagDaily.forEach(function (row) {
      var key = row.tag + "|" + row.site;
      groups[key] = groups[key] || { tag: row.tag, site: row.site, sum: 0, count: 0 };
      groups[key].sum += row.completeness;
      groups[key].count += 1;
    });
    Object.keys(groups).forEach(function (key) {
      var average = groups[key].sum / groups[key].count;
      if (worst === null || average < worst.average) { worst = { group: groups[key], average: average }; }
    });
    setText("insight-completeness", worst
      ? "Least complete: " + fmt.tag(worst.group.tag) + " at " + T.siteById[worst.group.site].name + ", " +
        fmt.percent(worst.average) + " of expected samples. Darker squares are more complete."
      : "Percentage of expected samples that were received and valid.");

    var byTag = {};
    sel.tagDaily.forEach(function (row) {
      byTag[row.tag] = byTag[row.tag] || { valid: 0, invalid: 0 };
      byTag[row.tag].valid += row.valid;
      byTag[row.tag].invalid += row.invalid;
    });
    var ranked = Object.keys(byTag).map(function (tag) {
      var received = byTag[tag].valid + byTag[tag].invalid;
      return { tag: tag, share: received ? byTag[tag].invalid / received : 0 };
    }).sort(function (a, b) { return b.share - a.share; });
    setText("insight-rejected", ranked.length
      ? fmt.tag(ranked[0].tag) + " loses the most, " + fmt.percent(ranked[0].share, 2) + " of its received samples. Sentinel values and bad flags drive most rejections."
      : "Share of received samples that failed validation, per measurement.");

    T.charts.completenessHeatmap(sel);
    T.charts.rejectedBars(sel);

    var body = byId("flatlines").tBodies[0];
    if (!sel.flatlines.length) {
      body.replaceChildren(h("tr", null, h("td", { class: "empty", colspan: "5", text: "No stuck sensors in this period." })));
    } else {
      body.replaceChildren.apply(body, sel.flatlines.map(function (row) {
        var site = T.siteById[row.site];
        return h("tr", null,
          h("td", null, h("span", { class: "plant", style: "--dot: " + site.color }, h("i"), site.name)),
          h("td", { text: fmt.tag(row.tag) }),
          h("td", { text: fmt.dateTime(row.start) }),
          h("td", { class: "num", text: row.hours + " h" }),
          h("td", { class: "num", text: fmt.number(row.value, 1) }));
      }));
    }
  }

  /* Wiring */
  function exportButtons() {
    var daily = byId("export-daily");
    if (daily) {
      daily.addEventListener("click", function () {
        T.downloadCsv("daily-kpis.csv", [
          { label: "plant", value: function (r) { return T.siteById[r.site].name; } },
          { label: "local_date", value: function (r) { return r.date; } },
          { label: "energy_mwh", value: function (r) { return r.energyMwh; } },
          { label: "running_hours", value: function (r) { return r.runningHours; } },
          { label: "stopped_hours", value: function (r) { return r.stoppedHours; } },
          { label: "emission_alarm_hours", value: function (r) { return r.exceedanceHours; } },
          { label: "data_completeness", value: function (r) { return r.completeness; } }
        ], T.selection().daily);
      });
    }
    var stops = byId("export-stops");
    if (stops) {
      stops.addEventListener("click", function () {
        T.downloadCsv("stops.csv", [
          { label: "plant", value: function (r) { return T.siteById[r.site].name; } },
          { label: "started_local", value: function (r) { return r.localStart; } },
          { label: "started_utc", value: function (r) { return r.start; } },
          { label: "ended_utc", value: function (r) { return r.end; } },
          { label: "hours", value: function (r) { return r.hours; } },
          { label: "type", value: function (r) { return r.category; } },
          { label: "cut_by_period", value: function (r) { return r.censored; } }
        ], T.selection().downtime);
      });
    }
  }

  var RENDERERS = { overview: drawOverview, operations: drawOperations, quality: drawQuality };

  function render() {
    var draw = RENDERERS[document.body.getAttribute("data-page")];
    if (draw) { draw(T.selection()); }
  }

  document.addEventListener("DOMContentLoaded", function () {
    T.start();
    exportButtons();
    T.onChange(render);
    render();
  });
})(window.Telemetry);
