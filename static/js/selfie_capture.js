(() => {
  const form = document.getElementById("faceEnrollmentForm");
  if (!form) return;

  const fileInput = document.getElementById("selfie");
  const uploadButton = document.getElementById("chooseSelfieUpload");
  const cameraButton = document.getElementById("chooseSelfieCamera");
  const uploadPanel = document.getElementById("selfieUploadPanel");
  const cameraPanel = document.getElementById("selfieCameraPanel");
  const video = document.getElementById("selfieCameraVideo");
  const canvas = document.getElementById("selfieCaptureCanvas");
  const startCameraButton = document.getElementById("startSelfieCamera");
  const captureButton = document.getElementById("captureSelfie");
  const cameraStatus = document.getElementById("selfieStatus");
  const previewPanel = document.getElementById("selfiePreviewPanel");
  const preview = document.getElementById("selfiePreview");
  const clearButton = document.getElementById("clearSelfie");
  const maxBytes = 10 * 1024 * 1024;
  let cameraStream = null;
  let previewUrl = "";
  let currentMode = "upload";

  function stopCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
      cameraStream = null;
    }
    video.srcObject = null;
    video.hidden = true;
    captureButton.hidden = true;
    captureButton.disabled = true;
    startCameraButton.hidden = false;
    startCameraButton.disabled = false;
    startCameraButton.textContent = "Enable camera";
  }

  function clearPreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = "";
    preview.removeAttribute("src");
    previewPanel.hidden = true;
  }

  function clearSelection() {
    fileInput.value = "";
    fileInput.setCustomValidity("");
    clearPreview();
  }

  function setMode(mode) {
    currentMode = mode;
    const cameraMode = mode === "camera";
    uploadButton.setAttribute("aria-pressed", String(!cameraMode));
    cameraButton.setAttribute("aria-pressed", String(cameraMode));
    uploadPanel.hidden = cameraMode;
    cameraPanel.hidden = !cameraMode;
    fileInput.required = false;
    cameraStatus.textContent = cameraMode
      ? "Select Enable camera to ask your browser for camera access. You can also use the upload option; many phones offer Take photo in the image picker."
      : "";
    clearSelection();
    stopCamera();
  }

  function showPreview(file) {
    clearPreview();
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    previewPanel.hidden = false;
  }

  async function requestCamera() {
    if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
      cameraStatus.textContent = "This browser cannot open the camera here. Use Upload a selfie; on a phone, the image picker may offer Take photo. Camera capture requires HTTPS or localhost.";
      return;
    }

    startCameraButton.disabled = true;
    cameraStatus.textContent = "Waiting for camera permission…";
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "user" },
          width: { ideal: 1280 },
          height: { ideal: 960 },
        },
      });
      video.srcObject = cameraStream;
      video.hidden = false;
      await video.play();
      captureButton.hidden = false;
      captureButton.disabled = false;
      startCameraButton.hidden = true;
      cameraStatus.textContent = "Frame yourself in the preview, then take a still photo. Live video is not uploaded.";
    } catch (error) {
      stopCamera();
      if (error && error.name === "NotAllowedError") {
        cameraStatus.textContent = "Camera access was denied. Allow camera access in your browser settings, or use Upload a selfie.";
      } else if (error && error.name === "NotFoundError") {
        cameraStatus.textContent = "No camera was found. Use Upload a selfie instead.";
      } else {
        cameraStatus.textContent = "The camera could not be opened. Check browser permission and use HTTPS or localhost, or use Upload a selfie.";
      }
    }
  }

  function canvasToBlob(quality) {
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
  }

  async function captureStill() {
    if (!video.videoWidth || !video.videoHeight) {
      cameraStatus.textContent = "Wait for the camera preview to appear, then try again.";
      return;
    }

    const scale = Math.min(1, Math.sqrt(30_000_000 / (video.videoWidth * video.videoHeight)));
    canvas.width = Math.max(80, Math.floor(video.videoWidth * scale));
    canvas.height = Math.max(80, Math.floor(video.videoHeight * scale));
    const context = canvas.getContext("2d", { alpha: false });
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    let blob = null;
    for (const quality of [0.9, 0.82, 0.74, 0.66, 0.58]) {
      blob = await canvasToBlob(quality);
      if (blob && blob.size <= maxBytes) break;
    }
    if (!blob || blob.size > maxBytes) {
      cameraStatus.textContent = "This camera image is over 10 MB. Use a lower-resolution camera or choose a smaller photo.";
      return;
    }

    try {
      const file = new File([blob], "selfie-capture.jpg", { type: "image/jpeg", lastModified: Date.now() });
      const transfer = new DataTransfer();
      transfer.items.add(file);
      fileInput.files = transfer.files;
      fileInput.setCustomValidity("");
      showPreview(file);
      stopCamera();
      startCameraButton.textContent = "Retake selfie";
      cameraStatus.textContent = "Selfie ready. Review the preview, then choose Find my photos.";
    } catch (_) {
      cameraStatus.textContent = "This browser could not attach the camera photo to the form. Use Upload a selfie; your phone's image picker may offer Take photo.";
    }
  }

  uploadButton.addEventListener("click", () => {
    if (currentMode !== "upload") setMode("upload");
    fileInput.click();
  });
  cameraButton.addEventListener("click", () => setMode("camera"));
  startCameraButton.addEventListener("click", () => {
    clearSelection();
    requestCamera();
  });
  captureButton.addEventListener("click", captureStill);
  clearButton.addEventListener("click", () => {
    clearSelection();
    cameraStatus.textContent = currentMode === "camera" ? "Selfie removed. Enable the camera to take another." : "Selfie removed. Choose a photo to continue.";
  });

  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    clearPreview();
    fileInput.setCustomValidity("");
    if (!file) return;
    if (file.size > maxBytes) {
      fileInput.setCustomValidity("Choose an image that is 10 MB or smaller.");
      cameraStatus.textContent = "This image is over 10 MB. Choose a smaller selfie.";
      previewPanel.hidden = true;
      return;
    }
    showPreview(file);
    cameraStatus.textContent = "Selfie selected. Review it before continuing.";
  });

  form.addEventListener("submit", (event) => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      event.preventDefault();
      if (currentMode === "upload") {
        cameraStatus.textContent = "Choose a selfie photo before continuing.";
        uploadButton.focus();
      } else {
        cameraStatus.textContent = "Take a selfie or switch to Upload a selfie before continuing.";
        startCameraButton.focus();
      }
      return;
    }
    if (file.size > maxBytes) {
      event.preventDefault();
      fileInput.setCustomValidity("Choose an image that is 10 MB or smaller.");
      fileInput.reportValidity();
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopCamera();
  });
  window.addEventListener("pagehide", () => {
    stopCamera();
    clearPreview();
  });
})();
