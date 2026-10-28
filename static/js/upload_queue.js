(() => {
  const form = document.getElementById("uploadForm");
  if (!form) return;

  const fileInput = form.querySelector('input[type="file"]');
  const submitButton = form.querySelector("button[type='submit'], button:not([type])");
  const status = document.getElementById("uploadStatus");
  let list = document.getElementById("uploadQueue");
  const maxParallelUploads = 3;

  if (!list) {
    list = document.createElement("ul");
    list.id = "uploadQueue";
    list.setAttribute("aria-live", "polite");
    form.insertAdjacentElement("afterend", list);
  }

  const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  async function runWithConcurrency(items, limit, callback) {
    let nextIndex = 0;
    let successes = 0;
    const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
      while (nextIndex < items.length) {
        const index = nextIndex;
        nextIndex += 1;
        if (await callback(items[index])) successes += 1;
      }
    });
    await Promise.all(workers);
    return successes;
  }

  function makeUploadId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
      const random = Math.floor(Math.random() * 16);
      return (character === "x" ? random : (random & 0x3) | 0x8).toString(16);
    });
  }

  function addQueueItem(file) {
    const row = document.createElement("li");
    const label = document.createElement("span");
    const detail = document.createElement("span");
    label.textContent = file.name;
    detail.textContent = "Waiting to upload";
    row.append(label, document.createTextNode(" — "), detail);
    list.prepend(row);
    return { row, detail };
  }

  function uploadFile(file, uploadId, item) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const body = new FormData();
      body.append("images", file, file.name);
      body.append("client_upload_id", uploadId);

      xhr.open("POST", form.dataset.uploadUrl);
      xhr.timeout = 120000;
      if (form.dataset.csrf) xhr.setRequestHeader("X-CSRFToken", form.dataset.csrf);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          item.detail.textContent = `Uploading ${percent}%`;
        } else {
          item.detail.textContent = "Uploading…";
        }
      };
      xhr.onload = () => {
        let payload = {};
        try { payload = JSON.parse(xhr.responseText); } catch (_) { /* handled below */ }
        if (xhr.status >= 200 && xhr.status < 300 && payload.job_id) {
          resolve(payload);
          return;
        }
        const error = new Error(payload.error || "Upload failed.");
        error.retryable = xhr.status === 0 || xhr.status === 408 || xhr.status >= 500;
        reject(error);
      };
      xhr.onerror = () => {
        const error = new Error("Network interrupted.");
        error.retryable = true;
        reject(error);
      };
      xhr.ontimeout = () => {
        const error = new Error("Upload timed out.");
        error.retryable = true;
        reject(error);
      };
      xhr.send(body);
    });
  }

  function addRetryButton(jobId, item) {
    if (!form.dataset.retryUrlTemplate || item.row.querySelector(".retry-upload-job")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "retry-upload-job echo-button-outline";
    button.textContent = "Retry this photo";
    button.addEventListener("click", async () => {
      button.disabled = true;
      item.detail.textContent = "Adding this photo back to the queue…";
      const url = form.dataset.retryUrlTemplate.replace(
        "00000000-0000-0000-0000-000000000000",
        jobId,
      );
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "X-CSRFToken": form.dataset.csrf || "", "X-Requested-With": "XMLHttpRequest" },
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not retry this photo.");
        button.remove();
        item.detail.textContent = "Retry queued";
        const completed = await waitForProcessing(jobId, item);
        if (completed) window.setTimeout(() => window.location.reload(), 900);
      } catch (error) {
        item.detail.textContent = error.message;
        button.disabled = false;
      }
    });
    item.row.append(document.createTextNode(" "), button);
  }

  async function submitWithRetry(file, item) {
    const uploadId = makeUploadId();
    const maxAttempts = 3;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        item.detail.textContent = attempt === 1 ? "Starting upload…" : `Retry ${attempt - 1} of ${maxAttempts - 1}…`;
        const result = await uploadFile(file, uploadId, item);
        item.detail.textContent = "Queued for processing";
        return result;
      } catch (error) {
        if (!error.retryable || attempt === maxAttempts) throw error;
        await wait(500 * (2 ** (attempt - 1)));
      }
    }
    throw new Error("Could not upload this photo.");
  }

  async function waitForProcessing(jobId, item) {
    const url = form.dataset.statusUrlTemplate.replace("00000000-0000-0000-0000-000000000000", jobId);
    const deadline = Date.now() + 10 * 60 * 1000;
    let pollDelay = 500;
    while (Date.now() < deadline) {
      await wait(pollDelay);
      pollDelay = Math.min(2000, Math.round(pollDelay * 1.5));
      const response = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not check upload status.");
      if (result.status === "complete") {
        item.detail.textContent = "Complete";
        return true;
      }
      if (result.status === "failed" || result.status === "cancelled") {
        item.detail.textContent = result.error || (result.status === "cancelled" ? "Upload cancelled." : "This photo needs another save attempt.");
        if (result.status === "failed" && result.can_retry) addRetryButton(jobId, item);
        return false;
      }
      item.detail.textContent = result.status === "processing" ? "Processing…" : "Queued — waiting for a worker…";
    }
    item.detail.textContent = "Still queued; you can return later to check it.";
    return false;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const files = Array.from(fileInput.files || []);
    if (!files.length) return;

    submitButton.disabled = true;
    fileInput.disabled = true;
    status.textContent = `Uploading ${files.length} photo(s) with up to ${maxParallelUploads} in parallel…`;

    // Keep file requests independent, but do not make every member of a large batch wait in line.
    const completed = await runWithConcurrency(files, maxParallelUploads, async (file) => {
      const item = addQueueItem(file);
      try {
        const result = await submitWithRetry(file, item);
        item.detail.textContent = "Uploaded; waiting for the private album save…";
        return await waitForProcessing(result.job_id, item);
      } catch (error) {
        item.detail.textContent = error.message;
        return false;
      }
    });

    status.textContent = completed
      ? `${completed} photo(s) saved. Failed files can be selected again to retry.`
      : "Uploads are queued or need attention; failed photos can be retried from the queue.";
    submitButton.disabled = false;
    fileInput.disabled = false;
    if (completed) window.setTimeout(() => window.location.reload(), 900);
  });
})();
