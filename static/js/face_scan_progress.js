(() => {
  const panel = document.getElementById("faceScanProgress");
  const progress = document.getElementById("faceScanBar");
  const count = document.getElementById("faceScanCount");
  const message = document.getElementById("faceScanMessage");
  if (!panel || !progress || !count || !message) return;

  const delay = Math.max(1000, Number(panel.dataset.pollMs) || 2500);
  let finishing = false;

  function updateProgress(result) {
    const total = Number(result.total) || 0;
    const complete = Number(result.complete) || 0;
    const queued = Number(result.queued) || 0;
    const processing = Number(result.processing) || 0;
    const failed = Number(result.failed) || 0;
    const pending = queued + processing;

    progress.max = Math.max(1, total);
    progress.value = complete;
    count.textContent = `${complete} of ${total} photos scanned`;
    progress.setAttribute("aria-valuetext", `${complete} of ${total} photos scanned`);

    if (pending > 0) {
      const activity = processing > 0 ? `${processing} processing` : "Waiting for the scanner";
      message.textContent = `${complete} complete · ${activity} · ${queued} queued · ${pending} remaining`;
      return;
    }

    if (finishing) return;
    finishing = true;
    if (failed > 0) {
      message.textContent = `Scan finished: ${complete} complete, ${failed} need attention. Updating your album…`;
    } else {
      message.textContent = `All ${complete} event photos scanned. Updating your matches…`;
      progress.value = total;
    }
    window.setTimeout(() => window.location.reload(), 900);
  }

  async function poll() {
    if (document.hidden || finishing) {
      window.setTimeout(poll, delay);
      return;
    }
    try {
      const response = await fetch(panel.dataset.statusUrl, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Scan status is temporarily unavailable.");
      updateProgress(await response.json());
    } catch (_) {
      message.textContent = "Checking scan progress…";
    }
    if (!finishing) window.setTimeout(poll, delay);
  }

  window.setTimeout(poll, delay);
})();
