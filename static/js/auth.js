document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.toggle-password').forEach((button) => {
    button.addEventListener('click', function () {
      const input = button.closest('.input-with-icon')?.querySelector('input');
      if (!input) return;
      const isHidden = input.type === 'password';
      input.type = isHidden ? 'text' : 'password';
      const icon = button.querySelector('i');
      if (icon) {
        icon.classList.toggle('fa-eye', !isHidden);
        icon.classList.toggle('fa-eye-slash', isHidden);
      }
      button.setAttribute('aria-label', isHidden ? 'Hide password' : 'Show password');
    });
  });

  const signupForm = document.querySelector('#signup-form');
  const signupPassword = signupForm?.querySelector('#signup-password');
  const strengthBar = signupForm?.querySelector('.strength-progress');
  const strengthText = signupForm?.querySelector('.strength-text');
  if (!signupPassword || !strengthBar || !strengthText) return;

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
});
