document.addEventListener('DOMContentLoaded', function () {
  // Password visibility toggle
  document.querySelectorAll('.toggle-password').forEach((button) => {
    button.addEventListener('click', function (e) {
      e.preventDefault();
      const container = button.closest('.input-with-icon') || button.parentNode;
      const input = container?.querySelector('input[type="password"], input[type="text"]');
      if (!input) return;

      const isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';

      const icon = button.querySelector('i');
      if (icon) {
        if (isPassword) {
          icon.classList.remove('fa-eye');
          icon.classList.add('fa-eye-slash');
        } else {
          icon.classList.remove('fa-eye-slash');
          icon.classList.add('fa-eye');
        }
      }
      button.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
    });
  });

  // Password strength meter
  const signupForm = document.querySelector('#signup-form');
  const signupPassword = signupForm?.querySelector('#signup-password');
  const strengthBar = signupForm?.querySelector('.strength-progress');
  const strengthText = signupForm?.querySelector('.strength-text');

  if (signupPassword && strengthBar && strengthText) {
    signupPassword.addEventListener('input', function () {
      const value = signupPassword.value;
      let score = 0;
      if (value.length >= 8) score += 30;
      if (/[a-z]/.test(value)) score += 15;
      if (/[A-Z]/.test(value)) score += 20;
      if (/\d/.test(value)) score += 15;
      if (/[^a-zA-Z0-9]/.test(value)) score += 20;
      strengthBar.style.width = `${score}%`;
      strengthBar.style.backgroundColor = score < 40 ? '#f56565' : score < 75 ? '#ed8936' : '#48bb78';
      strengthText.textContent = !value ? 'Password strength' : score < 40 ? 'Weak password' : score < 75 ? 'Moderate password' : 'Strong password';
    });
  }

  // Prevent multiple clicks and show loading state on login / signup submit
  document.querySelectorAll('.auth-form').forEach((form) => {
    form.addEventListener('submit', function (e) {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (!submitBtn) return;
      if (submitBtn.disabled) {
        e.preventDefault();
        return;
      }
      submitBtn.disabled = true;
      submitBtn.dataset.originalText = submitBtn.innerHTML;
      const isLogin = form.id === 'login-form';
      submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${isLogin ? 'Logging in...' : 'Creating account...'}`;
      submitBtn.style.opacity = '0.75';
      submitBtn.style.cursor = 'not-allowed';
    });
  });
});

// Re-enable submit buttons if navigated back via browser history (bfcache)
window.addEventListener('pageshow', function () {
  document.querySelectorAll('.auth-form button[type="submit"]').forEach((btn) => {
    btn.disabled = false;
    btn.style.opacity = '';
    btn.style.cursor = '';
    if (btn.dataset.originalText) {
      btn.innerHTML = btn.dataset.originalText;
    }
  });
});
