const state = {
  jobIds: JSON.parse(localStorage.getItem("jobIds") || "[]"),
  logs: {},
  poll: null,
};

const downloadForm = document.querySelector("#downloadForm");
const jobsEl = document.querySelector("#jobs");
const messageEl = document.querySelector("#message");
const latestLogBox = document.querySelector("#latestLogBox");
const reloadLatestLogButton = document.querySelector("#reloadLatestLog");
const copyLatestLogButton = document.querySelector("#copyLatestLog");

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

function updateLatestLogBox(text) {
  if (latestLogBox) {
    latestLogBox.value = text || "No downloader log loaded yet.";
  }
}

function newestJobId() {
  return state.jobIds[0] || null;
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

async function loadLatestLog(force = true) {
  let jobId = newestJobId();
  if (!jobId) {
    const jobs = await loadRecentJobs();
    jobId = jobs[0]?.id || null;
  }

  if (!jobId) {
    updateLatestLogBox("No jobs found yet. Start a job first.");
    return;
  }

  await loadJobLog(jobId, force);
  updateLatestLogBox(state.logs[jobId]);
}

async function loadRecentJobs() {
  const jobs = await api("/api/downloads");
  state.jobIds = jobs.map((job) => job.id);
  saveJobIds();
  return jobs;
}

async function loadJobs() {
  let jobs = [];

  if (!state.jobIds.length) {
    try {
      jobs = await loadRecentJobs();
    } catch (error) {
      renderJobs([]);
      return;
    }
  } else {
    const results = await Promise.allSettled(
      state.jobIds.map((id) => api(`/api/downloads/${id}`)),
    );
    jobs = results
      .filter((result) => result.status === "fulfilled")
      .map((result) => result.value);
  }

  await Promise.allSettled(
    jobs.map((job) => {
      const shouldRefresh = job.status === "running" || job.status === "failed" || job.status === "complete";
      return shouldRefresh ? loadJobLog(job.id, job.status === "running") : Promise.resolve();
    }),
  );

  const latestId = newestJobId();
  if (latestId && state.logs[latestId]) {
    updateLatestLogBox(state.logs[latestId]);
  }

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
      updateLatestLogBox(state.logs[jobId]);
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

reloadLatestLogButton?.addEventListener("click", async () => {
  reloadLatestLogButton.disabled = true;
  try {
    await loadLatestLog(true);
    setMessage("Latest log reloaded.");
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    reloadLatestLogButton.disabled = false;
  }
});

copyLatestLogButton?.addEventListener("click", async () => {
  copyLatestLogButton.disabled = true;
  try {
    await navigator.clipboard.writeText(latestLogBox?.value || "");
    setMessage("Latest log copied to clipboard.");
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    copyLatestLogButton.disabled = false;
  }
});

downloadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formEl = event.currentTarget;
  const form = new FormData(formEl);
  const submit = formEl.querySelector("button");

  submit.disabled = true;
  setMessage("Starting download...");
  updateLatestLogBox("Job submitted. Waiting for downloader log...");
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
