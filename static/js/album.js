document.addEventListener('DOMContentLoaded', function() {
  // Album data from URL params
  const urlParams = new URLSearchParams(window.location.search);
  const albumId = urlParams.get('id') || '1'; // Default to album ID 1 if not specified
  
  // Album mock data - in a real app, this would come from an API
  const albumData = {
    '1': {
      title: 'Johnson Wedding',
      date: 'February 28, 2025',
      photoCount: 156,
      photos: generateMockPhotos(156, 'Johnson Wedding')
    },
    '2': {
      title: 'Family Reunion',
      date: 'January 15, 2025',
      photoCount: 210,
      photos: generateMockPhotos(210, 'Family Reunion')
    },
    '3': {
      title: 'New Year\'s Party',
      date: 'January 1, 2025',
      photoCount: 124,
      photos: generateMockPhotos(124, 'New Year\'s Party')
    }
  };
  
  // Populate album details
  const album = albumData[albumId] || albumData['1']; // Fallback to first album if ID not found
  
  document.getElementById('albumTitle').textContent = album.title;
  document.getElementById('albumDate').textContent = album.date;
  document.getElementById('albumPhotoCount').textContent = album.photoCount;
  document.title = `${album.title} - EchoMoments`;
  
  // Load gallery photos
  const photoGallery = document.getElementById('photoGallery');
  
  // Simulate loading delay
  setTimeout(() => {
    photoGallery.innerHTML = ''; // Remove loading spinner
    
    // Show first 30 photos (pagination would be implemented in a real app)
    const photosToShow = album.photos.slice(0, 30);
    
    photosToShow.forEach((photo, index) => {
      const galleryItem = createGalleryItem(photo, index);
      photoGallery.appendChild(galleryItem);
    });
  }, 1200);
  
  // View toggle functionality
  const viewButtons = document.querySelectorAll('.view-button');
  
  viewButtons.forEach(button => {
    button.addEventListener('click', function() {
      // Remove active class from all buttons
      viewButtons.forEach(btn => btn.classList.remove('active'));
      // Add active class to clicked button
      this.classList.add('active');
      
      // Update gallery view
      const viewType = this.getAttribute('data-view');
      updateGalleryView(viewType);
    });
  });
  
  // Lightbox functionality
  const lightbox = document.getElementById('photoLightbox');
  const lightboxImage = document.getElementById('lightboxImage');
  const lightboxCaption = document.getElementById('lightboxCaption');
  const lightboxClose = document.querySelector('.lightbox-close');
  const lightboxPrev = document.querySelector('.lightbox-prev');
  const lightboxNext = document.querySelector('.lightbox-next');
  const currentPhotoIndex = document.getElementById('currentPhotoIndex');
  const totalPhotos = document.getElementById('totalPhotos');
  const faceTags = document.getElementById('faceTags');
  
  let currentIndex = 0;
  
  // Close lightbox
  lightboxClose.addEventListener('click', function() {
    lightbox.classList.remove('active');
  });
  
  // Close lightbox when clicking outside the content
  lightbox.addEventListener('click', function(event) {
    if (event.target === lightbox) {
      lightbox.classList.remove('active');
    }
  });
  
  // Next photo
  lightboxNext.addEventListener('click', function() {
    currentIndex = (currentIndex + 1) % album.photos.length;
    updateLightboxContent();
  });
  
  // Previous photo
  lightboxPrev.addEventListener('click', function() {
    currentIndex = (currentIndex - 1 + album.photos.length) % album.photos.length;
    updateLightboxContent();
  });
  
  // Keyboard navigation
  document.addEventListener('keydown', function(event) {
    if (!lightbox.classList.contains('active')) return;
    
    if (event.key === 'Escape') {
      lightbox.classList.remove('active');
    } else if (event.key === 'ArrowRight') {
      currentIndex = (currentIndex + 1) % album.photos.length;
      updateLightboxContent();
    } else if (event.key === 'ArrowLeft') {
      currentIndex = (currentIndex - 1 + album.photos.length) % album.photos.length;
      updateLightboxContent();
    }
  });
  
  // Update lightbox content based on current index
  function updateLightboxContent() {
    const photo = album.photos[currentIndex];
    lightboxImage.src = photo.imageUrl;
    lightboxCaption.textContent = photo.caption;
    currentPhotoIndex.textContent = currentIndex + 1;
    totalPhotos.textContent = album.photos.length;
    
    // Update face tags
    faceTags.innerHTML = '';
    if (photo.people && photo.people.length > 0) {
      photo.people.forEach(person => {
        const tag = document.createElement('span');
        tag.className = 'face-tag';
        tag.textContent = person;
        faceTags.appendChild(tag);
      });
    } else {
      faceTags.innerHTML = '<span class="text-muted">No people tagged</span>';
    }
  }
  
  // Helper function to create gallery items
  function createGalleryItem(photo, index) {
    const galleryItem = document.createElement('div');
    galleryItem.className = 'gallery-item';
    
    const img = document.createElement('img');
    img.src = photo.imageUrl;
    img.alt = photo.caption || 'Photo';
    img.loading = 'lazy';
    
    const overlay = document.createElement('div');
    overlay.className = 'gallery-item-overlay';
    
    const actions = document.createElement('div');
    actions.className = 'gallery-item-actions';
    
    const likeBtn = document.createElement('button');
    likeBtn.className = 'gallery-item-action';
    likeBtn.innerHTML = '<i class="far fa-heart"></i>';
    likeBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      this.innerHTML = '<i class="fas fa-heart"></i>';
      showToast('Added to favorites!', 'success');
    });
    
    const downloadBtn = document.createElement('button');
    downloadBtn.className = 'gallery-item-action';
    downloadBtn.innerHTML = '<i class="fas fa-download"></i>';
    downloadBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      showToast('Download started!', 'info');
    });
    
    actions.appendChild(likeBtn);
    actions.appendChild(downloadBtn);
    overlay.appendChild(actions);
    
    // Add photo to the item
    galleryItem.appendChild(img);
    galleryItem.appendChild(overlay);
    
    // Open lightbox when clicking on the item
    galleryItem.addEventListener('click', function() {
      currentIndex = index;
      updateLightboxContent();
      lightbox.classList.add('active');
    });
    
    return galleryItem;
  }
  
  // Update gallery view (grid or masonry)
  function updateGalleryView(viewType) {
    const gallery = document.getElementById('photoGallery');
    
    if (viewType === 'grid') {
      gallery.classList.remove('masonry');
    } else if (viewType === 'masonry') {
      gallery.classList.add('masonry');
    }
  }
  
  // Generate mock photos for demo purposes
  function generateMockPhotos(count, albumName) {
    const photos = [];
    const imageUrls = [
      'https://images.unsplash.com/photo-1519741497674-611481863552?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1511795409834-ef04bbd61622?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1522202176988-66273c2fd55f?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1539635278303-d4002c07eae3?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1506869640319-fe1a24fd76dc?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1467810563316-b5476525ef88?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1543269865-cbf427effbad?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1501386761578-eac5c94b800a?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1533777857889-4be7c70b33f7?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1521543832500-49e69fb2bea2?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1529156069898-49953e39b3ac?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80'
    ];
    
    const people = [
      'John Smith', 'Sarah Johnson', 'Michael Brown', 'Emily Davis', 
      'Robert Wilson', 'Jennifer Taylor', 'David Miller', 'Lisa Anderson',
      'James White', 'Patricia Thompson'
    ];
    
    for (let i = 0; i < count; i++) {
      const randomPeople = [];
      // Add 0-3 random people
      const peopleCount = Math.floor(Math.random() * 4);
      for (let j = 0; j < peopleCount; j++) {
        const randomPerson = people[Math.floor(Math.random() * people.length)];
        if (!randomPeople.includes(randomPerson)) {
          randomPeople.push(randomPerson);
        }
      }
      
      photos.push({
        id: `photo-${i}`,
        imageUrl: imageUrls[i % imageUrls.length],
        caption: `Photo ${i + 1} from ${albumName}`,
        timestamp: new Date(Date.now() - Math.floor(Math.random() * 10000000000)).toISOString(),
        people: randomPeople
      });
    }
    
    return photos;
  }
});

