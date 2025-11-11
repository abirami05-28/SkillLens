async function getRanking() {
  const jobId = document.getElementById("jobId").value;
  if (!jobId) return alert("Enter a Job ID first!");

  const res = await fetch(`${API_BASE}/match_job/${jobId}`, { headers: authHeaders() });
  const data = await res.json();

  let html = "<table border='1'><tr><th>Name</th><th>Score</th></tr>";
  data.top_k.forEach(c =>
    html += `<tr><td>${c.name}</td><td>${c.score.toFixed(2)}</td></tr>`
  );
  html += "</table>";
  document.getElementById("rankingTable").innerHTML = html;
}
