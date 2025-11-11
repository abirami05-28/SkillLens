async function uploadResume() {
  const fileInput = document.getElementById("resumeFile");
  if (!fileInput.files.length) return alert("Select a PDF file first!");

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  const res = await fetch(`${API_BASE}/resume/upload_resume`, {
    method: "POST",
    headers: {"Authorization": "Bearer " + getToken()},
    body: formData
  });

  const data = await res.json();
  document.getElementById("output").innerText = JSON.stringify(data, null, 2);
}
