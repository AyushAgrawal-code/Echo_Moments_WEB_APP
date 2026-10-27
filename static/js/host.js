// static/js/host.js
// Host page JS for EchoMoments
// Handles wizard navigation, live preview, AJAX create-event, QR generation, share buttons

(function () {
  // --- Helpers ---
  function qs(sel, root = document) { return root.querySelector(sel); }
  function qsa(sel, root = document) { return Array.from((root || document).querySelectorAll(sel)); }
  function toast(msg) {
    // simple toast
    const container = qs('#toastContainer');
    if (!container) { alert(msg); return; }
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.classList.add('visible'), 20);
    setTimeout(() => {
      el.classList.remove('visible');
      setTimeout(() => el.remove(), 300);
    }, 3500);
  }

  // CSRF helper (from Django docs)
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        // Does this cookie string begin with the name we want?
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  const csrftoken = getCookie('csrftoken');

  // --- Wizard navigation ---
  function showStep(n) {
    qsa('.form-step').forEach(s => s.classList.remove('active'));
    const step = qs(`.form-step[data-step="${n}"]`);
    if (step) step.classList.add('active');
  }

  qsa('.next-step').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const next = btn.getAttribute('data-next');
      showStep(next);
    });
  });

  qsa('.prev-step').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const prev = btn.getAttribute('data-prev');
      showStep(prev);
    });
  });

  // --- Live Preview updates ---
  function updatePreview() {
    const title = qs('#eventName').value || 'Event Name';
    const date = qs('#eventDate').value ? (new Date(qs('#eventDate').value)).toLocaleDateString() : 'Event Date';
    const desc = qs('#eventDescription').value || 'Event description will appear here...';

    qs('#previewTitle').textContent = title;
    qs('#previewDate').innerHTML = `<i class="far fa-calendar"></i> ${date}`;
    qs('#previewDescription').textContent = desc;
  }

  ['#eventName','#eventDate','#eventDescription'].forEach(sel => {
    const el = qs(sel);
    if (el) el.addEventListener('input', updatePreview);
  });

  // cover photo preview
  const coverInput = qs('#coverPhotoUpload');
  const coverPreview = qs('#coverPhotoPreview');
  if (coverInput) {
    coverInput.addEventListener('change', function () {
      const file = this.files && this.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function (ev) {
        coverPreview.innerHTML = `<img src="${ev.target.result}" alt="cover" style="width:100%;height:100%;object-fit:cover;">`;
      };
      reader.readAsDataURL(file);
    });
  }

  // theme color preview (add border/indicator)
  qsa('input[name="theme_color"]').forEach(r => {
    r.addEventListener('change', function () {
      // no heavy UI changes now; we could set background color
      // (left minimal for CSS to manage)
    });
  });

  // --- Form submit (AJAX) ---
  const form = qs('#createEventForm');
  if (form) {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();

      // Basic validation
      const name = qs('#eventName').value.trim();
      const date = qs('#eventDate').value;
      if (!name || !date) {
        toast('Event name and date are required.');
        showStep(1);
        return;
      }

      const fd = new FormData(form);

      // For checkboxes, ensure they send something (HTML sends nothing if unchecked)
      // Our backend treats presence as True; so we leave default behavior.

      try {
        const resp = await fetch(window.ECHO.CREATE_EVENT_URL, {
          method: 'POST',
          body: fd,
          headers: {
            'X-CSRFToken': csrftoken
          },
        });

        const data = await resp.json();
        if (resp.ok && data && data.success && data.event_code) {
          // success — open modal, show code, generate QR, set view album button
          const code = data.event_code;
          qs('#eventCodeDisplay').textContent = code;
          qs('#previewCode').textContent = code;

          // generate QR if library present
          const qrContainer = qs('#eventQRCode');
          if (window.QRCode) {
            // clear
            qrContainer.innerHTML = '';
            new QRCode(qrContainer, {
              text: data.join_url || (window.location.origin + "/events/join/?event_code=" + encodeURIComponent(code)),
              width: 160,
              height: 160
            });
          } else if (typeof generateQRCode === 'function') {
            try { generateQRCode((data.join_url || (window.location.origin + "/events/join/?event_code=" + encodeURIComponent(code))), 'eventQRCode'); } catch (e) {}
          } else {
            // fallback: simple placeholder
            const placeholder = document.createElement('div');
            placeholder.className = 'qr-placeholder';
            placeholder.innerHTML = '<i class="fas fa-qrcode"></i>';
            qrContainer.appendChild(placeholder);
          }

          // Also generate small preview QR
          const previewQR = qs('#previewQRplaceholder');
          if (previewQR) {
            previewQR.innerHTML = '';
            if (window.QRCode) {
              new QRCode(previewQR, {
                text: data.join_url || (window.location.origin + "/events/join/?event_code=" + encodeURIComponent(code)),
                width: 96,
                height: 96
              });
            }
          }

          // show modal
          qs('#successModal').style.display = 'block';

          // set view album btn
          const viewBtn = qs('#viewAlbumBtn');
          if (viewBtn) {
            viewBtn.onclick = function () {
              window.location.href = data.url;
            };
          }

          // copy link button
          const copyBtn = qs('#copy-link');
          if (copyBtn) {
            copyBtn.onclick = function () {
              const link = (data.join_url || (window.location.origin + "/events/join/?event_code=" + encodeURIComponent(code)));
              navigator.clipboard?.writeText(link);
              toast('Event link copied to clipboard.');
            };
          }

          // whatsapp share
          const waBtn = qs('#share-button-whatsapp');
          if (waBtn) {
            waBtn.onclick = function () {
              const link = encodeURIComponent((data.join_url || (window.location.origin + "/events/join/?event_code=" + encodeURIComponent(code))));
              const text = encodeURIComponent("Join my event: " + (qs('#eventName').value || '') + " — " + link);
              window.open("https://wa.me/?text=" + text, "_blank");
            };
          }

          // email share
          const emailBtn = qs('#share-button-email');
          if (emailBtn) {
            emailBtn.onclick = function () {
              const subject = encodeURIComponent("Join my event on EchoMoments");
              const body = encodeURIComponent("Join my event: " + (qs('#eventName').value || '') + "\n\n" + (data.join_url || (window.location.origin + "/events/join/?event_code=" + encodeURIComponent(code))));
              window.location.href = "mailto:?subject=" + subject + "&body=" + body;
            };
          }

          toast('Event created: ' + code);

        } else {
          // server returned success=false or missing event_code
          const err = (data && data.error) ? data.error : 'Server error while creating event.';
          toast(err);
        }

      } catch (err) {
        console.error(err);
        toast('Network or server error.');
      }
    });
  }

  // Close modal when clicking outside or pressing Esc
  document.addEventListener('click', function (e) {
    const modal = qs('#successModal');
    if (!modal) return;
    if (modal.style.display === 'block' && !modal.querySelector('.modal-content').contains(e.target)) {
      modal.style.display = 'none';
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      const modal = qs('#successModal');
      if (modal) modal.style.display = 'none';
    }
  });

  // small initial preview update
  updatePreview();

})();


