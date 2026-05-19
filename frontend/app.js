const state = {
  jobIds: JSON.parse(localStorage.getItem("jobIds") || "[]"),
  logs: {},
  poll: null,
};

const downloadForm = document.querySelector("#downloadForm");
const jobsEl = document.querySelector("#jobs");
const messageEl = document.querySelector("#message");

function saveJobIds() {
  localStorage.setItem("jobIds", JSON.stringify(state.jobIds.slice(0, 25)));
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

async function textApi(path) {
  const response = await fetch(path);
  const body = await response.text();
  if (!response.ok) {
    throw new Error(body || "Request failed.");
  }
  return body;
}

function setMessage(text, isError = false) {
  messageEl.textContent = text;
  messageEl.style.color = isError ? "#b3261e" : "#646464";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function logTextFor(job) {
  return state.logs[job.id] || "Log not loaded yet. Wait a few seconds, or click Reload log after the job starts.";
}

function renderJobs(jobs) {
  if (!jobs.length) {
    jobsEl.innerHTML = `<p class="hint">No downloads yet.</p>`;
    return;
  }

  jobsEl.innerHTML = jobs
    .map((job) => {
      const archive =
        job.status === "complete"
          ? `<a class="archive" href="/api/downloads/${job.id}/archive" target="_blank" rel="noreferrer">Download zip</a>`
          : "";
      const detail = job.error || job.progress || "Queued.";
      const logText = logTextFor(job);
      return `
        <article class="job" data-job-id="${escapeHtml(job.id)}">
          <div class="job-main">
            <div class="job-url">${escapeHtml(job.url)}</div>
            <p class="job-progress">${escapeHtml(detail)}</p>
            <div class="job-actions">
              ${archive}
              <a class="archive" href="/api/downloads/${job.id}/log" target="_blank" rel="noreferrer">Open raw log</a>
              <button class="small-button" type="button" data-action="reload-log" data-job-id="${escapeHtml(job.id)}">Reload log</button>
              <button class="small-button" type="button" data-action="copy-log" data-job-id="${escapeHtml(job.id)}">Copy log</button>
            </div>
            <label class="log-label">
              Downloader log for copy/paste
              <textarea class="log-box" readonly spellcheck="false">${escapeHtml(logText)}</textarea>
            </label>
          </div>
          <span class="status ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span>
        </article>
      `;
    })
    .join("");
}

async function loadJobLog(jobId, force = false) {
  if (!force && state.logs[jobId]) {
    return;
  }

  try {
    state.logs[jobId] = await textApi(`/api/downloads/${jobId}/log`);
  } catch (error) {
    state.logs[jobId] = `Log unavailable yet: ${error.message}`;
  }
}

async function loadJobs() {
  if (!state.jobIds.length) {
    renderJobs([]);
    return;
  }

  const results = await Promise.allSettled(
    state.jobIds.map((id) => api(`/api/downloads/${id}`)),
  );
  const jobs = results
    .filter((result) => result.status === "fulfilled")
    .map((result) => result.value);

  await Promise.allSettled(
    jobs.map((job) => {
      const shouldRefresh = job.status === "running" || job.status === "failed" || job.status === "complete";
      return shouldRefresh ? loadJobLog(job.id, job.status === "running") : Promise.resolve();
    }),
  );

  renderJobs(jobs);
}

function startPolling() {
  if (state.poll) return;
  state.poll = setInterval(loadJobs, 3000);
}

async function copyLog(jobId) {
  await loadJobLog(jobId, true);
  await navigator.clipboard.writeText(state.logs[jobId] || "");
  setMessage("Log copied to clipboard.");
  await loadJobs();
}

jobsEl.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;

  const jobId = button.dataset.jobId;
  const action = button.dataset.action;
  button.disabled = true;

  try {
    if (action === "reload-log") {
      await loadJobLog(jobId, true);
      setMessage("Log reloaded.");
      await loadJobs();
    }
    if (action === "copy-log") {
      await copyLog(jobId);
    }
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    button.disabled = false;
  }
});

downloadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formEl = event.currentTarget;
  const form = new FormData(formEl);
  const submit = formEl.querySelector("button");

  submit.disabled = true;
  setMessage("Starting download...");
  try {
    const job = await api("/api/downloads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: form.get("url") }),
    });
    state.jobIds = [job.id, ...state.jobIds.filter((id) => id !== job.id)];
    saveJobIds();
    formEl.reset();
    setMessage("Download queued.");
    await loadJobs();
    startPolling();
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    submit.disabled = false;
  }
});

loadJobs();
startPolling();
