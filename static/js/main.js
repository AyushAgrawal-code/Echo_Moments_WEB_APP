
  // Toast notification system
  function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Icon based on toast type
    let icon;
    switch(type) {
      case 'success':
        icon = '<i class="fas fa-check-circle" style="color: #68D391;"></i>';
        break;
      case 'error':
        icon = '<i class="fas fa-times-circle" style="color: #F56565;"></i>';
        break;
      case 'info':
      default:
        icon = '<i class="fas fa-info-circle" style="color: #4299E1;"></i>';
        break;
    }
    
    toast.innerHTML = `${icon} <span>${message}</span>`;
    toastContainer.appendChild(toast);
    
    // Remove toast after 5 seconds
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease-out forwards';
      setTimeout(() => {
        toastContainer.removeChild(toast);
      }, 300);
    }, 5000);
  }

document.addEventListener('DOMContentLoaded', function() {
  // Current year for copyright
  document.getElementById('currentYear').textContent = new Date().getFullYear();
  
  // Mobile menu toggle
  const menuIcon = document.getElementById('menu-icon');
  const mobileNav = document.getElementById('mobileNav');
 const signinButtons = document.querySelectorAll('.signin-btn');

signinButtons.forEach(button => {
  button.addEventListener('click', () => {
    const url = button.getAttribute('data-url'); // Django se injected URL
    window.location.href = url;
  });
});

 if (menuIcon){ menuIcon.addEventListener('click', function() {
    mobileNav.classList.toggle('active');
    if (mobileNav.classList.contains('active')) {
      menuIcon.classList.remove('fa-bars');
      menuIcon.classList.add('fa-times');
    } else {
      menuIcon.classList.remove('fa-times');
      menuIcon.classList.add('fa-bars');
    }
  });
}
  // Close mobile menu when clicking outside
  document.addEventListener('click', function(event) {
    const isClickInsideMenu = mobileNav.contains(event.target);
    const isClickOnMenuButton = menuIcon.contains(event.target);
    
    if (mobileNav.classList.contains('active') && !isClickInsideMenu && !isClickOnMenuButton) {
      mobileNav.classList.remove('active');
      menuIcon.classList.remove('fa-times');
      menuIcon.classList.add('fa-bars');
    }
  });
  
  // Album data for the grid
  const myAlbums = [
    {
      id: "1",
      title: "Johnson Wedding",
      date: "February 28, 2025",
      imageUrl: "https://images.unsplash.com/photo-1519741497674-611481863552?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
      photos: 156,
      type: "album"
    },
    {
      id: "2",
      title: "Family Reunion",
      date: "January 15, 2025",
      imageUrl: "https://images.unsplash.com/photo-1506869640319-fe1a24fd76dc?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
      photos: 210,
      type: "album"
    },
    {
      id: "3",
      title: "New Year's Party",
      date: "January 1, 2025",
      imageUrl: "https://images.unsplash.com/photo-1467810563316-b5476525ef88?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80",
      photos: 124,
      type: "album"
    }
  ];
  
  // Populate the album grid
  const albumGrid = document.querySelector('.album-grid');
  
  if (albumGrid) {
    myAlbums.forEach(album => {
      const albumCard = createEventCard(album);
      albumGrid.appendChild(albumCard);
    });
  }
  
  // QR Code Scanning functionality
  const scanQrBtn = document.getElementById('scanQrBtn');
  
  if (scanQrBtn) {
    scanQrBtn.addEventListener('click', function() {
      // In a real implementation, this would request camera access and scan a QR code
      // For this demo, we'll simulate with a success message
      showToast('QR scanning initiated. Please allow camera access.', 'info');
      
      // Simulate a successful scan after 3 seconds
      // setTimeout(() => {
      //   showToast('Successfully joined the event!', 'success');
      //   window.location.href = '#albums'; // Redirect to albums section
      // }, 3000);
    });
  }
  
  // Event code modal functionality
  const enterCodeBtn = document.getElementById('enterCodeBtn');
  const eventCodeModal = document.getElementById('eventCodeModal');
  const closeModal = document.querySelector('.close-modal');
  
  if (enterCodeBtn && eventCodeModal) {
    enterCodeBtn.addEventListener('click', function() {
      eventCodeModal.classList.add('active');
    });
    
    closeModal.addEventListener('click', function() {
      eventCodeModal.classList.remove('active');
    });
    
    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
      if (event.target === eventCodeModal) {
        eventCodeModal.classList.remove('active');
      }
    });
    
    // Handle event code submission
    const submitEventCodeBtn = eventCodeModal.querySelector('.echo-button-primary');
    
    submitEventCodeBtn.addEventListener('click', function() {
      const eventCodeInput = eventCodeModal.querySelector('.event-code-input');
      const eventCode = eventCodeInput.value.trim();
      
      if (eventCode === '') {
        showToast('Please enter an event code', 'error');
        return;
      }
      
      // Simulate event code validation
      if (eventCode === '123456' || eventCode.toLowerCase() === 'demo') {
        showToast('Successfully joined the event!', 'success');
        eventCodeModal.classList.remove('active');
        window.location.href = '#albums'; // Redirect to albums section
      } else {
        showToast('Invalid event code. Please try again.', 'error');
      }
    });
  }
  
  // Helper function to create event cards
  function createEventCard(event) {
    const card = document.createElement('div');
    card.className = 'event-card';
    
    const imageSection = document.createElement('div');
    imageSection.className = 'event-image';
    
    const img = document.createElement('img');
    img.src = event.imageUrl;
    img.alt = event.title;
    imageSection.appendChild(img);
    
    if (event.type === 'album' && event.photos) {
      const photoCount = document.createElement('div');
      photoCount.className = 'photo-count';
      photoCount.textContent = `${event.photos} photos`;
      imageSection.appendChild(photoCount);
    }
    
    const content = document.createElement('div');
    content.className = 'event-content';
    
    const dateDiv = document.createElement('div');
    dateDiv.className = 'event-date';
    dateDiv.innerHTML = `<i class="far fa-calendar"></i> <span>${event.date}</span>`;
    
    const title = document.createElement('h3');
    title.className = 'event-title';
    title.textContent = event.title;
    
    content.appendChild(dateDiv);
    content.appendChild(title);
    
    // Add appropriate button based on event type
    const button = document.createElement('button');
    
    switch(event.type) {
      case 'join':
        button.className = 'echo-button-primary full-width';
        button.textContent = 'Join Event';
        break;
      case 'host':
        button.className = 'echo-button-secondary full-width';
        button.textContent = 'Manage Event';
        break;
      case 'album':
      default:
        button.className = 'echo-button-outline full-width';
        button.textContent = 'View Album';
        break;
    }
    
    button.addEventListener('click', function() {
      showToast(`Clicked on "${event.title}"`, 'info');
    });
    
    content.appendChild(button);
    
    card.appendChild(imageSection);
    card.appendChild(content);
    
    return card;
  }
  
  const host_button =document.getElementById("host-event-button");
  const join_button =document.getElementById("join-event-button");

  if(host_button){host_button.addEventListener("click", function(){
    // console.log("clicked host hyrton")
    window.location.href = "/login";
    
  });}
  if(join_button){join_button.addEventListener("click", function(){
    window.location.href = '/#join';
  
  });}

});

