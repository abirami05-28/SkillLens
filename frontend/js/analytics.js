// js/analytics.js
async function loadAnalytics() {
  try {
    // 1️⃣ Fetch all analytics data
    const [funnelRes, skillsRes, clustersRes] = await Promise.all([
      fetch(`${API_BASE}/analytics/funnel`, { headers: authHeaders() }),
      fetch(`${API_BASE}/analytics/skills`, { headers: authHeaders() }),
      fetch(`${API_BASE}/analytics/clusters`, { headers: authHeaders() }),
    ]);

    const funnel = await funnelRes.json();
    const skills = await skillsRes.json();
    const clusters = await clustersRes.json();

    console.log("Analytics data:", { funnel, skills, clusters });

    // 2️⃣ Funnel chart (bar)
    updateBarChart(funnel);

    // 3️⃣ Frequent skills (bar)
    updateFreqChart(skills.rules);

    // 4️⃣ Cluster chart (scatter/pie)
    updateClusterChart(clusters.clusters);

  } catch (err) {
    console.error("Error loading analytics:", err);
    alert("Failed to load analytics data. Check backend connection.");
  }
}

// ===================== CHART UPDATE HELPERS =====================
function updateBarChart(funnel) {
  const ctx = document.getElementById("barChart").getContext("2d");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Total", "Screened", "Shortlisted", "Hired"],
      datasets: [
        {
          label: "Candidates",
          data: [funnel.total, funnel.screened, funnel.shortlisted, funnel.hired],
          backgroundColor: "#4facfe",
        },
      ],
    },
    options: { responsive: true, scales: { y: { beginAtZero: true } } },
  });
}

function updateFreqChart(rules) {
  const ctx = document.getElementById("freqBarChart").getContext("2d");
  const labels = rules.slice(0, 5).map(r => r.lhs.join(", "));
  const values = rules.slice(0, 5).map(r => (r.confidence * 100).toFixed(1));

  new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Confidence %", data: values, backgroundColor: "#00c6ff" }],
    },
    options: { responsive: true, scales: { y: { beginAtZero: true } } },
  });
}

function updateClusterChart(clusters) {
  const ctx = document.getElementById("pieChart").getContext("2d");
  const labels = clusters.map(c => `Cluster ${c.cluster}`);
  const data = clusters.map(c => c.count);

  new Chart(ctx, {
    type: "pie",
    data: {
      labels,
      datasets: [{ data, backgroundColor: ["#4facfe", "#00c6ff", "#a1c181", "#f45b69", "#ff8c42"] }],
    },
    options: { responsive: true, plugins: { legend: { position: "bottom" } } },
  });
}

// ===================== INIT =====================
window.addEventListener("DOMContentLoaded", loadAnalytics);
