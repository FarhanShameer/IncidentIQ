# incidentiq.py — recruiter-focused dashboard with Risk Register & STACKED severity chart
from flask import Flask, render_template_string, request, redirect, url_for
from collections import Counter, defaultdict
import datetime as dt

app = Flask(__name__)

incidents = [
    # RBC
    {"company":"RBC","title":"ATM Outage","severity":"High","root_cause":"Hardware",
     "date":"2025-06-12","status":"Closed","resolved":"2025-06-12","description":"Switch failover triggered."},
    {"company":"RBC","title":"Card Switch Latency","severity":"Medium","root_cause":"Network",
     "date":"2025-06-25","status":"Closed","resolved":"2025-06-26","description":"P95 recovered after tuning."},
    {"company":"RBC","title":"Fraud Alert","severity":"Medium","root_cause":"Security",
     "date":"2025-07-08","status":"Closed","resolved":"2025-07-10","description":"Cards blocked; rules updated."},
    {"company":"RBC","title":"DB Replication Lag","severity":"Low","root_cause":"Performance",
     "date":"2025-09-18","status":"Open","resolved":None,"description":"Replica lag 8m on transactions."},
    {"company":"RBC","title":"Login Timeout Spike","severity":"High","root_cause":"Load/Capacity",
     "date":"2025-09-21","status":"Open","resolved":None,"description":"Auth surge during promo."},

    # SOTI
    {"company":"SOTI","title":"MDM Sync Failure","severity":"High","root_cause":"Software",
     "date":"2025-06-22","status":"Closed","resolved":"2025-06-23","description":"Policy push fixed."},
    {"company":"SOTI","title":"Device Compliance Failure","severity":"Medium","root_cause":"Policy",
     "date":"2025-08-05","status":"Closed","resolved":"2025-08-07","description":"Encryption enforced."},
    {"company":"SOTI","title":"Mobile App Crash","severity":"Low","root_cause":"User Error",
     "date":"2025-08-19","status":"Open","resolved":None,"description":"Permission handling patch pending."},

    # Magna
    {"company":"Magna","title":"Sensor Malfunction","severity":"High","root_cause":"Hardware",
     "date":"2025-07-17","status":"Closed","resolved":"2025-07-17","description":"Torque sensor swapped."},
    {"company":"Magna","title":"Robot Encoder Drift","severity":"Medium","root_cause":"Calibration",
     "date":"2025-07-24","status":"Closed","resolved":"2025-07-25","description":"Re-zeroed; spec OK."},
    {"company":"Magna","title":"Assembly Line Delay","severity":"Medium","root_cause":"Supply Chain",
     "date":"2025-09-13","status":"Open","resolved":None,"description":"Bearing pack late; 30m idle."},

    # OPG
    {"company":"OPG","title":"Reactor Sensor Alert","severity":"High","root_cause":"Safety",
     "date":"2025-06-03","status":"Closed","resolved":"2025-06-03","description":"False positive; recalibrated."},
    {"company":"OPG","title":"Cooling Pump Vibration","severity":"High","root_cause":"Mechanical",
     "date":"2025-06-14","status":"Closed","resolved":"2025-06-15","description":"Bearing replaced."},
    {"company":"OPG","title":"Substation Telemetry Timeout","severity":"Medium","root_cause":"Grid/SCADA",
     "date":"2025-08-16","status":"Closed","resolved":"2025-08-16","description":"Storm routing restored."},

    # Enbridge
    {"company":"Enbridge","title":"Pipeline Leak Detection","severity":"High","root_cause":"Safety",
     "date":"2025-07-11","status":"Closed","resolved":"2025-07-11","description":"Sensor verified; no leak."},
    {"company":"Enbridge","title":"Compressor Overheat","severity":"Medium","root_cause":"Mechanical",
     "date":"2025-09-02","status":"Closed","resolved":"2025-09-03","description":"Fan replaced."},
    {"company":"Enbridge","title":"SCADA Error","severity":"Low","root_cause":"Software",
     "date":"2025-09-20","status":"Open","resolved":None,"description":"Tag mismatch in historian."},
]


TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IncidentIQ</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script defer src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <style>
    :root{
      --bg:#0f1220; --panel:#161a2e; --muted:#8a92b2; --accent:#5dd3ff;
      --good:#16a34a; --warn:#f59e0b; --bad:#ef4444;
    }
    body{background:var(--bg); color:#e6e9f5}
    .nav{background:#0b0e1a}
    .card{background:var(--panel); border:1px solid #1e2340; border-radius:16px; overflow:hidden}
    .kpi{font-weight:800; font-size:2.2rem; color:#ffffff; line-height:1}

    /* All small (previously grey) text to white */
    .tiny{font-size:.85rem; color:#ffffff}

    /* Keep charts inside their card */
    .chartbox{max-width:560px; margin:0 auto; height:260px}
    .chartbox canvas{width:100% !important; height:100% !important; display:block}

    .badge-high{background:var(--bad)} .badge-med{background:var(--warn); color:#111827}
    .badge-low{background:var(--good)}
    .risk-low {background:#0e2e1a; color:#86efac; border:1px solid #14532d; padding:.2rem .5rem; border-radius:999px}
    .risk-med {background:#382a08; color:#fde68a; border:1px solid #a16207; padding:.2rem .5rem; border-radius:999px}
    .risk-high{background:#3f0b0b; color:#fca5a5; border:1px solid #b91c1c; padding:.2rem .5rem; border-radius:999px}

    .chip{border-radius:999px; padding:.25rem .7rem; background:#0f1633; color:#ffffff; border:1px solid #2a3470; cursor:pointer}
    .chip.active{background:#1b255e}

    .link{color:var(--accent)}
    .table-dark>tbody>tr>td,.table-dark>thead>tr>th{vertical-align:middle}

    /* Search input placeholder white for visibility */
    #search::placeholder{ color:#ffffff; opacity:.7 }
  </style>
</head>
<body>
<nav class="nav py-2">
  <div class="container d-flex align-items-center gap-2">
    <h4 class="m-0">IncidentIQ</h4>
    <form class="ms-3 d-flex gap-2" method="get">
      <select name="company" class="form-select form-select-sm bg-dark text-white border-0" onchange="this.form.submit()">
        <option value="">All companies</option>
        {% for c in companies %}<option value="{{c}}" {% if c==selected_company %}selected{% endif %}>{{c}}</option>{% endfor %}
      </select>
      <select name="days" class="form-select form-select-sm bg-dark text-white border-0" onchange="this.form.submit()">
        {% for d in [90,180,365] %}
          <option value="{{d}}" {% if d==selected_days %}selected{% endif %}>Last {{d}} days</option>
        {% endfor %}
      </select>
    </form>
    <div class="ms-auto tiny">Repo: <span class="link">github.com/you/incidentiq</span></div>
  </div>
</nav>

<div class="container py-3">

  <!-- Row 1: KPIs + Incidents per month + Severity stacked bars -->
  <div class="row g-3">
    <div class="col-xl-3 col-lg-4">
      <div class="card p-3 h-100">
        <div class="tiny">Total incidents</div>
      
        
        <div class="kpi">{{ total }}</div>
        <div class="tiny mb-3">({{ open_count }} open · {{ closed_count }} closed)</div>
        <div class="tiny">High-severity incidents</div>
        <div class="kpi">{{ high_count }}</div>
        <div class="tiny">{{ pct_high }}% of total</div>
        <hr>
        <div class="tiny">Avg time to resolve (hrs)</div>
        <div class="kpi">{{ mttr_hours }}</div>
        <div class="tiny">Average across closed incidents</div>
      </div>
    </div>

    <div class="col-xl-5 col-lg-4">
      <div class="card p-3 h-100">
        <h6 class="m-0">Incidents per month</h6>
        <div class="chartbox mt-2"><canvas id="bar"></canvas></div>
      </div>
    </div>

    <div class="col-xl-4 col-lg-4">
      <div class="card p-3 h-100">
        <h6 class="m-0">Incidents by severity per month</h6>
        <div class="chartbox mt-2"><canvas id="sevStack"></canvas></div>
      </div>
    </div>
  </div>

  <!-- Row 2: Risk Register + Top Causes -->
  <div class="row g-3 mt-1">
    <div class="col-lg-7">
      <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center">
          <h6 class="m-0">Risk Register (by root cause)</h6>
          <span class="tiny">Weighted score = High×3 + Med×2 + Low×1 ({{ range_label }})</span>
        </div>
        <div class="table-responsive mt-2">
          <table class="table table-sm table-dark align-middle">
            <thead class="tiny text-uppercase">
              <tr>
                <th>Root cause</th>
                <th class="text-center">Open</th>
                <th class="text-center">In range</th>
                <th class="text-center">Severity mix</th>
                <th class="text-center">Score</th>
                <th class="text-center">Risk</th>
                <th class="text-center">Trend</th>
              </tr>
            </thead>
            <tbody>
              {% for r in risk_rows %}
                <tr>
                  <td>{{ r.cause }}</td>
                  <td class="text-center">{{ r.open }}</td>
                  <td class="text-center">{{ r.total }}</td>
                  <td class="text-center">
                    <span class="badge badge-low">L {{ r.low }}</span>
                    <span class="badge badge-med">M {{ r.med }}</span>
                    <span class="badge badge-high">H {{ r.high }}</span>
                  </td>
                  <td class="text-center">{{ r.score }}</td>
                  <td class="text-center">
                    {% if r.level=='High' %}<span class="risk-high">High</span>
                    {% elif r.level=='Medium' %}<span class="risk-med">Medium</span>
                    {% else %}<span class="risk-low">Low</span>{% endif %}
                  </td>
                  <td class="text-center">
                    {% if r.trend=='up' %}↑{% elif r.trend=='down' %}↓{% else %}→{% endif %}
                  </td>
                </tr>
              {% endfor %}
              {% if not risk_rows %}
                <tr><td colspan="7" class="text-center tiny">No risk data in this range.</td></tr>
              {% endif %}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="col-lg-5">
      <div class="card p-3">
        <h6 class="m-0">Top 5 causes</h6>
        <div class="chartbox mt-2"><canvas id="donut"></canvas></div>
      </div>
    </div>
  </div>

  <!-- Incidents table -->
  <div class="card mt-3 p-3">
    <div class="d-flex align-items-center gap-2">
      <h6 class="m-0">Incidents</h6>
      <span class="chip active" data-sev="All">All</span>
      <span class="chip" data-sev="High">High</span>
      <span class="chip" data-sev="Medium">Medium</span>
      <span class="chip" data-sev="Low">Low</span>
      <input class="form-control form-control-sm ms-auto" id="search" placeholder="Search title/cause..." style="max-width:220px">
    </div>
    <div class="table-responsive mt-2">
      <table class="table table-sm table-dark align-middle" id="tbl">
        <thead><tr class="tiny text-uppercase">
          <th>Date</th><th>Company</th><th>Title</th><th>Severity</th><th>Cause</th><th>Status</th>
        </tr></thead>
        <tbody>
          {% for i in rows %}
            <tr data-sev="{{ i.severity }}" data-text="{{ (i.title ~ ' ' ~ i.root_cause ~ ' ' ~ i.description)|lower }}">
              <td class="tiny">{{ i.date }}</td>
              <td class="tiny">{{ i.company }}</td>
              <td>{{ i.title }}</td>
              <td>
                {% if i.severity=='High' %}<span class="badge badge-high">High</span>
                {% elif i.severity=='Medium' %}<span class="badge badge-med">Medium</span>
                {% else %}<span class="badge badge-low">Low</span>{% endif %}
              </td>
              <td class="tiny">{{ i.root_cause }}</td>
              <td class="tiny">{{ i.status }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Quick add (optional) -->
  <div class="card mt-3 p-3">
    <form method="post" action="{{ url_for('add_incident') }}" class="row g-2">
      <div class="col-md-2"><select name="company" class="form-select">
        {% for c in companies %}<option>{{c}}</option>{% endfor %}
      </select></div>
      <div class="col-md-3"><input name="title" class="form-control" placeholder="Title" required></div>
      <div class="col-md-2"><select name="severity" class="form-select">
        <option>Low</option><option>Medium</option><option>High</option>
      </select></div>
      <div class="col-md-2"><input name="root_cause" class="form-control" placeholder="Root cause"></div>
      <div class="col-md-1"><select name="status" class="form-select">
        <option>Open</option><option>Closed</option>
      </select></div>
      <div class="col-md-2"><input name="date" class="form-control" placeholder="YYYY-MM-DD" value="{{ today }}"></div>
      <div class="col-md-12"><input name="description" class="form-control" placeholder="Short description (optional)"></div>
      <div class="col-md-12 text-end"><button class="btn btn-outline-light">Add Incident</button></div>
    </form>
  </div>

</div>

<script>
window.addEventListener('DOMContentLoaded', function () {
  // Global Chart.js colors for visibility on dark background
  Chart.defaults.color = '#e6e9f5';
  Chart.defaults.borderColor = 'rgba(230,233,245,0.12)';

  // ---- Table filters ----
  const chips=[...document.querySelectorAll('.chip')], rows=[...document.querySelectorAll('#tbl tbody tr')], q=document.getElementById('search');
  function applyFilters(){
    const sev=document.querySelector('.chip.active')?.dataset.sev || 'All';
    const text=(q.value||'').toLowerCase();
    rows.forEach(r=>{
      const okSev=(sev==='All'||r.dataset.sev===sev);
      const okTxt=!text || r.dataset.text.includes(text);
      r.style.display=(okSev&&okTxt)?'':'none';
    });
  }
  chips.forEach(c=>c.onclick=()=>{chips.forEach(x=>x.classList.remove('active')); c.classList.add('active'); applyFilters();});
  q.oninput=applyFilters;

  // ---- Incidents per month (bar) ----
  const months = {{ months|tojson }};
  const totals = {{ created_counts|tojson }};
  if (!months.length) {
    document.getElementById('bar').parentElement.innerHTML =
      '<div class="tiny text-center">No data in this range.</div>';
  } else {
    new Chart(document.getElementById('bar'), {
      type:'bar',
      data:{ labels: months,
        datasets:[{ label:'Incidents', data: totals, backgroundColor:'rgba(93,211,255,.6)' }] },
      options:{ responsive:true, maintainAspectRatio:false,
        scales:{ y:{ beginAtZero:true, ticks:{ stepSize:1, precision:0 } } }
      }
    });
  }

  // ---- Severity by month (STACKED bars) ----
  const sevLabels = {{ sev_months|tojson }};
  const lowSeries = {{ sev_low|tojson }};
  const medSeries = {{ sev_med|tojson }};
  const highSeries= {{ sev_high|tojson }};
  if (!sevLabels.length) {
    document.getElementById('sevStack').parentElement.innerHTML =
      '<div class="tiny text-center">No severity data.</div>';
  } else {
    new Chart(document.getElementById('sevStack'), {
      type:'bar',
      data:{
        labels: sevLabels,
        datasets:[
          {label:'Low',    data: lowSeries,  backgroundColor:'#16a34a'},
          {label:'Medium', data: medSeries,  backgroundColor:'#f59e0b'},
          {label:'High',   data: highSeries, backgroundColor:'#ef4444'}
        ]
      },
      options:{
        responsive:true, maintainAspectRatio:false,
        scales:{
          x:{ stacked:true },
          y:{ stacked:true, beginAtZero:true, ticks:{ stepSize:1, precision:0 } }
        },
        plugins:{ legend:{ position:'top' } }
      }
    });
  }

  // ---- Top 5 Causes donut ----
  const cLabels = {{ cause_labels|tojson }};
  const cVals   = {{ cause_values|tojson }};
  if (!cLabels.length) {
    document.getElementById('donut').parentElement.innerHTML =
      '<div class="tiny text-center">No categories to display.</div>';
  } else {
    new Chart(document.getElementById('donut'), {
      type:'doughnut',
      data:{ labels: cLabels, datasets:[{ data: cVals,
        backgroundColor:['#22c55e','#f59e0b','#ef4444','#38bdf8','#a78bfa'] }] },
      options:{ plugins:{legend:{position:'bottom'}}, cutout:'55%', responsive:true, maintainAspectRatio:false }
    });
  }
});
</script>
</body>
</html>
"""

def parse(d): return dt.datetime.strptime(d, "%Y-%m-%d").date()
def in_last_days(item, days): return parse(item["date"]) >= dt.date.today() - dt.timedelta(days=days)
def month_key(d): return (d.year, d.month)
def month_label(y, m): return dt.date(y, m, 1).strftime("%b %Y")

def monthly_counts(items):
    """Return month labels and created-per-month totals for given items."""
    bucket = defaultdict(int)
    if not items: return [], []
    dates = [parse(i["date"]) for i in items]
    start = dt.date(min(dates).year, min(dates).month, 1)
    end   = dt.date(max(dates).year, max(dates).month, 1)
    cur = start
    while cur <= end:
        bucket[month_key(cur)]
        nxt = cur.replace(day=28) + dt.timedelta(days=4)
        cur = nxt.replace(day=1)
    for i in items:
        bucket[month_key(parse(i["date"]))] += 1
    labels  = [month_label(y,m) for (y,m) in sorted(bucket.keys())]
    created = [bucket[k] for k in sorted(bucket.keys())]
    return labels, created

def monthly_severity_series(items):
    """Return labels and three parallel series (Low/Med/High per month)."""
    bucket = defaultdict(lambda: {"Low":0,"Medium":0,"High":0})
    if not items: return [], [], [], []
    dates = [parse(i["date"]) for i in items]
    start = dt.date(min(dates).year, min(dates).month, 1)
    end   = dt.date(max(dates).year, max(dates).month, 1)
    cur = start
    while cur <= end:
        bucket[month_key(cur)]
        nxt = cur.replace(day=28) + dt.timedelta(days=4)
        cur = nxt.replace(day=1)
    for i in items:
        k = month_key(parse(i["date"]))
        bucket[k][i["severity"]] += 1
    keys_sorted = sorted(bucket.keys())
    labels = [month_label(y,m) for (y,m) in keys_sorted]
    low = [bucket[k]["Low"] for k in keys_sorted]
    med = [bucket[k]["Medium"] for k in keys_sorted]
    high= [bucket[k]["High"] for k in keys_sorted]
    return labels, low, med, high

def average_resolution_hours(items):
    hrs=[]
    for i in items:
        if i["status"]=="Closed" and i["resolved"]:
            hrs.append((parse(i["resolved"])-parse(i["date"])).total_seconds()/3600.0)
    return 0.0 if not hrs else round(sum(hrs)/len(hrs),1)

def risk_register(items, _):
    """Per-root-cause risk analytics with weighted score + simple trend."""
    by_cause = defaultdict(lambda: {"Low":0,"Medium":0,"High":0,"total":0,"open":0})
    for i in items:
        c = i["root_cause"]
        by_cause[c]["total"] += 1
        by_cause[c][i["severity"]] += 1
        if i["status"]=="Open":
            by_cause[c]["open"] += 1

    per_cause_months = defaultdict(lambda: defaultdict(int))
    for i in items:
        ym = month_key(parse(i["date"]))
        per_cause_months[i["root_cause"]][ym] += 1

    rows=[]
    for cause, rec in by_cause.items():
        low, med, high = rec["Low"], rec["Medium"], rec["High"]
        score = 3*high + 2*med + 1*low
        level = "High" if score>=6 else ("Medium" if score>=3 else "Low")

        months_sorted = sorted(per_cause_months[cause].keys())
        if len(months_sorted) >= 2:
            v_now  = per_cause_months[cause][months_sorted[-1]]
            v_prev = per_cause_months[cause][months_sorted[-2]]
            trend = "up" if v_now>v_prev else ("down" if v_now<v_prev else "flat")
        else:
            trend = "flat"

        rows.append({
            "cause": cause, "open": rec["open"], "total": rec["total"],
            "low": low, "med": med, "high": high,
            "score": score, "level": level, "trend": trend
        })
    rows.sort(key=lambda r: (r["score"], r["open"]), reverse=True)
    return rows


@app.route("/")
def dashboard():
    selected = (request.args.get("company") or "").strip()
    days = int(request.args.get("days") or 90)

    filtered = [i for i in incidents
                if (not selected or i["company"].lower()==selected.lower())
                and in_last_days(i, days)]

    total = len(filtered)
    open_count = sum(1 for i in filtered if i["status"]=="Open")
    closed_count = total - open_count
    high_count = sum(1 for i in filtered if i["severity"]=="High")
    mttr_hours = average_resolution_hours(filtered)

    months, created_counts = monthly_counts(filtered)
    sev_months, sev_low, sev_med, sev_high = monthly_severity_series(filtered)

    cause_counts = Counter(i["root_cause"] for i in filtered)
    top_pairs = sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    cause_labels = [p[0] for p in top_pairs]
    cause_values = [p[1] for p in top_pairs]

    risk_rows = risk_register(filtered, filtered)

    return render_template_string(
        TEMPLATE,
        companies=sorted({i["company"] for i in incidents}),
        selected_company=selected,
        selected_days=days,
        rows=sorted(filtered, key=lambda x:x["date"], reverse=True),
        total=total, open_count=open_count, closed_count=closed_count,
        high_count=high_count, pct_high=(0 if total==0 else round(100*high_count/total)),
        mttr_hours=mttr_hours,
        months=months, created_counts=created_counts,
        sev_months=sev_months, sev_low=sev_low, sev_med=sev_med, sev_high=sev_high,
        cause_labels=cause_labels, cause_values=cause_values,
        risk_rows=risk_rows,
        range_label=f"Last {days} days",
        today=dt.date.today().isoformat()
    )

@app.route("/add", methods=["POST"])
def add_incident():
    f = request.form
    incidents.append({
        "company": f.get("company","RBC"),
        "title":   f.get("title","New Incident"),
        "severity":f.get("severity","Low"),
        "root_cause": f.get("root_cause",""),
        "date":    f.get("date") or dt.date.today().isoformat(),
        "status":  f.get("status","Open"),
        "resolved": None if f.get("status","Open")=="Open" else (f.get("date") or dt.date.today().isoformat()),
        "description": f.get("description","")
    })
    return redirect(url_for("dashboard", company=f.get("company",""), days=request.args.get("days",90)))

if __name__ == "__main__":
    app.run(debug=True)




