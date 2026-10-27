
// Centralized Album JavaScript
let albumData = {
    eventName: "Wedding Reception",
    totalPhotos: 24,
    contributors: 8,
    currentFilter: 'all',
    currentSort: 'newest',
    currentView: 'grid',
    photos: [],
    slideshowIndex: 0,
    slideshowAutoplay: true,
    slideshowInterval: null
};

// Initialize album
document.addEventListener('DOMContentLoaded', function() {
    loadPhotos();
    initializeEventListeners();
});

// Load all photos
function loadPhotos() {
    // Sample photo data
    const samplePhotos = [
        {
            src: 'https://images.unsplash.com/photo-1469371670807-013ccf25f16a?w=800&h=800&fit=crop&crop=faces',
            uploader: 'sarah',
            uploaderName: 'Sarah Johnson',
            timestamp: new Date(Date.now() - 2 * 60 * 1000),
            likes: 5,
            id: 1
        },
        {
            src: 'https://images.unsplash.com/photo-1511285560929-80b456fea0bc?w=800&h=800&fit=crop&crop=faces',
            uploader: 'mike',
            uploaderName: 'Mike Chen',
            timestamp: new Date(Date.now() - 4 * 60 * 1000),
            likes: 8,
            id: 2
        },
        {
            src: 'https://images.unsplash.com/photo-1465495976277-4387d4b0e4a6?w=800&h=800&fit=crop&crop=faces',
            uploader: 'emily',
            uploaderName: 'Emily Davis',
            timestamp: new Date(Date.now() - 6 * 60 * 1000),
            likes: 3,
            id: 3
        },
        {
            src: 'https://images.unsplash.com/photo-1583939003579-730e3918a45a?w=800&h=800&fit=crop&crop=faces',
            uploader: 'sarah',
            uploaderName: 'Sarah Johnson',
            timestamp: new Date(Date.now() - 8 * 60 * 1000),
            likes: 6,
            id: 4
        },
        {
            src: 'https://images.unsplash.com/photo-1606216794074-735e91aa2c92?w=800&h=800&fit=crop&crop=faces',
            uploader: 'mike',
            uploaderName: 'Mike Chen',
            timestamp: new Date(Date.now() - 10 * 60 * 1000),
            likes: 4,
            id: 5
        },
        {
            src: 'https://images.unsplash.com/photo-1519741497674-611481863552?w=800&h=800&fit=crop&crop=faces',
            uploader: 'host',
            uploaderName: 'Host',
            timestamp: new Date(Date.now() - 12 * 60 * 1000),
            likes: 9,
            id: 6
        },
        {
            src: 'https://images.unsplash.com/photo-1537633552985-df8429e8048b?w=800&h=800&fit=crop&crop=faces',
            uploader: 'emily',
            uploaderName: 'Emily Davis',
            timestamp: new Date(Date.now() - 15 * 60 * 1000),
            likes: 7,
            id: 7
        },
        {
            src: 'https://images.unsplash.com/photo-1545558014-8692077e9b5c?w=800&h=800&fit=crop&crop=faces',
            uploader: 'mike',
            uploaderName: 'Mike Chen',
            timestamp: new Date(Date.now() - 18 * 60 * 1000),
            likes: 12,
            id: 8
        },
        {
            src: 'https://images.unsplash.com/photo-1522673607200-164d1b6ce486?w=800&h=800&fit=crop&crop=faces',
            uploader: 'sarah',
            uploaderName: 'Sarah Johnson',
            timestamp: new Date(Date.now() - 20 * 60 * 1000),
            likes: 2,
            id: 9
        },
        {
            src: 'https://images.unsplash.com/photo-1516975080664-ed2fc6a32937?w=800&h=800&fit=crop&crop=faces',
            uploader: 'host',
            uploaderName: 'Host',
            timestamp: new Date(Date.now() - 25 * 60 * 1000),
            likes: 11,
            id: 10
        },
        {
            src: 'https://images.unsplash.com/photo-1520854221256-17451cc331bf?w=800&h=800&fit=crop&crop=faces',
            uploader: 'mike',
            uploaderName: 'Mike Chen',
            timestamp: new Date(Date.now() - 28 * 60 * 1000),
            likes: 6,
            id: 11
        },
        {
            src: 'https://images.unsplash.com/photo-1594736797933-d0601ba2fe65?w=800&h=800&fit=crop&crop=faces',
            uploader: 'sarah',
            uploaderName: 'Sarah Johnson',
            timestamp: new Date(Date.now() - 30 * 60 * 1000),
            likes: 15,
            id: 12
        }
    ];
    
    albumData.photos = samplePhotos;
    renderPhotos();
}

// Render photos based on current filters
function renderPhotos() {
    let filteredPhotos = [...albumData.photos];
    
    // Apply filter
    if (albumData.currentFilter !== 'all') {
        filteredPhotos = filteredPhotos.filter(photo => photo.uploader === albumData.currentFilter);
    }
    
    // Apply sort
    switch (albumData.currentSort) {
        case 'newest':
            filteredPhotos.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            break;
        case 'oldest':
            filteredPhotos.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            break;
        case 'uploader':
            filteredPhotos.sort((a, b) => a.uploaderName.localeCompare(b.uploaderName));
            break;
        case 'most-liked':
            filteredPhotos.sort((a, b) => b.likes - a.likes);
            break;
    }
    
    const photoAlbum = document.getElementById('photoAlbum');
    photoAlbum.innerHTML = '';
    
    filteredPhotos.forEach(photo => {
        const photoDiv = document.createElement('div');
        photoDiv.className = 'photo-item';
        photoDiv.setAttribute('data-uploader', photo.uploader);
        photoDiv.setAttribute('data-timestamp', photo.timestamp.getTime());
        photoDiv.onclick = () => openPhotoModal(photo);
        
        const timeAgo = getTimeAgo(photo.timestamp);
        
        photoDiv.innerHTML = `
            <img src="${photo.src}" alt="${photo.uploaderName} photo">
            <div class="photo-overlay">
                <p>${photo.uploaderName} • ${timeAgo}</p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
                    <span>❤️ ${photo.likes}</span>
                    <button onclick="event.stopPropagation(); likePhoto(this, ${photo.id})" style="background: none; border: none; color: white; cursor: pointer;">👍</button>
                </div>
            </div>
        `;
        
        photoAlbum.appendChild(photoDiv);
    });
    
    // Update view mode if needed
    updateViewMode();
}

// Initialize event listeners
function initializeEventListeners() {
    document.getElementById('uploaderFilter').addEventListener('change', filterPhotos);
    document.getElementById('sortFilter').addEventListener('change', sortPhotos);
    document.getElementById('viewMode').addEventListener('change', changeViewMode);
}

// Filter photos
function filterPhotos() {
    albumData.currentFilter = document.getElementById('uploaderFilter').value;
    renderPhotos();
}

// Sort photos
function sortPhotos() {
    albumData.currentSort = document.getElementById('sortFilter').value;
    renderPhotos();
}

// Change view mode
function changeViewMode() {
    albumData.currentView = document.getElementById('viewMode').value;
    updateViewMode();
}

// Update view mode
function updateViewMode() {
    const photoAlbum = document.getElementById('photoAlbum');
    
    switch (albumData.currentView) {
        case 'grid':
            photoAlbum.className = 'photo-grid';
            break;
        case 'masonry':
            photoAlbum.className = 'photo-grid';
            photoAlbum.style.gridTemplateRows = 'masonry';
            break;
        case 'slideshow':
            startSlideshow();
            break;
    }
}

// Start slideshow
function startSlideshow() {
    const modal = document.getElementById('slideshowModal');
    albumData.slideshowIndex = 0;
    updateSlideshowPhoto();
    modal.classList.add('active');
    
    if (albumData.slideshowAutoplay) {
        startSlideshowAutoplay();
    }
}

// Update slideshow photo
function updateSlideshowPhoto() {
    const photo = albumData.photos[albumData.slideshowIndex];
    const slideshowPhoto = document.getElementById('slideshowPhoto');
    const slideshowInfo = document.getElementById('slideshowInfo');
    const slideshowCounter = document.getElementById('slideshowCounter');
    
    if (photo) {
        slideshowPhoto.src = photo.src;
        slideshowInfo.textContent = `${photo.uploaderName} • ${getTimeAgo(photo.timestamp)} • ❤️ ${photo.likes}`;
        slideshowCounter.textContent = `${albumData.slideshowIndex + 1} of ${albumData.photos.length}`;
    }
}

// Previous slide
function previousSlide() {
    albumData.slideshowIndex = (albumData.slideshowIndex - 1 + albumData.photos.length) % albumData.photos.length;
    updateSlideshowPhoto();
}

// Next slide
function nextSlide() {
    albumData.slideshowIndex = (albumData.slideshowIndex + 1) % albumData.photos.length;
    updateSlideshowPhoto();
}

// Toggle slideshow autoplay
function toggleSlideshowAutoplay() {
    albumData.slideshowAutoplay = !albumData.slideshowAutoplay;
    const button = document.getElementById('autoplayButton');
    
    if (albumData.slideshowAutoplay) {
        button.textContent = '⏸️ Pause';
        startSlideshowAutoplay();
    } else {
        button.textContent = '▶️ Play';
        stopSlideshowAutoplay();
    }
}

// Start slideshow autoplay
function startSlideshowAutoplay() {
    if (albumData.slideshowInterval) {
        clearInterval(albumData.slideshowInterval);
    }
    
    albumData.slideshowInterval = setInterval(() => {
        nextSlide();
    }, 3000);
}

// Stop slideshow autoplay
function stopSlideshowAutoplay() {
    if (albumData.slideshowInterval) {
        clearInterval(albumData.slideshowInterval);
        albumData.slideshowInterval = null;
    }
}

// Close slideshow modal
function closeSlideshowModal() {
    document.getElementById('slideshowModal').classList.remove('active');
    stopSlideshowAutoplay();
    document.getElementById('viewMode').value = 'grid';
    albumData.currentView = 'grid';
    updateViewMode();
}

// Open photo modal
function openPhotoModal(photo) {
    const modal = document.getElementById('photoModal');
    const modalPhoto = document.getElementById('modalPhoto');
    const modalTitle = document.getElementById('modalPhotoTitle');
    const modalInfo = document.getElementById('modalPhotoInfo');
    const modalLikeCount = document.getElementById('modalLikeCount');
    
    modalPhoto.src = photo.src;
    modalTitle.textContent = `Photo by ${photo.uploaderName}`;
    modalInfo.textContent = `Uploaded ${getTimeAgo(photo.timestamp)}`;
    modalLikeCount.textContent = photo.likes;
    
    modal.classList.add('active');
    modal.currentPhoto = photo;
}

// Like photo
function likePhoto(button, photoId) {
    const photo = albumData.photos.find(p => p.id === photoId);
    if (photo) {
        photo.likes++;
        
        // Update UI
        const overlay = button.closest('.photo-overlay');
        const likeSpan = overlay.querySelector('span');
        likeSpan.textContent = `❤️ ${photo.likes}`;
        
        // Add animation
        button.style.transform = 'scale(1.2)';
        setTimeout(() => {
            button.style.transform = 'scale(1)';
        }, 200);
        
        console.log(`Photo ${photoId} liked! Total likes: ${photo.likes}`);
    }
}

// Like current photo in modal
function likeCurrentPhoto() {
    const modal = document.getElementById('photoModal');
    const photo = modal.currentPhoto;
    
    if (photo) {
        photo.likes++;
        document.getElementById('modalLikeCount').textContent = photo.likes;
        
        // Update the photo in the grid as well
        renderPhotos();
        
        showToast('Photo liked!', 'success');
    }
}

// Download current photo
function downloadCurrentPhoto() {
    const modal = document.getElementById('photoModal');
    const photo = modal.currentPhoto;
    
    if (photo) {
        const a = document.createElement('a');
        a.href = photo.src;
        a.download = `echomoments-photo-${photo.id}.jpg`;
        a.click();
        showToast('Photo download started', 'success');
    }
}

// Share photo
function sharePhoto() {
    const modal = document.getElementById('photoModal');
    const photo = modal.currentPhoto;
    
    if (photo) {
        const shareUrl = `${window.location.origin}/photo/${photo.id}`;
        
        if (navigator.share) {
            navigator.share({
                title: `Photo by ${photo.uploaderName}`,
                text: `Check out this photo from ${albumData.eventName}!`,
                url: shareUrl
            });
        } else if (navigator.clipboard) {
            navigator.clipboard.writeText(shareUrl);
            showToast('Photo link copied to clipboard!', 'success');
        } else {
            prompt('Copy this link to share the photo:', shareUrl);
        }
    }
}

// Report photo
function reportPhoto() {
    const modal = document.getElementById('photoModal');
    const photo = modal.currentPhoto;
    
    if (photo) {
        const reason = prompt('Please provide a reason for reporting this photo:');
        if (reason) {
            console.log(`Reporting photo ${photo.id}: ${reason}`);
            showToast('Photo reported. Thank you for your feedback.', 'info');
            closeModal('photoModal');
        }
    }
}

// Download all photos
function downloadAllPhotos() {
    console.log('Preparing to download all photos...');
    showToast('Preparing download... This may take a moment.', 'info');
    
    // Simulate download preparation
    setTimeout(() => {
        showToast('Download started! Check your downloads folder.', 'success');
    }, 2000);
}

// Refresh album
function refreshAlbum() {
    console.log('Refreshing album...');
    showToast('Album refreshed!', 'info');
    loadPhotos();
}

// Load more photos
function loadMorePhotos() {
    console.log('Loading more photos...');
    showToast('Loading more photos...', 'info');
    
    // Simulate loading more photos
    setTimeout(() => {
        showToast('No more photos to load', 'info');
        document.getElementById('loadMoreSection').style.display = 'none';
    }, 1000);
}

// Close modal
function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
    if (modalId === 'slideshowModal') {
        stopSlideshowAutoplay();
    }
}

// Utility function to get time ago
function getTimeAgo(timestamp) {
    const now = new Date();
    const diff = now - new Date(timestamp);
    const minutes = Math.floor(diff / (1000 * 60));
    
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes} min ago`;
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

// Toast notification system
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.cssText = `
        position: fixed;
        top: 2rem;
        right: 2rem;
        background: ${type === 'success' ? 'var(--echo-emerald)' : type === 'error' ? '#EF4444' : 'var(--echo-purple)'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: var(--echo-radius);
        box-shadow: var(--echo-shadow);
        z-index: 1001;
        opacity: 0;
        transform: translateX(100%);
        transition: all 0.3s ease;
    `;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    }, 100);
    
    // Auto remove
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// Keyboard navigation for slideshow
document.addEventListener('keydown', function(e) {
    const slideshowModal = document.getElementById('slideshowModal');
    if (slideshowModal.classList.contains('active')) {
        switch (e.key) {
            case 'ArrowLeft':
                previousSlide();
                break;
            case 'ArrowRight':
                nextSlide();
                break;
            case 'Escape':
                closeSlideshowModal();
                break;
            case ' ':
                e.preventDefault();
                toggleSlideshowAutoplay();
                break;
        }
    }
});

// Click outside modal to close
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        if (e.target.id === 'slideshowModal') {
            closeSlideshowModal();
        } else {
            e.target.classList.remove('active');
        }
    }
});
