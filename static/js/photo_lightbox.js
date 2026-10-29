(() => {
  const triggers = document.querySelectorAll(".photo-preview-trigger");
  if (!triggers.length || typeof HTMLDialogElement === "undefined") return;

  const dialog = document.createElement("dialog");
  dialog.className = "photo-lightbox";
  dialog.setAttribute("aria-label", "Photo preview");

  const image = document.createElement("img");
  image.alt = "Full-size event photo";

  const closeButton = document.createElement("button");
  closeButton.className = "photo-lightbox-close";
  closeButton.type = "button";
  closeButton.setAttribute("aria-label", "Close photo preview");
  closeButton.textContent = "×";

  dialog.append(closeButton, image);
  document.body.append(dialog);

  closeButton.addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const thumbnail = trigger.querySelector("img");
      image.alt = thumbnail?.alt || "Full-size event photo";
      image.src = trigger.href;
      dialog.showModal();
      closeButton.focus();
    });
  });
})();
