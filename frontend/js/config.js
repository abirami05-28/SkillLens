// js/config.js
// update this after Railway gives you the backend URL
const API_BASE_URL = "https://skilllens-backend.up.railway.app";
export { API_BASE_URL };

//const API_BASE = "http://127.0.0.1:8000"; // your backend URL

function getToken() {
  return localStorage.getItem("token") || "";
}

// Use this for JSON API calls
function authHeadersForJson() {
  const token = getToken();
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = "Bearer " + token;
  return headers;
}

// Use this for FormData uploads
function authHeadersForFormData() {
  const token = getToken();
  const headers = {};
  if (token) headers["Authorization"] = "Bearer " + token;
  return headers;
}

// For legacy calls (default)
function authHeaders() {
  return authHeadersForJson();
}
