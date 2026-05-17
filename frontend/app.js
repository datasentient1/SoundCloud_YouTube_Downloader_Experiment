const state = {
  token: localStorage.getItem("token"),
  user: null,
  mode: "login",
  poll: null,
};

const authPanel = document.querySelector("#authPanel");
const appPanel = document.querySelector("#appPanel");
const authForm = document.querySelector("#authForm");
const authSubmit = document.querySelector("#authSubmit");
const authMessage = document.querySelector("#authMessage");
const termsPanel = document.querySelector("#termsPanel");
const downloadPanel = document.querySelector("#downloadPanel");
const termsCheckbox = document.querySelector("#termsCheckbox");
const jobsEl = document.querySelector("#jobs");

function headers() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${state.token}`,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(body?.detail || "Request failed.");
  }
  return body;
}

function setMessage(text, isError = false) {
  authMessage.textContent = text;
  authMessage.style.color = isError ? "#b3261e" : "#646464";
}

function renderSession() {
  const signedIn = Boolean(state.token && state.user);
  authPanel.classList.toggle("hidden", signedIn);
  appPanel.classList.toggle("hidden", !signedIn);
  if (!signedIn) return;

  termsPanel.classList.toggle("hidden", state.user.termsAccepted);
  downloadPanel.classList.toggle("hidden", !state.user.termsAccepted);
  if (state.user.termsAccepted) {
    loadJobs();
    state.poll ||= setInterval(loadJobs, 3000);
  }
}

function renderJobs(jobs) {
  if (!jobs.length) {
    jobsEl.innerHTML = `<p class="hint">No exports yet.</p>`;
    return;
  }

  jobsEl.innerHTML = jobs
    .map((job) => {
      const archive =
        job.status === "complete"
          ? `<a class="archive" href="/api/downloads/${job.id}/archive" target="_blank" rel="noreferrer">Download zip</a>`
          : "";
      const detail = job.error || job.progress || "Queued.";
      return `
        <article class="job">
          <div>
            <div class="job-url">${job.url}</div>
            <p class="job-progress">${detail}</p>
            ${archive}
          </div>
          <span class="status ${job.status}">${job.status}</span>
        </article>
      `;
    })
    .join("");
}

async function loadMe() {
  if (!state.token) return;
  try {
    state.user = await api("/api/me", { headers: headers() });
  } catch {
    localStorage.removeItem("token");
    state.token = null;
    state.user = null;
  }
}

async function loadJobs() {
  if (!state.token || !state.user?.termsAccepted) return;
  try {
    const jobs = await api("/api/downloads", { headers: headers() });
    renderJobs(jobs);
  } catch (error) {
    jobsEl.innerHTML = `<p class="hint">${error.message}</p>`;
  }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    state.mode = tab.dataset.mode;
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    authSubmit.textContent = state.mode === "login" ? "Sign in" : "Create account";
    setMessage("");
  });
});

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(authForm);
  const payload = {
    email: form.get("email"),
    password: form.get("password"),
  };

  authSubmit.disabled = true;
  setMessage("Working...");
  try {
    const session = await api(`/api/auth/${state.mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.token = session.access_token;
    state.user = session.user;
    localStorage.setItem("token", state.token);
    setMessage("");
    renderSession();
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    authSubmit.disabled = false;
  }
});

document.querySelector("#acceptTermsButton").addEventListener("click", async () => {
  if (!termsCheckbox.checked) return;
  state.user = await api("/api/terms", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ accepted: true }),
  });
  renderSession();
});

document.querySelector("#downloadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api("/api/downloads", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ url: form.get("url") }),
  });
  event.currentTarget.reset();
  await loadJobs();
});

document.querySelector("#signOutButton").addEventListener("click", () => {
  localStorage.removeItem("token");
  state.token = null;
  state.user = null;
  if (state.poll) clearInterval(state.poll);
  state.poll = null;
  renderSession();
});

loadMe().then(renderSession);
