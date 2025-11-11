// js/auth.js

// --- SIGNUP ---
async function signup() {
  const email = document.getElementById("email").value.trim();
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const orgname = document.getElementById("orgname")?.value.trim();
  const contact = document.getElementById("contact")?.value.trim();
  const address = document.getElementById("address")?.value.trim();

  if (!email || !username || !password) {
    alert("Please fill in all required fields.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, username, password, orgname, contact, address })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Signup failed.");

    alert("Registration successful!");
    window.location.href = "signin.html";
  } catch (err) {
    alert("Signup failed: " + err.message);
  }
}

// --- LOGIN ---
async function login() {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value.trim();

  if (!email || !password) {
    alert("Please enter both email and password.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Invalid credentials.");

    localStorage.setItem("token", data.access_token);
    localStorage.setItem("user_email", email);

    // 🆕 decode JWT to store username
    const payload = JSON.parse(atob(data.access_token.split(".")[1]));
    localStorage.setItem("username", payload.username || email.split("@")[0]);

    alert("Login successful!");
    window.location.href = "userdash.html";
  } catch (err) {
    alert("Login failed: " + err.message);
  }
}


// --- GOOGLE LOGIN (if used) ---
function googleLogin() {
  window.location.href = `${API_BASE}/auth/google/start`;
}

// --- AUTH HELPERS ---
function getToken() {
  return localStorage.getItem("token") || "";
}

function authHeaders() {
  const token = getToken();
  return token
    ? { Authorization: "Bearer " + token }
    : {};
}

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user_email");
  localStorage.removeItem("username");
  window.location.href = "signin.html";
}

function getUserInfo() {
  return {
    email: localStorage.getItem("user_email"),
    username: localStorage.getItem("username"),
    token: localStorage.getItem("token")
  };
}
