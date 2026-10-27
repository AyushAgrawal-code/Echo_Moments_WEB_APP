document.addEventListener('DOMContentLoaded', function() {

  // ===== Common: Toggle password visibility =====
  const togglePasswordButton = document.querySelector('.toggle-password');
  const passwordInput = document.querySelector('input[type="password"]');
  
  if (togglePasswordButton && passwordInput) {
    const icon = togglePasswordButton.querySelector('i');
    togglePasswordButton.addEventListener('click', function () {
      const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
      passwordInput.setAttribute('type', type);
      
      // Toggle icon style
      icon.classList.toggle('fa-eye');
      icon.classList.toggle('fa-eye-slash');
    });
  }

  // ===== For SIGNUP page =====
  const signupForm = document.querySelector('#signup-form');
  const signupPassword = document.querySelector('#signup-password');

  if (signupForm) {
    // Password strength meter
    const strengthBar = document.querySelector('.strength-progress');
    const strengthText = document.querySelector('.strength-text');
    
    if (signupPassword && strengthBar && strengthText) {
      signupPassword.addEventListener('input', function() {
        const password = this.value;
        let strength = 0;
        
        if (password.length >= 8) strength += 25;
        if (password.match(/[a-z]/)) strength += 15;
        if (password.match(/[A-Z]/)) strength += 20;
        if (password.match(/[0-9]/)) strength += 20;
        if (password.match(/[^a-zA-Z0-9]/)) strength += 20;
        
        strength = Math.min(strength, 100);
        strengthBar.style.width = strength + '%';
        
        if (strength < 30) {
          strengthBar.style.backgroundColor = '#f56565';
          strengthText.textContent = 'Weak password';
        } else if (strength < 70) {
          strengthBar.style.backgroundColor = '#ed8936';
          strengthText.textContent = 'Moderate password';
        } else {
          strengthBar.style.backgroundColor = '#48bb78';
          strengthText.textContent = 'Strong password';
        }
      });
    }

    // Signup form submission
    signupForm.addEventListener('submit', function(e) {
      // e.preventDefault();

      const name = document.getElementById('signup-name').value;
      const email = document.getElementById('signup-email').value;
      const password = document.getElementById('signup-password').value;
      const termsAccepted = document.getElementById('terms').checked;

      if (!termsAccepted) {
        showToast('Please accept the Terms of Service', 'error');
        return;
      }

      console.log('Signup attempt with:', { name, email, password });

      showToast('Account created successfully!', 'success');

      setTimeout(() => {
        window.location.href = '/login';
      }, 1500);
    });
  }

  // ===== For LOGIN page =====
  const loginForm = document.querySelector('#login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', function(e) {
      // e.preventDefault();

      const email = document.getElementById('login-email').value;
      const password = document.getElementById('login-password').value;

      console.log('Login attempt with:', { email });

      showToast('Successfully logged in!', 'success');

      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 1500);
    });
  }

});
