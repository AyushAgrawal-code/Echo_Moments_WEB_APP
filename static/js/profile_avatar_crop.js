(() => {
  const input = document.getElementById("id_profile_pic");
  const form = document.getElementById("avatarForm");
  const dialog = document.getElementById("avatarCropDialog");
  const stage = document.getElementById("avatarCropStage");
  const preview = document.getElementById("avatarCropPreview");
  const zoomInput = document.getElementById("avatarCropZoom");
  const saveButton = document.getElementById("saveAvatarCrop");
  const closeButton = document.getElementById("closeAvatarCrop");
  const cancelButton = document.getElementById("cancelAvatarCrop");

  if (!input || !form || !dialog || !stage || !preview || !zoomInput || !saveButton) return;

  let sourceFile = null;
  let sourceUrl = "";
  let naturalWidth = 0;
  let naturalHeight = 0;
  let offsetX = 0;
  let offsetY = 0;
  let dragPoint = null;
  let acceptedCrop = false;

  function cropMetrics(zoom = Number(zoomInput.value)) {
    const size = stage.clientWidth;
    const baseScale = Math.max(size / naturalWidth, size / naturalHeight);
    const scale = baseScale * zoom;
    const renderedWidth = naturalWidth * scale;
    const renderedHeight = naturalHeight * scale;
    const maxX = Math.max(0, (renderedWidth - size) / 2);
    const maxY = Math.max(0, (renderedHeight - size) / 2);
    offsetX = Math.max(-maxX, Math.min(maxX, offsetX));
    offsetY = Math.max(-maxY, Math.min(maxY, offsetY));
    return { size, scale, renderedWidth, renderedHeight };
  }

  function renderCrop() {
    const { size } = cropMetrics();
    preview.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${Number(zoomInput.value)})`;
    stage.style.setProperty("--crop-size", `${size}px`);
  }

  function cleanUpPreview() {
    if (sourceUrl) URL.revokeObjectURL(sourceUrl);
    sourceUrl = "";
    preview.removeAttribute("src");
    sourceFile = null;
    naturalWidth = 0;
    naturalHeight = 0;
    offsetX = 0;
    offsetY = 0;
    dragPoint = null;
  }

  input.addEventListener("change", () => {
    const file = input.files?.[0];
    if (!file) return;

    sourceFile = file;
    acceptedCrop = false;
    offsetX = 0;
    offsetY = 0;
    zoomInput.value = "1.45";
    sourceUrl = URL.createObjectURL(file);
    preview.onload = () => {
      naturalWidth = preview.naturalWidth;
      naturalHeight = preview.naturalHeight;
      if (!dialog.open) dialog.showModal();
      requestAnimationFrame(renderCrop);
    };
    preview.onerror = () => {
      window.alert("This photo could not be opened. Please choose another image.");
      cleanUpPreview();
      input.value = "";
    };
    preview.src = sourceUrl;
  });

  zoomInput.addEventListener("input", renderCrop);

  stage.addEventListener("pointerdown", (event) => {
    if (!naturalWidth) return;
    dragPoint = { x: event.clientX, y: event.clientY };
    stage.classList.add("is-dragging");
    stage.setPointerCapture(event.pointerId);
  });

  stage.addEventListener("pointermove", (event) => {
    if (!dragPoint) return;
    offsetX += event.clientX - dragPoint.x;
    offsetY += event.clientY - dragPoint.y;
    dragPoint = { x: event.clientX, y: event.clientY };
    renderCrop();
  });

  function stopDragging() {
    dragPoint = null;
    stage.classList.remove("is-dragging");
  }

  stage.addEventListener("pointerup", stopDragging);
  stage.addEventListener("pointercancel", stopDragging);

  function cancelCrop() {
    acceptedCrop = false;
    if (dialog.open) dialog.close();
  }

  closeButton?.addEventListener("click", cancelCrop);
  cancelButton?.addEventListener("click", cancelCrop);
  dialog.addEventListener("close", () => {
    if (!acceptedCrop) input.value = "";
    cleanUpPreview();
  });

  saveButton.addEventListener("click", () => {
    if (!sourceFile || !naturalWidth || !naturalHeight) return;
    const { size, scale } = cropMetrics();
    const outputSize = 512;
    const outputScale = outputSize / size;
    const canvas = document.createElement("canvas");
    canvas.width = outputSize;
    canvas.height = outputSize;
    const context = canvas.getContext("2d", { alpha: sourceFile.type === "image/png" });
    if (!context) {
      window.alert("Your browser could not prepare this photo. Please try another image.");
      return;
    }
    if (sourceFile.type !== "image/png") {
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, outputSize, outputSize);
    }

    const drawScale = scale * outputScale;
    const x = (outputSize - naturalWidth * drawScale) / 2 + offsetX * outputScale;
    const y = (outputSize - naturalHeight * drawScale) / 2 + offsetY * outputScale;
    context.drawImage(preview, x, y, naturalWidth * drawScale, naturalHeight * drawScale);

    const outputType = sourceFile.type === "image/png" ? "image/png" : "image/jpeg";
    canvas.toBlob((blob) => {
      if (!blob) {
        window.alert("Your browser could not prepare this photo. Please try again.");
        return;
      }
      const extension = outputType === "image/png" ? "png" : "jpg";
      const croppedFile = new File([blob], `profile-photo.${extension}`, {
        type: outputType,
        lastModified: Date.now(),
      });
      const transfer = new DataTransfer();
      transfer.items.add(croppedFile);
      input.files = transfer.files;
      acceptedCrop = true;
      dialog.close();
      form.requestSubmit();
    }, outputType, outputType === "image/jpeg" ? 0.92 : undefined);
  });
})();
