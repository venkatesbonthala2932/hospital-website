/**
 * Aadityaa Hospital — Frontend API + Auth Client
 *
 * Include in any HTML page that needs login or API calls:
 *
 *   <!-- Firebase JS SDK -->
 *   <script src="https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js"></script>
 *   <script src="https://www.gstatic.com/firebasejs/10.12.0/firebase-auth-compat.js"></script>
 *
 *   <!-- This file -->
 *   <script src="/static/js/api.js"></script>
 *
 * SETUP: Replace the firebaseConfig below with your project's web config.
 * Find it at: Firebase Console → Project Settings → Your apps → Web app → Config
 */

// ─────────────────────────────────────────────────────────────────────────────
// Firebase web config — get this from Firebase Console → Project Settings
// ─────────────────────────────────────────────────────────────────────────────
const firebaseConfig = {
  apiKey:            "AIzaSyDl7TDEX2PccjAH3C1_PVkeUY2PRuHKvv4",     // ← Firebase Console → Project Settings → Web app
  authDomain:        "aaditya-hospital.firebaseapp.com",
  projectId:         "aaditya-hospital",
  storageBucket:     "aaditya-hospital.appspot.com",
  messagingSenderId: "249159299183",       // ← fill in
  appId:             "1:249159299183:web:2c1cfa789ed9125883dd9a",
};

// API base — relative URL works because Flask serves both the HTML and the API
const API_BASE = "/api";

// Human-readable Firebase auth error messages
const _FB_ERRORS = {
  "auth/invalid-credential":       "Wrong email or password. Please check and try again.",
  "auth/wrong-password":           "Incorrect password. Please try again.",
  "auth/user-not-found":           "No account found with that email address.",
  "auth/email-already-in-use":     "An account with this email already exists. Try signing in instead.",
  "auth/too-many-requests":        "Too many failed attempts. Please wait a few minutes and try again.",
  "auth/invalid-email":            "Please enter a valid email address.",
  "auth/weak-password":            "Password must be at least 8 characters.",
  "auth/network-request-failed":   "Network error. Please check your connection.",
  "auth/popup-closed-by-user":     "Google sign-in was cancelled.",
  "auth/cancelled-popup-request":  "Another sign-in is in progress.",
  "auth/account-exists-with-different-credential":
    "An account already exists with this email using a different sign-in method.",
};

function _fbMsg(err) {
  return _FB_ERRORS[err?.code] || err?.message || "Something went wrong. Please try again.";
}

// ─────────────────────────────────────────────────────────────────────────────
// Firebase init (only if SDK is loaded)
// ─────────────────────────────────────────────────────────────────────────────
let _firebaseApp  = null;
let _firebaseAuth = null;

function _initFirebase() {
  if (_firebaseAuth) return _firebaseAuth;
  if (typeof firebase === "undefined") return null;
  if (!firebase.apps.length) {
    _firebaseApp = firebase.initializeApp(firebaseConfig);
  } else {
    _firebaseApp = firebase.apps[0];
  }
  _firebaseAuth = firebase.auth();
  return _firebaseAuth;
}

// ─────────────────────────────────────────────────────────────────────────────
// Auth helpers
// ─────────────────────────────────────────────────────────────────────────────
const Auth = {
  /** Returns the Firebase ID token for the current user, or null. */
  async getToken() {
    const auth = _initFirebase();
    if (!auth || !auth.currentUser) return null;
    try {
      return await auth.currentUser.getIdToken();
    } catch {
      return null;
    }
  },

  /** Register with email + password. Creates account on Firebase + Supabase profiles. */
  async register(email, password, fullName, phone = "") {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ email, password, full_name: fullName, phone }),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Registration failed.");
    // Now sign in so Firebase sets the current user
    const auth = _initFirebase();
    if (auth) {
      try {
        await auth.signInWithEmailAndPassword(email, password);
      } catch (fbErr) {
        throw new Error(_fbMsg(fbErr));
      }
    }
    return json;
  },

  /** Log in with email + password. */
  async login(email, password) {
    const auth = _initFirebase();
    if (!auth) throw new Error("Firebase SDK not loaded.");
    let cred;
    try {
      cred = await auth.signInWithEmailAndPassword(email, password);
    } catch (fbErr) {
      throw new Error(_fbMsg(fbErr));
    }
    const token = await cred.user.getIdToken();
    const res   = await fetch(`${API_BASE}/auth/login`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Login failed.");
    return json;
  },

  /** Google sign-in via popup. */
  async loginWithGoogle() {
    const auth = _initFirebase();
    if (!auth) throw new Error("Firebase SDK not loaded.");
    const provider = new firebase.auth.GoogleAuthProvider();
    let cred;
    try {
      cred = await auth.signInWithPopup(provider);
    } catch (fbErr) {
      throw new Error(_fbMsg(fbErr));
    }
    const token = await cred.user.getIdToken();
    const res   = await fetch(`${API_BASE}/auth/login`, {
      method:  "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Google sign-in failed.");
    return json;
  },

  /** Log out. */
  async logout() {
    const auth = _initFirebase();
    const token = await this.getToken();
    if (token) {
      await fetch(`${API_BASE}/auth/logout`, {
        method:  "POST",
        headers: { "Authorization": `Bearer ${token}` },
      }).catch(() => {});
    }
    if (auth) await auth.signOut();
    localStorage.removeItem("ah_user");
    window.location.href = "/";
  },

  /** Returns current user object from Firebase, or null. */
  currentUser() {
    const auth = _initFirebase();
    return auth?.currentUser ?? null;
  },

  /** Subscribe to auth state changes. callback(user | null) */
  onAuthStateChange(callback) {
    const auth = _initFirebase();
    if (!auth) return () => {};
    return auth.onAuthStateChanged(callback);
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Core fetch wrapper — attaches Firebase Bearer token automatically
// ─────────────────────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const token   = await Auth.getToken();
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res  = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const json = await res.json().catch(() => ({}));

  if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
  return json;
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API — no login required
// ─────────────────────────────────────────────────────────────────────────────
const API = {
  getSpecialties()       { return apiFetch("/specialties"); },
  getSpecialty(slug)     { return apiFetch(`/specialties/${slug}/doctors`); },
  getDoctors(slug = "")  { return apiFetch(`/doctors${slug ? `?specialty=${slug}` : ""}`); },
  getDoctor(id)          { return apiFetch(`/doctors/${id}`); },
  getAvailableDates(id)  { return apiFetch(`/doctors/${id}/available-dates`); },
  getAvailableSlots(id, date) { return apiFetch(`/doctors/${id}/slots?date=${date}`); },

  // ── Appointments (require login) ───────────────────────────────────────────
  async bookAppointment(payload) {
    const token = await Auth.getToken();
    if (!token) throw new Error("LOGIN_REQUIRED");
    return apiFetch("/appointments", { method: "POST", body: JSON.stringify(payload) });
  },
  getMyAppointments()              { return apiFetch("/appointments/mine"); },
  cancelAppointment(id)            { return apiFetch(`/appointments/${id}/cancel`, { method: "PUT" }); },

  // ── Doctor dashboard ───────────────────────────────────────────────────────
  getDoctorAppointments(date = "") {
    return apiFetch(`/doctor/appointments${date ? `?date=${date}` : ""}`);
  },
  getDoctorPatients()              { return apiFetch("/doctor/patients"); },
  getDoctorLeaves()                { return apiFetch("/doctor/leaves"); },
  submitLeave(date, reason = "")   {
    return apiFetch("/doctor/leaves", { method: "POST", body: JSON.stringify({ date, reason }) });
  },
  updateAppointmentStatus(id, status) {
    return apiFetch(`/doctor/appointments/${id}/status`, {
      method: "PUT", body: JSON.stringify({ status }),
    });
  },

  // ── Admin dashboard ────────────────────────────────────────────────────────
  getAdminStats()                  { return apiFetch("/admin/stats"); },
  getAllAppointments(filters = {}) {
    const p = new URLSearchParams(filters).toString();
    return apiFetch(`/admin/appointments${p ? `?${p}` : ""}`);
  },
  confirmAppointment(id)           { return apiFetch(`/admin/appointments/${id}/confirm`, { method: "POST" }); },
  rejectAppointment(id, reason="") {
    return apiFetch(`/admin/appointments/${id}/reject`, {
      method: "POST", body: JSON.stringify({ reason }),
    });
  },
  getAllLeaves(status = "")        { return apiFetch(`/admin/leaves${status ? `?status=${status}` : ""}`); },
  approveLeave(id, note = "")     {
    return apiFetch(`/admin/leaves/${id}/approve`, { method: "POST", body: JSON.stringify({ note }) });
  },
  rejectLeave(id, note = "")      {
    return apiFetch(`/admin/leaves/${id}/reject`, { method: "POST", body: JSON.stringify({ note }) });
  },
  getAllDoctors()                   { return apiFetch("/admin/doctors"); },
  getAllPatients()                  { return apiFetch("/admin/patients"); },
  setUserRole(uid, role)           {
    return apiFetch(`/admin/users/${uid}/role`, { method: "PUT", body: JSON.stringify({ role }) });
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// withAuth — wraps a booking action; shows login if not authenticated
// ─────────────────────────────────────────────────────────────────────────────
async function withAuth(action) {
  try {
    await action();
  } catch (err) {
    if (err.message === "LOGIN_REQUIRED") {
      const loginEl = document.getElementById("login-modal");
      if (loginEl) loginEl.style.display = "flex";
      else alert("Please log in to book an appointment.");
    } else {
      alert(`Error: ${err.message}`);
    }
  }
}
